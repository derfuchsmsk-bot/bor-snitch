import os
from dotenv import load_dotenv
load_dotenv()

from google.cloud import firestore
from src.utils.config import settings

# Initialize Firestore Async Client
# Note: Requires GOOGLE_APPLICATION_CREDENTIALS env var or running in GCP
db = firestore.AsyncClient(project=settings.GCP_PROJECT_ID)
