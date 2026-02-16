import asyncio
import os
import sys
from dotenv import load_dotenv
from google.cloud import firestore
from google.api_core.exceptions import DeadlineExceeded

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.database import db

OLD_CHAT_ID = "-954103380"
NEW_CHAT_ID = "-1003893798466"

async def copy_collection(source_col_ref, target_col_ref, batch_size=50):
    """Copies all documents from source collection to target collection using explicit pagination."""
    print(f"  Processing collection: {source_col_ref.id}")
    
    count = 0
    last_doc = None
    
    while True:
        try:
            # Build query with pagination
            if last_doc:
                # Firestore `start_after` requires the snapshot
                query = source_col_ref.limit(batch_size).start_after(last_doc)
            else:
                query = source_col_ref.limit(batch_size)
            
            # Execute query and buffer results
            current_batch = []
            async for doc in query.stream():
                current_batch.append(doc)
            
            if not current_batch:
                break
                
            # Process batch
            for doc in current_batch:
                try:
                    doc_data = doc.to_dict()
                    await target_col_ref.document(doc.id).set(doc_data)
                    count += 1
                    
                    # Process subcollections (recursive)
                    # Note: collections() returns an async generator
                    async for sub_col in doc.reference.collections():
                         target_sub_col_ref = target_col_ref.document(doc.id).collection(sub_col.id)
                         await copy_collection(sub_col, target_sub_col_ref, batch_size=20) 
                except Exception as e:
                    print(f"    ! Error copying doc {doc.id}: {e}")

            # Update cursor for next page
            last_doc = current_batch[-1]
            print(f"    - Processed batch of {len(current_batch)} (Total: {count})")
            
        except DeadlineExceeded:
            print("    ! Deadline Exceeded. Retrying batch...")
            await asyncio.sleep(2)
            continue
        except Exception as e:
            print(f"    ! Error processing batch in {source_col_ref.id}: {e}")
            break

    print(f"  - Finished copying {count} documents in '{source_col_ref.id}'")

async def migrate():
    print(f"Starting migration from {OLD_CHAT_ID} to {NEW_CHAT_ID}...")
    
    source_chat_ref = db.collection("chats").document(OLD_CHAT_ID)
    target_chat_ref = db.collection("chats").document(NEW_CHAT_ID)
    
    # 1. Copy the main chat document data
    try:
        source_doc = await source_chat_ref.get()
        if source_doc.exists:
            print(f"Found source chat document. Copying data...")
            await target_chat_ref.set(source_doc.to_dict())
        else:
            print(f"Warning: Source chat document {OLD_CHAT_ID} does not exist. Proceeding to subcollections...")
    except Exception as e:
         print(f"Error reading source chat doc: {e}")

    # 2. Copy all subcollections
    print("Discovering subcollections...")
    async for collection in source_chat_ref.collections():
        target_col_ref = target_chat_ref.collection(collection.id)
        await copy_collection(collection, target_col_ref)

    print("\nMigration complete!")

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\nMigration interrupted by user.")
