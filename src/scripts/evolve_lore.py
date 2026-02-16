import asyncio
import os
import sys
import logging
import vertexai
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.services.lore_service import LoreService
from src.utils.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

async def run_evolution(chat_id: int):
    # Initialize Vertex AI
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
    
    print(f"Starting lore evolution for chat {chat_id}...")
    try:
        await LoreService.evolve_lore(chat_id)
        print("Evolution completed.")
    except Exception as e:
        print(f"Error during evolution: {e}")

if __name__ == "__main__":
    # Default chat for testing
    chat_id = settings.MAIN_CHAT_ID
    
    # Check if chat_id provided as arg
    if len(sys.argv) > 1:
        try:
            chat_id = int(sys.argv[1])
        except ValueError:
            print("Invalid chat ID provided.")
            sys.exit(1)
            
    asyncio.run(run_evolution(chat_id))
