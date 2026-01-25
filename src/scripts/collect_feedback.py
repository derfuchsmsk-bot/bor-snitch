import asyncio
import logging
from datetime import datetime, timedelta, timezone
import sys
import os

# Ensure src is in python path if run directly
sys.path.append(os.getcwd())

from src.services.db import db, get_logs_for_time_range
from src.utils.config import settings
import vertexai
from vertexai.generative_models import GenerativeModel

logging.basicConfig(level=logging.INFO)

async def main():
    print("🚀 Starting Feedback Collection...")
    
    try:
        # Init Vertex AI
        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        model = GenerativeModel("gemini-3-flash-preview") # Stronger model for analysis
    except Exception as e:
        print(f"Failed to init Vertex AI: {e}")
        return

    # Time range: Last 14 days (Test period)
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=14)
    
    chats_ref = db.collection("chats")
    report_content = "# 📝 Feedback & Improvement Suggestions Report\n\n"
    report_content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    report_content += f"**Analysis Period:** {start_dt.date()} to {end_dt.date()}\n\n"
    
    print(f"Fetching chats...")
    
    found_chats = False
    
    try:
        # Note: firestore.AsyncClient.collection().stream() is an async generator
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
            
            found_chats = True
            chat_id = chat_doc.id
            print(f"Analyzing chat {chat_id}...")
            
            logs = await get_logs_for_time_range(chat_id, start_dt, end_dt)
            
            if not logs:
                print(f"  - No logs found.")
                continue
            
            print(f"  - Processing {len(logs)} messages...")
            
            # Chunking strategies might be needed for huge logs, but for test period it's likely fine.
            # Gemini 3 Flash context window is huge (1M+ tokens).
            
            chat_text = ""
            for log in logs:
                username = log.get('username', 'Anon')
                text = log.get('text', '')
                # Include date for context
                ts = log.get('timestamp')
                date_str = ts.strftime("%Y-%m-%d") if ts else ""
                chat_text += f"[{date_str}] {username}: {text}\n"
                
            prompt = f"""
            You are a Product Manager analyzing user feedback for a Telegram Bot ("BorSnitchBot").
            
            Analyze the following chat history and extract:
            1. 🐛 **Bug Reports**: Anything users said is broken or not working.
            2. 💡 **Feature Requests**: What users explicitly asked for or implied they want.
            3. 🗣️ **Improvement Suggestions**: Feedback on mechanics (points, snitching, rules).
            4. 📈 **General Sentiment**: How users feel about the bot (Fun? Annoying? Fair?).
            
            Ignore normal conversation unrelated to the bot, unless it shows frustration/joy with the bot.
            Focus on constructive feedback.
            
            Format the output as Markdown. Use bullet points.
            
            CHAT LOGS:
            {chat_text}
            """
            
            try:
                response = await model.generate_content_async(prompt)
                feedback = response.text
                
                report_content += f"## Chat ID: `{chat_id}`\n\n"
                report_content += feedback + "\n\n---\n\n"
                print(f"  - Analysis complete.")
                
            except Exception as e:
                logging.error(f"  - AI Error: {e}")
                report_content += f"## Chat ID: `{chat_id}`\n\nError analyzing chat: {e}\n\n---\n\n"

        if not found_chats:
            print("No active chats found.")
            
        # Write to file
        output_file = "feedback_report.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        print(f"✅ Report saved to {output_file}")
        
    except Exception as e:
        print(f"Critical error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
