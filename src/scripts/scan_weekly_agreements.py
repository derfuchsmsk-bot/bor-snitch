import asyncio
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
load_dotenv()

from src.utils.config import settings
from src.utils.game_config import config
from src.services.analysis_service import AnalysisService
from aiogram import Bot

async def main():
    parser = argparse.ArgumentParser(description="Scan chat logs for agreements over the last N days.")
    parser.add_argument("--chat_id", default=str(settings.MAIN_CHAT_ID), help="Target chat ID (default: MAIN_CHAT_ID)")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back (default: 7)")
    parser.add_argument("--notify", action="store_true", help="Send announcement message to Telegram chat")
    args = parser.parse_args()

    print(f"=== Scanning agreements for chat {args.chat_id} (Past {args.days} days) ===")
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    service = AnalysisService(bot)

    try:
        res = await service.perform_agreement_check(
            chat_id=str(args.chat_id),
            lookback_days=args.days,
            send_message=args.notify
        )
        print(f"Status: {res.get('status')}")
        print(f"Messages scanned: {res.get('messages_scanned', 0)}")
        new_ag = res.get('new_agreements', [])
        print(f"New agreements found: {len(new_ag)}")
        for idx, ag in enumerate(new_ag, 1):
            print(f"  {idx}. [{ag.get('type')}] {ag.get('users')}: {ag.get('text')}")
        upd_ag = res.get('updated_agreements', [])
        if upd_ag:
            print(f"Updated agreements: {len(upd_ag)}")
            for idx, ag in enumerate(upd_ag, 1):
                print(f"  {idx}. {ag.get('text')}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
