"""
Centralized database connection logic for Couchbase.
"""
from __future__ import annotations
import os
import json
import logging
import time
import httpx

from couchbase.cluster import Cluster, QueryOptions
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.management.search import SearchIndex
from datetime import timedelta
from typing import Dict, List, Optional
from svc.core.config import DEFAULT_BUCKET, DEFAULT_SCOPE, DEFAULT_COLLECTION

logger = logging.getLogger("uvicorn.error")

@staticmethod
def get_collection(cluster=None, bucket_name=None, scope_name=None, collection_name=None):
    """
    Get a specific collection from the cluster.
    """
    if not cluster:
        cluster = db_manager.get_cluster_connection()
        if not cluster:
            raise ConnectionError("Could not obtain cluster connection")

    bucket_name = bucket_name or DEFAULT_BUCKET
    scope_name = scope_name or DEFAULT_SCOPE
    collection_name = collection_name or DEFAULT_COLLECTION

    bucket = cluster.bucket(bucket_name)
    scope = bucket.scope(scope_name)
    return scope.collection(collection_name)


@staticmethod
def test_capella_connectivity(api_key: str = None, endpoint: str = None) -> bool:
    """Test connectivity to Capella AI services."""
    try:
        test_key = api_key or os.getenv("CAPELLA_API_EMBEDDINGS_KEY") or os.getenv("CAPELLA_API_LLM_KEY")
        test_endpoint = endpoint or os.getenv("CAPELLA_API_ENDPOINT")

        if not test_key or not test_endpoint:
            return False

        headers = {"Authorization": f"Bearer {test_key}"}

        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{test_endpoint.rstrip('/')}/v1/models", headers=headers)
            return response.status_code < 500
    except Exception as e:
        logger.error(f"⚠️ Capella connectivity test failed: {e}")
        return False



class CouchbaseClient:
    """Centralized Couchbase client for HR agent operations."""

    def __init__(self, conn_string: str, username: str, password: str, bucket_name: str):
        """Initialize Couchbase client with connection details."""
        self.conn_string = conn_string
        self.username = username
        self.password = password
        self.bucket_name = bucket_name
        self.cluster = None
        self.bucket = None
        self._collections = {}

    def connect(self):
        """Establish connection to Couchbase cluster."""
        try:
            self.cluster = self.get_cluster_connection()
            if not self.cluster:
                 raise ConnectionError("Failed to connect to Couchbase")
            return self.cluster
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Couchbase: {e}")

    def close(self):
        """Establish connection to Couchbase cluster."""
        try:
            if not self.cluster:
                 raise ConnectionError("Failed to close Couchbase connection, cluister object not initialized")
            self.cluster.close
        except Exception as e:
            raise ConnectionError(f"Failed to close Couchbase connection: {e}")


    def get_cluster_connection(self) -> Optional[Cluster]:
        """
        Get a Couchbase cluster connection.
        Returns the existing connection if one exists, otherwise creates a new one.
        """
        if self.cluster:
            return self.cluster

        try:
            logger.info(f"Connecting to Couchbase at {self.conn_string}...")

            auth = PasswordAuthenticator(self.username, self.password)
            options = ClusterOptions(authenticator=auth)
            options.apply_profile("wan_development")

            cluster = Cluster(self.conn_string, options)
            cluster.wait_until_ready(timedelta(seconds=20))

            self.cluster = cluster
            logger.info(" Successfully connected to Couchbase")
            return cluster

        except Exception as e:
            logger.error(f" Failed to connect to Couchbase: {e}")
            return None



    def setup_collection(self, scope_name: str, collection_name: str, clear_existing_data: bool = False):
        """Setup collection - create scope and collection if they don't exist."""
        try:
            if not self.cluster:
                self.connect()

            if not self.bucket:
                self.bucket = self.cluster.bucket(self.bucket_name)
                logger.info(f"✅ Connected to bucket '{self.bucket_name}'")

            bucket_manager = self.bucket.collections()
            scopes = bucket_manager.get_all_scopes()
            scope_exists = any(scope.name == scope_name for scope in scopes)

            if not scope_exists and scope_name != "_default":
                logger.info(f"Creating scope '{scope_name}'...")
                bucket_manager.create_scope(scope_name)
                logger.info(f"✅ Scope '{scope_name}' created")

            collections = bucket_manager.get_all_scopes()
            collection_exists = any(
                scope.name == scope_name
                and collection_name in [col.name for col in scope.collections]
                for scope in collections
            )

            if collection_exists:
                if clear_existing_data:
                    logger.info(f"Collection '{collection_name}' exists, clearing data...")
                    self.clear_collection_data(scope_name, collection_name)
                else:
                    logger.info(f"✅ Collection '{collection_name}' exists")
            else:
                logger.info(f"Creating collection '{collection_name}'...")
                bucket_manager.create_collection(scope_name, collection_name)
                logger.info(f"✅ Collection '{collection_name}' created")

            time.sleep(3)

            # Create primary index
            try:
                self.cluster.query(
                    f"CREATE PRIMARY INDEX IF NOT EXISTS ON `{self.bucket_name}`.`{scope_name}`.`{collection_name}`"
                ).execute()
                logger.info("✅ Primary index created")
            except Exception as e:
                logger.warning(f"Error creating primary index: {e}")

            return self.bucket.scope(scope_name).collection(collection_name)

        except Exception as e:
            raise RuntimeError(f"Error setting up collection: {e}")

    def clear_collection_data(self, scope_name: str, collection_name: str):
        """Clear all data from a collection."""
        try:
            delete_query = f"DELETE FROM `{self.bucket_name}`.`{scope_name}`.`{collection_name}`"
            self.cluster.query(delete_query)
            time.sleep(2)
            logger.info("✅ Collection data cleared")
        except Exception as e:
            logger.warning(f"Error clearing collection data: {e}")

    def setup_vector_search_index(self, index_definition: dict, scope_name: str):
        """Setup vector search index for the specified scope.
        
        Note: For Capella, you may need to create the search index via the Capella UI first.
        Set environment variable SKIP_INDEX_CREATION=true to skip programmatic index creation.
        """
        try:
            if not self.bucket:
                raise RuntimeError("Bucket not initialized")

            index_name = index_definition["name"]
            scope_index_manager = self.bucket.scope(scope_name).search_indexes()
            
            # Check if index already exists
            try:
                existing_indexes = scope_index_manager.get_all_indexes()
                existing_index_names = [index.name for index in existing_indexes]
                
                if index_name in existing_index_names:
                    logger.info(f"✅ Vector search index '{index_name}' already exists")
                    return
            except Exception as e:
                logger.warning(f"Could not list existing indexes: {e}")
                existing_index_names = []
            
            # Skip creation if env var is set (useful for Capella where index should be created via UI)
            if os.getenv("SKIP_INDEX_CREATION", "").lower() == "true":
                logger.warning(f"⚠️ SKIP_INDEX_CREATION is set. Please create index '{index_name}' manually in Capella UI.")
                logger.info(f"Index definition: {json.dumps(index_definition, indent=2)}")
                return

            # Try to create the index
            logger.info(f"Creating vector search index '{index_name}'...")
            try:
                search_index = SearchIndex.from_json(index_definition)
                scope_index_manager.upsert_index(search_index)
                logger.info(f"✅ Vector search index '{index_name}' created")
            except Exception as create_error:
                error_msg = str(create_error)
                if "already exists" in error_msg.lower():
                    logger.info(f"✅ Vector search index '{index_name}' already exists")
                elif "internal_server_failure" in error_msg.lower():
                    logger.error(f"❌ Failed to create index programmatically. This is common with Capella.")
                    logger.error(f"Please create the index '{index_name}' manually in Capella UI:")
                    logger.error(f"  1. Go to your Capella cluster > Search")
                    logger.error(f"  2. Create a new search index on scope '{scope_name}'")
                    logger.error(f"  3. Use the index definition from agentcatalog_index.json")
                    logger.error(f"  4. Set SKIP_INDEX_CREATION=true to skip this step")
                    raise
                else:
                    raise
                    
        except Exception as e:
            raise RuntimeError(f"Error setting up vector search index: {e}")

    def setup_vector_store(self, scope_name, collection_name, index_name, embeddings, llm, resume_dir):
        """Setup vector store with resume data."""
        try:
            # Import the resume loader
            from svc.data.resume_loader import load_resumes_to_couchbase

            # Load resume data
            load_resumes_to_couchbase(
                cluster=self.cluster,
                bucket_name=self.bucket_name,
                scope_name=scope_name,
                collection_name=collection_name,
                embeddings=embeddings,
                index_name=index_name,
                resume_dir=resume_dir,
                llm_client=llm,
            )
            logger.info("✅ Resume data loaded into vector store")

        except Exception as e:
            raise RuntimeError(f"Error setting up vector store: {e}")

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

    # --------- Candidate Functions --------- #

    def upsert_candidate(email: str, name: str) -> Dict[str, Any]:
        """
        Create or update a candidate document.
        """
        coll = get_collection()
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
            existing = coll.get(key).content_as[dict]
            doc["created_at"] = existing.get("created_at", now)
        except Exception:
            doc["created_at"] = now

        coll.upsert(key, doc)
        return doc

    def get_candidate_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get candidate by email."""
        coll = get_collection()
        key = _candidate_key(email)
        try:
            res = coll.get(key)
            return res.content_as[dict]
        except Exception:
            return None

    # --------- Application Functions --------- #

    def upsert_application(application_id: str, email: str, first_name: str, last_name: str, position: str, company_name: str) -> Dict[str, Any]:
        """
        Create or update an application document.
        """
        coll = get_collection()
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
        }

        # If it already exists, preserve created_at
        try:
            existing = coll.get(key).content_as[dict]
            doc["created_at"] = existing.get("created_at", now)
        except Exception:
            doc["created_at"] = now

        coll.upsert(key, doc)
        return doc

    def get_application_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent application for a given email.
        """
        cluster = get_cluster()
        query = f"SELECT * FROM `{CB_BUCKET}` WHERE type = 'application' AND email = $email ORDER BY created_at DESC LIMIT 1"
        try:
            result = cluster.query(query, QueryOptions(parameters={"email": email.lower()}))
            rows = list(result.rows())
            return rows[0] if rows else None
        except Exception:
            return None

    def get_application(key: str) -> Optional[Dict[str, Any]]:
        """
        Get application with key.
        """
        coll = get_collection()
        try:
            application = coll.get(key).content_as[dict]
            return application
        except Exception:
            return None

    # --------- Meeting Functions --------- #

    def create_meeting(candidate_email: str, slot_iso: str) -> Dict[str, Any]:
        """
        Create a meeting document; assume slot_iso is valid.
        """
        coll = get_collection()
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
        coll.insert(_meeting_key(meeting_id), doc)
        return doc

    def list_meetings() -> list[Dict[str, Any]]:
        """
        Query all meetings from the bucket.
        """
        cluster = get_cluster()
        q = f"SELECT `{CB_BUCKET}`.* FROM `{CB_BUCKET}` WHERE type = 'meeting'"
        res = cluster.query(q, QueryOptions())
        return list(res.rows())
