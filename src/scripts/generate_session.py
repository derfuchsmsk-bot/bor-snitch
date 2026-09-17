import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 32869643
API_HASH = "181e407b416fa55e1bdc0effea81bbe4"

print("=" * 60)
print("🔑 Генератор TELEGRAM_STRING_SESSION для голосового чата")
print("=" * 60)
print("Сейчас скрипт запросит номер телефона (в формате +7...) и код подтверждения из Telegram.\n")

try:
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_str = client.session.save()
        print("\n" + "=" * 60)
        print("✅ ВАША СТРОКА СЕССИИ (СКОПИРУЙТЕ ЕЁ ПОЛНОСТЬЮ):")
        print("=" * 60)
        print(session_str)
        print("=" * 60)
except Exception as e:
    print(f"\n❌ Ошибка авторизации: {e}")
