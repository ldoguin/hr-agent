import os
import pathlib

from starlette.config import Config

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default configuration
DEFAULT_BUCKET = os.getenv("CB_BUCKET", "default")
DEFAULT_SCOPE = os.getenv("CB_SCOPE", "agentc_data")
DEFAULT_COLLECTION = os.getenv("CB_COLLECTION", "candidates")
DEFAULT_AGENDA_COLLECTION = os.getenv("CB_AGENDA_COLLECTION", "timeslots")
DEFAULT_INDEX = os.getenv("CB_INDEX", "candidates_index")
DEFAULT_RESUME_DIR = os.getenv("RESUME_DIR", "resumes")

CB_CONN_STRING = os.getenv("CB_CONN_STRING", "couchbase://localhost")
CB_USERNAME = os.getenv("CB_USERNAME", "Administrator")
CB_PASSWORD = os.getenv("CB_PASSWORD", "password")

ROOT = pathlib.Path(__file__).resolve().parent.parent  # svc/
BASE_DIR = ROOT.parent  # ./

config = Config(BASE_DIR / ".env")


API_USERNAME = config("API_USERNAME", str)
API_PASSWORD = config("API_PASSWORD", str)

# Auth configs.
API_SECRET_KEY = config("API_SECRET_KEY", str)
API_ALGORITHM = config("API_ALGORITHM", str)
API_ACCESS_TOKEN_EXPIRE_MINUTES = config(
    "API_ACCESS_TOKEN_EXPIRE_MINUTES", int
)  # infinity


# AI configuration
CAPELLA_API_ENDPOINT = os.getenv("CAPELLA_API_ENDPOINT")
CAPELLA_API_EMBEDDINGS_KEY = os.getenv("CAPELLA_API_EMBEDDINGS_KEY")
CAPELLA_API_EMBEDDING_MODEL = os.getenv("CAPELLA_API_EMBEDDING_MODEL")
CAPELLA_API_LLM_KEY = os.getenv("CAPELLA_API_LLM_KEY")
CAPELLA_API_LLM_MODEL = os.getenv("CAPELLA_API_LLM_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# AgentMail configuration
INBOX_USERNAME = os.getenv("INBOX_USERNAME", "hrbot")
PORT = int(os.getenv("AGENTMAIL_PORT", "8000"))
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "llama-daring-thankingly.ngrok-free.app")
AGENTMAIL_API_KEY = os.getenv("AGENTMAIL_API_KEY")

# Agent Catalog activity log location (agentc defaults)
AGENT_CATALOG_BUCKET = os.getenv("AGENT_CATALOG_BUCKET", "agentc")
AGENT_CATALOG_LOGS_SCOPE = os.getenv("AGENT_CATALOG_LOGS_SCOPE", "agent_activity")
AGENT_CATALOG_LOGS_COLLECTION = os.getenv("AGENT_CATALOG_LOGS_COLLECTION", "logs")
AGENT_CATALOG_GRADES_COLLECTION = os.getenv("AGENT_CATALOG_GRADES_COLLECTION", "grades")
SERVER_URL = os.getenv("SERVER_URL", "")