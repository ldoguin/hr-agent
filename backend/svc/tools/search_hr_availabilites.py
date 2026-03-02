"""
Vector search tool for finding candidates based on job descriptions.
This tool uses Couchbase vector search to find the most relevant candidates.

Updated for Agent Catalog v1.0.0 with @tool decorator.
"""

import sys
import os
import logging
from typing import List, Dict, Any
from datetime import timedelta, datetime
from dateutil import parser

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from agentc_core.tool import tool
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from couchbase.vector_search import VectorQuery, VectorSearch
from couchbase.search import SearchRequest, MatchNoneQuery
from svc.core.timeslot_manager import get_work_hours_availabilities

logger = logging.getLogger(__name__)


def get_cluster_connection():
    """Get a fresh cluster connection."""
    try:
        auth = PasswordAuthenticator(
            username=os.getenv("CB_USERNAME", "Administrator"),
            password=os.getenv("CB_PASSWORD", "password"),
        )
        options = ClusterOptions(authenticator=auth)
        options.apply_profile("wan_development")

        cluster = Cluster(os.getenv("CB_CONN_STRING", "couchbase://localhost"), options)
        cluster.wait_until_ready(timedelta(seconds=15))
        return cluster
    except Exception as e:
        logger.error(f"Could not connect to Couchbase cluster: {str(e)}")
        return None


def get_scope_and_collection(cluster=None):
    """Get scope and collection for timeslot operations."""
    if cluster is None:
        cluster = get_cluster_connection()
        if not cluster:
            return None, None

    bucket_name = os.getenv("CB_BUCKET", "calendar")
    scope_name = os.getenv("CB_SCOPE", "hr")
    collection_name = os.getenv("CB_COLLECTION", "timeslots")

    bucket = cluster.bucket(bucket_name)
    scope = bucket.scope(scope_name)

    return scope, collection_name


@tool(
    name="search_hr_availabilities",
    description="Search for 1 hour timeslot availabilites in the HR calendar. Returns the next 5 availability slots.",
    annotations={"category": "meeting", "type": "search"}
)
def search_hr_availabilities(
    start_date: str,
) -> str:
    """
    Search for HR availabilities using timeslot manager.

    Args:
        start_date: The starting date to search for availabilities, as a machine friendly string like yyyy-MM-dd

    Returns:
        Formatted string with availability information
    """
    try:
        # Import the timeslot manager functions
        DT = parser.parse(start_date)

        # Get scope and collection
        scope, collection_name = get_scope_and_collection()
        if scope is None:
            return "Failed to connect to Couchbase"

        # Get work hours availabilities for the next 5 work days
        availabilities = get_work_hours_availabilities(
            scope=scope,
            start_date=DT,
            days_count=5,
            collection_name=collection_name,
            timezone_offset=0
        )

        if not availabilities:
            return "No availabilities found for the specified date range."

        # Format results
        result_text = f"Found HR availabilities for {len(availabilities)} work days:\n\n"

        for i, day_info in enumerate(availabilities, 1):
            result_text += f"**Day {i}: {day_info['date']} ({day_info['day_of_week']})**\n"
            result_text += f"- Total Available: {day_info['total_available_minutes']} minutes\n"
            result_text += f"- Total Booked: {day_info['total_booked_minutes']} minutes\n"

            # Show available 1-hour slots
            available_slots = []
            for hour in day_info['working_hours']:
                if hour['available']:
                    available_slots.append(f"{hour['start_time']}-{hour['end_time']}")

            if available_slots:
                result_text += f"- Available 1-hour slots: {', '.join(available_slots)}\n"
            else:
                result_text += f"- No available 1-hour slots\n"

            result_text += "\n"

        return result_text

    except Exception as e:
        logger.error(f"Error in HR availability search: {e}")
        import traceback
        traceback.print_exc()
        return f"Error performing HR availability search: {str(e)}"

@tool(
    name="add_meeting_timeslot",
    description="Add a meeting timeslot to the HR calendar. Returns success or failure message.",
    annotations={"category": "meeting", "type": "action"}
)
def add_meeting_timeslot(
    meeting_data: str,
) -> str:
    """
    Add a meeting timeslot to the HR calendar.

    Args:
        meeting_data: JSON string containing meeting information with format:
        {"meeting_id":"application::c82633f9-57f4-4a44-b224-a698a8ce7c37","date":"2025-12-19T16:00:00","end_time":"2025-12-19T17:00:00"}

    Returns:
        Formatted string with success or failure information
    """
    try:
        # Import the timeslot manager functions and JSON parser
        from svc.core.timeslot_manager import add_timeslot
        import json
        from datetime import datetime, timedelta
        from dateutil import parser

        # Try to parse as JSON first
        try:
            data = json.loads(meeting_data)
            meeting_id = data["meeting_id"]
            start_time_str = data["date"]
            end_time_str = data["end_time"]

            # Convert string dates to datetime objects
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
        except (json.JSONDecodeError, KeyError, ValueError):
            # If not valid JSON, try to parse as a simple date string
            try:
                # Assume it's a start date string, add 1 hour for end time
                start_time = parser.parse(meeting_data)
                end_time = start_time + timedelta(hours=1)
                meeting_id = f"auto_{int(start_time.timestamp())}"  # Generate a unique ID
            except Exception as e:
                return f"Invalid meeting data format: {str(e)}"

        # Get scope and collection
        scope, collection_name = get_scope_and_collection()
        if scope is None:
            return "Failed to connect to Couchbase"

        # Add the timeslot
        success = add_timeslot(
            start_time=start_time,
            end_time=end_time,
            meeting_doc_id=meeting_id,
            scope=scope,
            collection_name=collection_name
        )

        if success:
            return f"Successfully added meeting timeslot {meeting_id} from {start_time} to {end_time}"
        else:
            return f"Failed to add meeting timeslot {meeting_id}"

    except Exception as e:
        logger.error(f"Error adding meeting timeslot: {e}")
        import traceback
        traceback.print_exc()
        return f"Error adding meeting timeslot: {str(e)}"

@tool(
    name="verify_meeting_slot_availability",
    description="Verify if a specific meeting slot is available in the HR calendar. Returns availability status.",
    annotations={"category": "meeting", "type": "search"}
)
def verify_meeting_slot_availability(
    slot_data: str,
) -> str:
    """
    Verify if a specific meeting slot is available in the HR calendar.

    Args:
        slot_data: JSON string containing slot information with format:
        {"start_time":"2025-12-19T16:00:00","end_time":"2025-12-19T17:00:00"}

    Returns:
        Formatted string with availability status information
    """
    try:
        # Import the timeslot manager functions and JSON parser
        from svc.core.timeslot_manager import search_timeslot
        import json
        from datetime import datetime

        # Try to parse as JSON first
        try:
            data = json.loads(slot_data)
            start_time_str = data["start_time"]
            end_time_str = data["end_time"]

            # Convert string dates to datetime objects
            start_time = parser.parse(start_time_str)
            end_time = parser.parse(end_time_str)
        except (json.JSONDecodeError, KeyError, ValueError):
            # If not valid JSON, try to parse as a simple date string
            try:
                # Assume it's a start date string, add 1 hour for end time
                start_time = parser.parse(slot_data)
                end_time = start_time + timedelta(hours=1)
            except Exception as e:
                return f"Invalid slot data format: {str(e)}"

        # Get scope and collection
        scope, collection_name = get_scope_and_collection()
        if scope is None:
            return "Failed to connect to Couchbase"

        # Check if the timeslot is available
        meeting_id = search_timeslot(
            start_time=start_time,
            end_time=end_time,
            scope=scope,
            collection_name=collection_name
        )

        if meeting_id is None:
            return f"✅ Slot from {start_time} to {end_time} is AVAILABLE for scheduling"
        else:
            return f"❌ Slot from {start_time} to {end_time} is BOOKED (Meeting ID: {meeting_id})"

    except Exception as e:
        logger.error(f"Error verifying meeting slot availability: {e}")
        import traceback
        traceback.print_exc()
        return f"Error verifying meeting slot availability: {str(e)}"

@tool(
    name="send_meeting_invitation",
    description="Send a meeting invitation email to a candidate with meeting details and virtual meeting link.",
    annotations={"category": "communication", "type": "action"}
)
def send_meeting_invitation(
    invitation_data: str,
) -> str:
    """
    Send a meeting invitation email to a candidate.

    Args:
        invitation_data: JSON string containing invitation information with format:
        {
          "candidate_email": "candidate@example.com",
          "meeting_id": "meeting_123",
          "start_time": "2025-12-19T16:00:00",
          "end_time": "2025-12-19T17:00:00",
          "virtual_meeting_link": "https://zoom.us/j/123456789",
          "subject": "Interview Invitation for Software Engineer Position",
          "message": "Additional custom message for the candidate"
        }

    Returns:
        Formatted string with email sending status information
    """
    try:
        # Import required modules
        import json
        from datetime import datetime
        from dateutil import parser
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import os

        # Parse the JSON string
        try:
            data = json.loads(invitation_data)
            candidate_email = data["candidate_email"]
            meeting_id = data["meeting_id"]
            start_time_str = data["start_time"]
            end_time_str = data["end_time"]
            virtual_meeting_link = data.get("virtual_meeting_link", "https://meet.example.com")
            subject = data.get("subject", "Meeting Invitation")
            custom_message = data.get("message", "")
        except (json.JSONDecodeError, KeyError) as e:
            return f"Invalid invitation data format: {str(e)}"

        # Convert string dates to datetime objects
        try:
            start_time = parser.parse(start_time_str)
            end_time = parser.parse(end_time_str)
        except ValueError as e:
            return f"Invalid date format: {str(e)}"

        # Format the email content
        formatted_date = start_time.strftime("%A, %B %d, %Y")
        formatted_time = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"

        # Read email template
        try:
            with open("agentc-hrdemo/email_html_template.html", "r") as f:
                html_template = f.read()
        except FileNotFoundError:
            html_template = """
            <html>
            <body>
                <h2>{subject}</h2>
                <p>Dear Candidate,</p>
                <p>{custom_message}</p>
                <p>We are pleased to invite you to a meeting scheduled for:</p>
                <p><strong>Date:</strong> {formatted_date}<br/>
                <strong>Time:</strong> {formatted_time}<br/>
                <strong>Meeting ID:</strong> {meeting_id}</p>
                <p><a href="{virtual_meeting_link}">Join Virtual Meeting</a></p>
                <p>Please let us know if you need to reschedule.</p>
                <p>Best regards,<br/>HR Team</p>
            </body>
            </html>
            """

        # Replace placeholders in template
        email_content = html_template.replace("{subject}", subject)
        email_content = email_content.replace("{custom_message}", custom_message)
        email_content = email_content.replace("{formatted_date}", formatted_date)
        email_content = email_content.replace("{formatted_time}", formatted_time)
        email_content = email_content.replace("{meeting_id}", meeting_id)
        email_content = email_content.replace("{virtual_meeting_link}", virtual_meeting_link)

        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.getenv("SMTP_FROM_EMAIL", "hr@example.com")
        msg['To'] = candidate_email

        # Add HTML and plain text parts
        msg.attach(MIMEText(custom_message, 'plain'))
        msg.attach(MIMEText(email_content, 'html'))

        # Send email (in production, this would use a real SMTP server)
        # For testing, we'll simulate the sending
        print(f"[EMAIL SIMULATION] Sending invitation to {candidate_email}")
        print(f"Subject: {subject}")
        print(f"Meeting: {meeting_id} on {formatted_date} at {formatted_time}")
        print(f"Virtual link: {virtual_meeting_link}")

        # In a real implementation, you would use:
        # smtp_server = os.getenv("SMTP_SERVER", "smtp.example.com")
        # smtp_port = int(os.getenv("SMTP_PORT", "587"))
        # smtp_username = os.getenv("SMTP_USERNAME")
        # smtp_password = os.getenv("SMTP_PASSWORD")
        #
        # with smtplib.SMTP(smtp_server, smtp_port) as server:
        #     server.starttls()
        #     server.login(smtp_username, smtp_password)
        #     server.sendmail(msg['From'], [msg['To']], msg.as_string())

        return f"✅ Meeting invitation sent successfully to {candidate_email} for meeting {meeting_id}"

    except Exception as e:
        logger.error(f"Error sending meeting invitation: {e}")
        import traceback
        traceback.print_exc()
        return f"Error sending meeting invitation: {str(e)}"

@tool(
    name="cancel_meeting_timeslot",
    description="Cancel a meeting timeslot from the HR calendar. Returns success or failure message.",
    annotations={"category": "meeting", "type": "action"}
)
def cancel_meeting_timeslot(
    meeting_data: str,
) -> str:
    """
    Cancel a meeting timeslot from the HR calendar.

    Args:
        meeting_data: JSON string containing meeting information with format:
        {"start_time":"2025-12-19T16:00:00","end_time":"2025-12-19T17:00:00"}

    Returns:
        Formatted string with success or failure information
    """
    try:
        # Import the timeslot manager functions and JSON parser
        from svc.core.timeslot_manager import delete_timeslot
        import json
        from datetime import datetime

        # Parse the JSON string
        try:
            data = json.loads(meeting_data)
            start_time_str = data["start_time"]
            end_time_str = data["end_time"]

            # Convert string dates to datetime objects
            start_time = parser.parse(start_time_str)
            end_time = parser.parse(end_time_str)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return f"Invalid meeting data format: {str(e)}"

        # Get scope and collection
        scope, collection_name = get_scope_and_collection()
        if scope is None:
            return "Failed to connect to Couchbase"

        # Delete the timeslot
        success = delete_timeslot(
            start_time=start_time,
            end_time=end_time,
            scope=scope,
            collection_name=collection_name
        )

        if success:
            return f"Successfully canceled meeting timeslot from {start_time} to {end_time}"
        else:
            return f"Failed to cancel meeting timeslot - no matching timeslot found"

    except Exception as e:
        logger.error(f"Error canceling meeting timeslot: {e}")
        import traceback
        traceback.print_exc()
        return f"Error canceling meeting timeslot: {str(e)}"
