import asyncio
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Load env vars first
load_dotenv()

from src.utils.config import settings

async def send_report():
    print("Sending amnesty report...")
    
    report_text = """🧹 <b>Амнистия: Очистка от Нытья и Духоты</b>

Согласно указу, все баллы, начисленные за категории «Нытье» и «Духота», были аннулированы (с учетом прошедших еженедельных списаний).

👤 <b>Влад Берёзкин</b>: -179 очков
👤 <b>Паштет</b>: -159 очков
👤 <b>Elisey Khrapov</b>: -104 очка
👤 <b>Костя Кабан</b>: -80 очков
👤 <b>Макс Костюк</b>: -69 очков
👤 <b>Ваня Любецкий</b>: -50 очков
👤 <b>ustaliyputnik</b>: -34 очка"""

    bot = Bot(token=settings.TELEGRAM_TOKEN)
    try:
        await bot.send_message(chat_id=settings.MAIN_CHAT_ID, text=report_text, parse_mode="HTML")
        print("Report sent successfully.")
    except Exception as e:
        print(f"Failed to send report: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_report())
