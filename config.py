import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Load Secrets ---
AI_PIPE_TOKEN = os.getenv("AI_PIPE_TOKEN")
AI_PIPE_URL = os.getenv("AI_PIPE_URL")
MY_SECRET = os.getenv("MY_SECRET")

# --- Configure API ---
if not AI_PIPE_TOKEN:
    raise ValueError("AI_PIPE_TOKEN not found or not set in .env file.")
if not AI_PIPE_URL:
    raise ValueError("AI_PIPE_URL not found or not set in .env file.")
if not MY_SECRET or MY_SECRET == "your_project_secret_from_google_form":
    raise ValueError("MY_SECRET not found or not set in .env file.")

# --- Setup Professional Logger ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - (%(module)s.%(funcName)s) - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("project_run.log"), # Saves logs to a file
        logging.StreamHandler()                  # Prints logs to the console
    ]
)

logger = logging.getLogger(__name__)

logger.info("Configuration loaded. Logging is active. Using AI Pipe endpoint.")