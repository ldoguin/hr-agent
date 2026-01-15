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
