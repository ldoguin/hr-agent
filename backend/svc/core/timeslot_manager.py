"""
Flexible Timeslot Management Tool for Couchbase.
This tool provides methods to search, add, and delete flexible timeslots in Couchbase.
Timeslots can have variable durations and custom start/end times.
Timeslots are stored in JSON documents, with one document per month.
Each month document contains days, and each day contains a list of timeslots.
Each timeslot has start_time, end_time, duration, and meeting_id.

Uses Couchbase subdoc API for add/delete operations and doc API for search operations.
"""

import os
import logging
import random
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from dateutil import parser
from couchbase.cluster import Cluster, QueryOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from couchbase.management.collections import CreateCollectionSettings
from couchbase.exceptions import DocumentNotFoundException, PathNotFoundException
from couchbase.subdocument import get as subdoc_get, upsert as subdoc_upsert, remove as subdoc_remove
from couchbase.collection import Collection
from couchbase.scope import Scope
from svc.core.db import CouchbaseClient, get_collection
logger = logging.getLogger("uvicorn.error")
from svc.core.config import DEFAULT_AGENDA_COLLECTION, DEFAULT_SCOPE


def get_agenda_collection(cluster: Cluster) -> Collection:
    """
    Get the Agenda collection in the default scope
    """
    try:
        return get_collection(cluster=cluster, collection_name=DEFAULT_AGENDA_COLLECTION)
    except Exception:
        return None


# --------- Database Helper Functions --------- #

def _candidate_key(email: str) -> str:
    """Generate candidate document key."""
    return f"candidate::{email.lower()}"

def _application_key(application_id: str) -> str:
    """Generate application document key."""
    return f"application::{application_id}"

def _meeting_key(meeting_id: str) -> str:
    """Generate meeting document key."""
    return f"meeting::{meeting_id}"

def _pending_email_key(application_id: str) -> str:
    """Generate pending-email document key."""
    return f"pending_email::{application_id}"

def _settings_key() -> str:
    return "settings::auto_send"

def _session_label(session_id: str) -> str:
    """Generate an email label that carries the trace session ID."""
    return f"session::{session_id}"

def _is_session_label(label: str) -> bool:
    return label.startswith("session::")

def _session_id_from_label(label: str) -> str:
    return label.split("::", 1)[1]

# --------- Candidate Functions --------- #

def upsert_candidate(collection: Collection, email: str, name: str) -> Dict[str, Any]:
    """
    Create or update a candidate document.
    """
    key = _candidate_key(email)
    now = datetime.utcnow().isoformat()

    doc = {
        "type": "candidate",
        "email": email.lower(),
        "name": name,
        "updated_at": now,
    }

    # If it already exists, preserve created_at
    try:
        existing = collection.get(key).content_as[dict]
        doc["created_at"] = existing.get("created_at", now)
    except Exception:
        doc["created_at"] = now

    collection.upsert(key, doc)
    return doc

def get_candidate_by_email(collection: Collection, email: str) -> Optional[Dict[str, Any]]:
    """Get candidate by email."""
    key = _candidate_key(email)
    try:
        res = collection.get(key)
        return res.content_as[dict]
    except Exception:
        return None

# --------- Application Functions --------- #

def upsert_application(collection: Collection, application_id: str, email: str, first_name: str, last_name: str, position: str, company_name: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create or update an application document.
    """
    key = _application_key(application_id)
    now = datetime.utcnow().isoformat()

    doc = {
        "type": "application",
        "id": application_id,
        "email": email.lower(),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}".strip(),
        "position": position,
        "company_name": company_name,
        "status": "email_sent",
        "email_sent_at": now,
        "updated_at": now,
        "session_id": session_id,
    }

    # If it already exists, preserve created_at
    try:
        existing = collection.get(key).content_as[dict]
        doc["created_at"] = existing.get("created_at", now)
    except Exception:
        doc["created_at"] = now

    collection.upsert(key, doc)
    return doc

def get_application_by_email(cluster: Cluster, email: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recent application for a given email.
    """
    query = f"SELECT * FROM `{DEFAULT_AGENDA_COLLECTION}` WHERE type = 'application' AND email = $email ORDER BY created_at DESC LIMIT 1"
    try:
        result = cluster.query(query, QueryOptions(parameters={"email": email.lower()}))
        rows = list(result.rows())
        return rows[0] if rows else None
    except Exception:
        return None

def get_application(collection: Collection, key: str) -> Optional[Dict[str, Any]]:
    """
    Get application with key.
    """
    try:
        application = collection.get(key).content_as[dict]
        return application
    except Exception:
        return None

# --------- Meeting Functions --------- #

def create_meeting(collection: Collection, candidate_email: str, slot_iso: str) -> Dict[str, Any]:
    """
    Create a meeting document; assume slot_iso is valid.
    """
    candidate = get_candidate_by_email(candidate_email)
    if candidate is None:
        raise ValueError("Candidate not found")

    meeting_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    doc = {
        "type": "meeting",
        "id": meeting_id,
        "candidate_email": candidate_email.lower(),
        "slot": slot_iso,
        "status": "booked",
        "created_at": now,
    }
    collection.insert(_meeting_key(meeting_id), doc)
    return doc

# --------- AgentC Trace Helpers --------- #

def get_latest_assistant_text(cluster, session_id: str) -> Optional[str]:
    """
    Return the text of the last assistant log entry for a session from agentc.

    This is the canonical source for the agent's reply text — we read it here
    rather than duplicating it in the pending_email document.
    """
    from svc.core.config import AGENT_CATALOG_BUCKET, AGENT_CATALOG_LOGS_SCOPE, AGENT_CATALOG_LOGS_COLLECTION
    keyspace = f"`{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_LOGS_COLLECTION}`"
    # `span` and `timestamp` are reserved words in N1QL — must be backtick-quoted.
    # Use a literal string parameter (safe: session_id is a UUID) to avoid
    # named-parameter dialect differences across SDK versions.
    q = (
        f"SELECT l.content.`value` AS text "
        f"FROM {keyspace} AS l "
        f"WHERE l.`span`.`session` = \"{session_id}\" "
        f"  AND l.content.kind = 'assistant' "
        f"ORDER BY l.`timestamp` DESC LIMIT 1"
    )
    try:
        rows = list(cluster.query(q).rows())
        return rows[0]["text"] if rows else None
    except Exception:
        return None


# --------- Pending Email Functions --------- #

def upsert_pending_email(collection: Collection, application_id: str, subject: str,
                         to: str, email_type: str, inbox_id: Optional[str],
                         message_id: Optional[str]) -> Dict[str, Any]:
    """
    Store send-context for a pending outgoing email.

    Text content is intentionally omitted — it is read from the agentc trace
    (the assistant log entry for the session) so we don't duplicate it.
    An optional 'text_override' field is set when the user edits the draft.
    """
    now = datetime.utcnow().isoformat()
    doc = {
        "type": "pending_email",
        "application_id": application_id,
        "subject": subject,
        "to": to,
        "email_type": email_type,
        "status": "pending",
        "created_at": now,
        "sent_at": None,
        "inbox_id": inbox_id,
        "message_id": message_id,
        "text_override": None,   # set when user edits the draft
    }
    collection.upsert(_pending_email_key(application_id), doc)
    return doc


def get_pending_email(collection: Collection, application_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the pending email for an application, or None if not found / already sent."""
    try:
        doc = collection.get(_pending_email_key(application_id)).content_as[dict]
        return doc if doc.get("status") == "pending" else None
    except Exception:
        return None


def mark_email_sent(collection: Collection, application_id: str) -> None:
    """Mark a pending email as sent."""
    try:
        collection.mutate_in(_pending_email_key(application_id), [
            subdoc_upsert("status", "sent"),
            subdoc_upsert("sent_at", datetime.utcnow().isoformat()),
        ])
    except Exception:
        pass


def update_pending_email_text(collection: Collection, application_id: str, text: str) -> None:
    """Store a user-edited override for the pending email body."""
    try:
        collection.mutate_in(_pending_email_key(application_id), [
            subdoc_upsert("text_override", text),
        ])
    except Exception:
        pass


# --------- Settings Functions --------- #

def get_auto_send_settings(collection: Collection) -> Dict[str, Any]:
    """Return auto-send settings, defaulting to disabled."""
    try:
        return collection.get(_settings_key()).content_as[dict]
    except Exception:
        return {"enabled": False, "min_score": 9}


def upsert_auto_send_settings(collection: Collection, enabled: bool, min_score: int) -> Dict[str, Any]:
    """Persist auto-send settings."""
    doc = {"type": "settings", "key": "auto_send", "enabled": enabled, "min_score": min_score}
    collection.upsert(_settings_key(), doc)
    return doc


def list_applications(cluster: Cluster) -> list[Dict[str, Any]]:
    """Return all application documents, newest first."""
    from svc.core.config import DEFAULT_BUCKET
    keyspace = f"`{DEFAULT_BUCKET}`.`{DEFAULT_SCOPE}`.`{DEFAULT_AGENDA_COLLECTION}`"
    q = f"SELECT t.* FROM {keyspace} AS t WHERE t.type = 'application' ORDER BY t.created_at DESC"
    res = cluster.query(q, QueryOptions())
    return list(res.rows())


def list_meetings(cluster: Cluster) -> list[Dict[str, Any]]:
    """
    Return all booked meeting timeslots from month calendar documents, sorted by start_time.

    Meetings are stored as subdocuments inside month docs (key=YYYY-MM) under
    days.<DD>.timeslots.<id>. Real bookings have a meeting_id starting with 'application::'.

    The scheduling tools write month docs to the same collection as candidates
    (CB_COLLECTION env var), not the agenda collection. We use DEFAULT_COLLECTION here.

    Probes the last 12 / next 12 months by KV get (no index required) then extracts
    timeslots in Python to avoid complex nested N1QL UNNEST chains.
    """
    from svc.core.config import DEFAULT_COLLECTION
    collection = get_collection(cluster=cluster, collection_name=DEFAULT_COLLECTION)
    if collection is None:
        return []

    # Generate candidate month keys for the past 12 months and next 12 months
    now = datetime.utcnow()
    month_keys = []
    for delta in range(-12, 13):
        year = now.year + (now.month - 1 + delta) // 12
        month = (now.month - 1 + delta) % 12 + 1
        month_keys.append(f"{year:04d}-{month:02d}")

    meetings: list[Dict[str, Any]] = []
    for key in month_keys:
        try:
            doc = collection.get(key).content_as[dict]
        except Exception:
            continue  # month doc doesn't exist, skip

        month = doc.get("month", key)
        days = doc.get("days", {})
        for _day_key, day_doc in days.items():
            if not isinstance(day_doc, dict):
                continue
            timeslots = day_doc.get("timeslots", {})
            for _ts_id, ts in timeslots.items():
                if not isinstance(ts, dict):
                    continue
                meeting_id = ts.get("meeting_id", "")
                if not meeting_id or not meeting_id.startswith("application::"):
                    continue
                meetings.append({
                    "meeting_id": meeting_id,
                    "start_time": ts.get("start_time", ""),
                    "end_time": ts.get("end_time", ""),
                    "duration_minutes": ts.get("duration_minutes"),
                    "month": month,
                })

    meetings.sort(key=lambda m: m["start_time"])
    return meetings



def get_month_key(date: datetime) -> str:
    """Generate a month key in format YYYY-MM for document naming."""
    return date.strftime("%Y-%m")

def get_day_key(date: datetime) -> str:
    """Generate a day key in format DD for day identification."""
    return f"{date.day:02d}"

def get_timeslot_path(date: datetime, timeslot_id: str) -> str:
    """Generate the subdocument path for a timeslot in format days.DD.timeslots.ID."""
    return f"days.{get_day_key(date)}.timeslots.{timeslot_id}"

def get_or_create_month_document(scope: Scope, collection_name: str, month_key: str) -> Dict[str, Any]:
    """
    Get or create a month document with the basic structure.
    Each month document contains days, and each day contains a list of timeslots.
    """
    try:
        
        collection = scope.collection(collection_name)

        # Try to get existing document
        try:
            doc = collection.get(month_key)
            return doc.content_as[dict]
        except DocumentNotFoundException:
            # Create new document with empty structure for all days in the month
            new_doc = {
                "month": month_key,
                "days": {}  # Days will be created on-demand
            }
            collection.insert(month_key, new_doc)
            return new_doc

    except Exception as e:
        logger.error(f"Error getting/creating month document: {str(e)}")
        raise

def generate_timeslot_id() -> str:
    """Generate a unique timeslot ID."""
    return f"ts_{random.randint(1000000000, 9999999999)}"

def search_timeslot(scope: Scope, start_time: datetime, end_time: datetime, collection_name: str = "timeslots") -> Optional[str]:
    """
    Search for available timeslots within a given time range.

    Args:
        start_time: The start datetime of the time range to search
        end_time: The end datetime of the time range to search
        scope: Couchbase active scope
        collection_name: Couchbase collection name

    Returns:
        The meeting document ID if the entire time range is available, None if any part is booked
    """
    try:
        collection = scope.collection(collection_name)

        # Round times to minutes for precision
        start_time = start_time.replace(second=0, microsecond=0)
        end_time = end_time.replace(second=0, microsecond=0)

        # Get the month document
        month_key = get_month_key(start_time)
        day_key = get_day_key(start_time)

        try:
            # Get the full day document to check all timeslots
            doc = collection.get(month_key)
            month_data = doc.content_as[dict]

            if day_key not in month_data.get("days", {}):
                # No timeslots exist for this day, time range is available
                return None

            day_data = month_data["days"][day_key]
            timeslots = day_data.get("timeslots", {})

            # Check if the requested time range conflicts with any existing timeslots
            for timeslot_id, timeslot_data in timeslots.items():
                # Handle case where timeslot_data might be a string (from legacy hourly timeslots)
                if isinstance(timeslot_data, str):
                    # This is a legacy hourly timeslot, convert to new format
                    try:
                        hour = int(timeslot_id)
                        existing_start = start_time.replace(hour=hour, minute=0, second=0, microsecond=0)
                        existing_end = existing_start + timedelta(hours=1)
                        meeting_id = timeslot_data
                    except ValueError:
                        continue
                else:
                    existing_start_str = timeslot_data.get("start_time")
                    existing_end_str = timeslot_data.get("end_time")

                    if existing_start_str and existing_end_str:
                        try:
                            # Convert string times to datetime objects for comparison
                            existing_start = datetime.fromisoformat(existing_start_str)
                            existing_end = datetime.fromisoformat(existing_end_str)
                            meeting_id = timeslot_data.get("meeting_id")
                        except ValueError:
                            continue
                    else:
                        continue

                # Check for overlap
                if not (end_time <= existing_start or start_time >= existing_end):
                    # There's an overlap, return the meeting ID
                    return meeting_id

            # No conflicts found, time range is available
            return None

        except DocumentNotFoundException:
            # Document doesn't exist, time range is available
            return None

    except Exception as e:
        logger.error(f"Error searching timeslot: {str(e)}")
        return None

def add_timeslot(start_time: datetime, end_time: datetime, meeting_doc_id: str,
                scope: Scope, collection_name: str = "timeslots") -> bool:
    """
    Add a flexible timeslot (book a meeting) using Couchbase subdoc API.

    Args:
        start_time: The start datetime of the timeslot
        end_time: The end datetime of the timeslot
        meeting_doc_id: The ID of the meeting document to store in the timeslot
        scope: Couchbase active scope
        collection_name: Couchbase collection name

    Returns:
        True if successful, False otherwise
    """
    try:
        # Round times to minutes for precision
        start_time = start_time.replace(second=0, microsecond=0)
        end_time = end_time.replace(second=0, microsecond=0)

        # Calculate duration in minutes
        duration_minutes = int((end_time - start_time).total_seconds() / 60)

        month_key = get_month_key(start_time)
        day_key = get_day_key(start_time)
        timeslot_id = generate_timeslot_id()
        timeslot_path = get_timeslot_path(start_time, timeslot_id)

        collection = scope.collection(collection_name)

        # Ensure the month document exists
        get_or_create_month_document(scope, collection_name, month_key)

        # Create the timeslot data
        timeslot_data = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration_minutes,
            "meeting_id": meeting_doc_id
        }

        # Use subdocument mutation to set the timeslot
        collection.mutate_in(month_key, [
            subdoc_upsert(timeslot_path, timeslot_data, xattr=False, create_parents=True)
        ])

        return True

    except Exception as e:
        logger.error(f"Error adding timeslot: {str(e)}")
        return False

def delete_timeslot(start_time: datetime, end_time: datetime, scope: Scope, collection_name: str = "timeslots") -> bool:
    """
    Delete a flexible timeslot (cancel a meeting) using Couchbase subdoc API.

    Args:
        start_time: The start datetime of the timeslot to delete
        end_time: The end datetime of the timeslot to delete
        scope: Couchbase active scope
        collection_name: Couchbase collection name

    Returns:
        True if successful, False otherwise
    """
    try:
        # Round times to minutes for precision
        start_time = start_time.replace(second=0, microsecond=0)
        end_time = end_time.replace(second=0, microsecond=0)

        month_key = get_month_key(start_time)
        day_key = get_day_key(start_time)
        
        collection = scope.collection(collection_name)

        try:
            # Get the month document to find the exact timeslot to delete
            doc = collection.get(month_key)
            month_data = doc.content_as[dict]

            if day_key not in month_data.get("days", {}):
                return False  # No timeslots exist for this day

            day_data = month_data["days"][day_key]
            timeslots = day_data.get("timeslots", {})

            # Find the timeslot that matches the exact start and end time
            timeslot_to_delete = None
            for timeslot_id, timeslot_data in timeslots.items():
                existing_start = timeslot_data.get("start_time")
                existing_end = timeslot_data.get("end_time")

                if existing_start and existing_end:
                    existing_start_dt = datetime.fromisoformat(existing_start)
                    existing_end_dt = datetime.fromisoformat(existing_end)

                    if existing_start_dt == start_time and existing_end_dt == end_time:
                        timeslot_to_delete = timeslot_id
                        break

            if timeslot_to_delete:
                timeslot_path = get_timeslot_path(start_time, timeslot_to_delete)
                # Use subdocument mutation to remove the timeslot
                collection.mutate_in(month_key, [
                    subdoc_remove(timeslot_path, xattr=False)
                ])
                return True
            else:
                return False

        except DocumentNotFoundException:
            return False

    except Exception as e:
        logger.error(f"Error deleting timeslot: {str(e)}")
        return False

def fill_non_working_hours(date: datetime, scope: Scope, non_working_id: str = "non-working", collection_name: str = "timeslots", timezone_offset: int = 0) -> bool:
    """
    Fill non-working hours timeslots (midnight to 9 AM and 6 PM to midnight) for a given date.

    Args:
        date: The date to fill non-working hours for
        non_working_id: The ID to use for non-working timeslots (default: "non-working")
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Apply timezone offset to the date
        tz_date = date + timedelta(hours=timezone_offset)

        month_key = get_month_key(tz_date)
        
        collection = scope.collection(collection_name)

        # Ensure the month document exists
        get_or_create_month_document(scope, collection_name, month_key)

        # Define non-working time ranges
        non_working_ranges = [
            (tz_date.replace(hour=0, minute=0), tz_date.replace(hour=9, minute=0)),  # Midnight to 9 AM
            (tz_date.replace(hour=18, minute=0), tz_date.replace(hour=23, minute=59))  # 6 PM to midnight
        ]

        # Add each non-working time range as a single timeslot
        for start_time, end_time in non_working_ranges:
            success = add_timeslot(start_time, end_time, non_working_id,
                                 scope, collection_name)
            if not success:
                return False

        return True

    except Exception as e:
        logger.error(f"Error filling non-working hours: {str(e)}")
        return False

def fill_non_working_hours_for_month(scope: Scope, year: int, month: int, non_working_id: str = "non-working",
                                   collection_name: str = "timeslots", timezone_offset: int = 0) -> bool:
    """
    Fill non-working hours timeslots for an entire month.

    Args:
        year: The year to fill
        month: The month to fill (1-12)
        non_working_id: The ID to use for non-working timeslots (default: "non-working")
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the number of days in the month
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        first_day = datetime(year, month, 1)
        last_day = datetime(next_year, next_month, 1) - timedelta(days=1)
        num_days = last_day.day

        # Process each day in the month
        for day in range(1, num_days + 1):
            current_date = datetime(year, month, day)
            success = fill_non_working_hours(
                current_date, non_working_id, scope,
                collection_name, timezone_offset
            )
            if not success:
                return False

        return True

    except Exception as e:
        logger.error(f"Error filling non-working hours for month: {str(e)}")
        return False

def find_next_available_timeslots(scope: Scope, start_time: datetime, duration_minutes: int = 60, count: int = 10,
                               collection_name: str = "timeslots", timezone_offset: int = 0) -> List[Tuple[datetime, datetime]]:
    """
    Find the next available timeslots starting from a given time.

    Args:
        start_time: The starting time to search from
        duration_minutes: Duration of each timeslot to find (default: 60 minutes)
        count: Number of available timeslots to find (default: 10)
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        List of available time ranges as (start_time, end_time) tuples
    """
    try:
        available_timeslots = []
        current_time = start_time.replace(minute=0, second=0, microsecond=0)  # Round to minute

        # Apply timezone offset
        tz_current_time = current_time + timedelta(hours=timezone_offset)

        collection = scope.collection(collection_name)

        # Search through subsequent time ranges until we find enough available timeslots
        searches = 0
        max_searches = 1000  # Safety limit

        while len(available_timeslots) < count and searches < max_searches:
            # Calculate end time for this timeslot
            end_time = tz_current_time + timedelta(minutes=duration_minutes)

            # Check if this time range is available
            meeting_id = search_timeslot(scope, tz_current_time, end_time, collection_name)

            if meeting_id is None:
                # Convert back to original timezone for return
                original_start = tz_current_time - timedelta(hours=timezone_offset)
                original_end = end_time - timedelta(hours=timezone_offset)
                available_timeslots.append((original_start, original_end))

            # Move to next time slot (by duration_minutes)
            tz_current_time = end_time
            searches += 1

        return available_timeslots

    except Exception as e:
        logger.error(f"Error finding next available timeslots: {str(e)}")
        return []

def is_weekend(date: datetime) -> bool:
    """
    Check if a given date is a weekend (Saturday or Sunday).

    Args:
        date: The datetime object to check

    Returns:
        True if the date is Saturday or Sunday, False otherwise
    """
    return date.weekday() >= 5  # 5 = Saturday, 6 = Sunday

def fill_weekend_timeslots(scope: Scope, date: datetime, weekend_id: str = "weekend",
                          collection_name: str = "timeslots", timezone_offset: int = 0) -> bool:
    """
    Fill all timeslots for a weekend day (Saturday or Sunday) as a single timeslot.

    Args:
        date: The date to fill (must be Saturday or Sunday)
        weekend_id: The ID to use for weekend timeslots (default: "weekend")
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if the date is actually a weekend
        if not is_weekend(date):
            logger.warning(f"Date {date} is not a weekend day")
            return False

        # Apply timezone offset to the date
        tz_date = date + timedelta(hours=timezone_offset)

        # Create a single timeslot for the entire day
        start_time = tz_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = tz_date.replace(hour=23, minute=59, second=0, microsecond=0)

        success = add_timeslot(scope, start_time, end_time, weekend_id, collection_name)
        return success

    except Exception as e:
        logger.error(f"Error filling weekend timeslots: {str(e)}")
        return False

def fill_weekend_timeslots_for_month(scope: Scope, year: int, month: int, weekend_id: str = "weekend",
                                   collection_name: str = "timeslots", timezone_offset: int = 0) -> bool:
    """
    Fill all weekend timeslots for an entire month.

    Args:
        year: The year to fill
        month: The month to fill (1-12)
        weekend_id: The ID to use for weekend timeslots (default: "weekend")
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the number of days in the month
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        first_day = datetime(year, month, 1)
        last_day = datetime(next_year, next_month, 1) - timedelta(days=1)
        num_days = last_day.day

        # Process each day in the month
        for day in range(1, num_days + 1):
            current_date = datetime(year, month, day)
            if is_weekend(current_date):
                success = fill_weekend_timeslots(scope, 
                    current_date, weekend_id,
                    collection_name, timezone_offset
                )
                if not success:
                    return False

        return True

    except Exception as e:
        logger.error(f"Error filling weekend timeslots for month: {str(e)}")
        return False

def generate_meeting_id(prefix: str = "meeting", meeting_number: int = None) -> str:
    """
    Generate a unique meeting ID.

    Args:
        prefix: Prefix for the meeting ID (default: "meeting")
        meeting_number: Optional meeting number to include

    Returns:
        Generated meeting ID string
    """
    if meeting_number is not None:
        return f"{prefix}_{meeting_number:06d}"
    else:
        return f"{prefix}_{random.randint(100000, 999999)}"

def get_work_hours_availabilities(scope: Scope, start_date: datetime = None, days_count: int = 5,
                                collection_name: str = "timeslots", timezone_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get work hours availabilities for the next specified number of work days.

    Args:
        scope: Couchbase active scope
        start_date: The starting date (default: today)
        days_count: Number of work days to check (default: 5)
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        List of dictionaries with availability information for each work day:
        [
            {
                'date': 'YYYY-MM-DD',
                'day_of_week': 'Monday/Tuesday/etc',
                'working_hours': [
                    {
                        'start_time': 'HH:MM',
                        'end_time': 'HH:MM',
                        'duration_minutes': int,
                        'available': bool,
                        'meeting_id': str or None
                    },
                    ...
                ],
                'total_available_minutes': int,
                'total_booked_minutes': int
            },
            ...
        ]
    """
    try:
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Ensure timezone_offset is an integer
        timezone_offset = int(timezone_offset)

        # Apply timezone offset
        tz_start_date = start_date + timedelta(hours=timezone_offset)

        result = []
        work_days_found = 0
        current_date = tz_start_date
        max_days_to_search = 365  # Safety limit

        while work_days_found < days_count and max_days_to_search > 0:
            # Skip weekends
            if is_weekend(current_date):
                current_date += timedelta(days=1)
                max_days_to_search -= 1
                continue

            # This is a work day, process it
            work_day_info = {
                'date': (current_date - timedelta(hours=timezone_offset)).strftime('%Y-%m-%d'),
                'day_of_week': current_date.strftime('%A'),
                'working_hours': [],
                'total_available_minutes': 0,
                'total_booked_minutes': 0
            }

            # Working hours: 9 AM to 5 PM (9-17)
            working_hours = list(range(9, 18))

            for hour in working_hours:
                # Check each hour for availability
                hour_start = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                hour_end = hour_start + timedelta(hours=1)

                # Check if this hour is available
                meeting_id = search_timeslot(scope, hour_start, hour_end, collection_name)

                hour_info = {
                    'start_time': hour_start.strftime('%H:%M'),
                    'end_time': hour_end.strftime('%H:%M'),
                    'duration_minutes': 60,
                    'available': meeting_id is None,
                    'meeting_id': meeting_id
                }

                work_day_info['working_hours'].append(hour_info)

                if meeting_id is None:
                    work_day_info['total_available_minutes'] += 60
                else:
                    work_day_info['total_booked_minutes'] += 60

            result.append(work_day_info)
            work_days_found += 1
            current_date += timedelta(days=1)
            max_days_to_search -= 1

        return result

    except Exception as e:
        logger.error(f"Error getting work hours availabilities: {str(e)}")
        return []

def fill_year_with_random_meetings(scope: Scope, year: int, meeting_probability: float = 0.3,
                                 collection_name: str = "timeslots", timezone_offset: int = 0) -> Dict[str, int]:
    """
    Fill a whole year with randomly scheduled meetings during working hours.

    Args:
        year: The year to fill
        meeting_probability: Probability of scheduling a meeting in each working hour (0.0-1.0)
        scope: Couchbase active scope
        collection_name: Couchbase collection name
        timezone_offset: Timezone offset in hours from UTC (default: 0 for UTC)

    Returns:
        Dictionary with statistics: {
            'total_working_hours': int,
            'meetings_scheduled': int,
            'success_count': int,
            'failure_count': int
        }
    """
    try:
        stats = {
            'total_working_hours': 0,
            'meetings_scheduled': 0,
            'success_count': 0,
            'failure_count': 0
        }

        # Process each month in the year
        for month in range(1, 13):
            # Get the number of days in the month
            if month == 12:
                next_month = 1
                next_year = year + 1
            else:
                next_month = month + 1
                next_year = year

            first_day = datetime(year, month, 1)
            last_day = datetime(next_year, next_month, 1) - timedelta(days=1)
            num_days = last_day.day

            # Process each day in the month
            for day in range(1, num_days + 1):
                current_date = datetime(year, month, day)

                # Skip weekends
                if is_weekend(current_date):
                    continue

                # Apply timezone offset
                tz_date = current_date + timedelta(hours=timezone_offset)

                # Working hours: 9 AM to 5 PM (9-17)
                working_hours = list(range(9, 18))

                # Try to schedule meetings in each working hour
                for hour in working_hours:
                    stats['total_working_hours'] += 1

                    # Randomly decide if we should schedule a meeting
                    if random.random() <= meeting_probability:
                        # Create a random duration meeting (30-120 minutes)
                        duration_minutes = random.choice([30, 60, 90, 120])
                        start_time = tz_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                        end_time = start_time + timedelta(minutes=duration_minutes)

                        # Generate a meeting ID
                        meeting_id = generate_meeting_id("meeting", stats['meetings_scheduled'] + 1)

                        # Try to add the timeslot
                        success = add_timeslot(scope, start_time, end_time, meeting_id, collection_name)

                        if success:
                            stats['success_count'] += 1
                            stats['meetings_scheduled'] += 1
                        else:
                            stats['failure_count'] += 1

        return stats
    except Exception as e:
        logger.error(f"Error filling year with random meetings: {str(e)}")
        return {
            'total_working_hours': 0,
            'meetings_scheduled': 0,
            'success_count': 0,
            'failure_count': 0
        }

# Example usage and testing
if __name__ == "__main__":
    print("Test code disabled - functions now require scope parameter")
    print("To test, use the functions from search_hr_availabilites.py or other calling modules")
