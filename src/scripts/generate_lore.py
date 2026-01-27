import asyncio
import logging
from datetime import datetime
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import storage
from src.services.db import db
from src.utils.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Vertex AI
init_params = {
    "project": settings.GCP_PROJECT_ID,
    "location": settings.GCP_LOCATION
}
if settings.GCP_LOCATION != "global":
    init_params["api_transport"] = "grpc"
vertexai.init(**init_params)

async def fetch_all_messages(chat_id):
    """
    Fetches all messages for a given chat ordered by timestamp.
    """
    chat_ref = db.collection("chats").document(str(chat_id))
    messages_ref = chat_ref.collection("messages")
    
    # Stream all messages ordered by timestamp
    query = messages_ref.order_by("timestamp")
    
    messages = []
    async for doc in query.stream():
        data = doc.to_dict()
        messages.append(data)
    
    return messages

async def generate_lore_for_chat(chat_id):
    """
    Generates lore description using Gemini 3 Flash.
    """
    logging.info(f"Fetching messages for chat {chat_id}...")
    messages = await fetch_all_messages(chat_id)
    
    if not messages:
        logging.warning(f"No messages found for chat {chat_id}")
        return None

    logging.info(f"Fetched {len(messages)} messages. Preparing context...")
    
    # Prepare context string
    context_str = ""
    
    # Add archive content
    try:
        archive_path = "archive/processed_Сайонара_тур_МИНСК-КАЗАНЬ-МИНСК-ЛУДИНСК-ЕСЬКИНО-ВЛАДИМИР_minified.txt"
        with open(archive_path, "r", encoding="utf-8") as f:
            archive_text = f.read()
            context_str += f"=== АРХИВ СООБЩЕНИЙ (2025 год) ===\n{archive_text}\n\n=== СВЕЖИЕ СООБЩЕНИЯ ===\n"
            logging.info(f"Loaded archive text: {len(archive_text)} chars")
    except Exception as e:
        logging.error(f"Failed to read archive: {e}")

    for msg in messages:
        username = msg.get('username', 'Unknown')
        text = msg.get('text', '')
        timestamp = msg.get('timestamp')
        date_str = ""
        if timestamp:
            try:
                date_str = f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] "
            except:
                pass
                
        context_str += f"{date_str}{username}: {text}\n"

    logging.info(f"Sending to AI (Length: {len(context_str)} chars)...")
    
    # Use Gemini 3 Flash for large context window (1M+ tokens)
    model = GenerativeModel("gemini-3-flash-preview")
    
    prompt = """
    Проанализируй эту переписку и составь подробное описание "Лора" (Lore) этого чата на русском языке.
    
    Включи следующие разделы:
    1. **Ключевые персонажи**: Опиши характер, повадки, стиль общения и роль каждого активного участника. Кто снитч? Кто душнила? Кто клоун?
    2. **Локальные мемы и приколы**: Опиши повторяющиеся шутки, фразы или ситуации.
    3. **Легендарные события**: Если были какие-то яркие споры, обсуждения или события, упомяни их.
    4. **Общая атмосфера**: Какая атмосфера царит в чате?
    5. **Сленг**: Особые слова или выражения, которые используют участники.
    
    Твой ответ должен быть отформатирован как красивый Markdown файл.
    """
    
    try:
        response = await model.generate_content_async([prompt, context_str])
        return response.text
    except Exception as e:
        logging.error(f"Error generating lore: {e}")
        return None

def upload_to_gcs(content, filename):
    """
    Uploads content to Google Cloud Storage.
    """
    bucket_name = settings.LORE_BUCKET_NAME
    if not bucket_name:
        logging.error("LORE_BUCKET_NAME not set in config. Skipping upload.")
        return

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        
        blob.upload_from_string(content, content_type="text/markdown")
        logging.info(f"Uploaded {filename} to gs://{bucket_name}/{filename}")
    except Exception as e:
        logging.error(f"Failed to upload to GCS: {e}")

async def main():
    logging.info("Starting Lore Generation Script...")
    
    if not settings.LORE_BUCKET_NAME:
        logging.warning("⚠️  LORE_BUCKET_NAME is not set in .env. Files will not be uploaded.")
    
    # Get active chats
    chats_ref = db.collection("chats")
    async for chat_doc in chats_ref.stream():
        chat_data = chat_doc.to_dict()
        if not chat_data.get("active"):
            continue
            
        chat_id = chat_doc.id
        if str(chat_id) != "-954103380":
            continue

        logging.info(f"Processing chat {chat_id}...")
        
        lore_content = await generate_lore_for_chat(chat_id)
        
        if lore_content:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"lore_{chat_id}_{date_str}.md"
            
            # Save locally first (optional, useful for debug)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(lore_content)
            
            upload_to_gcs(lore_content, filename)
            
            logging.info(f"Lore generated and saved for chat {chat_id}")
    
    logging.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
