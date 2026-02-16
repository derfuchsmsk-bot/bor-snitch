import asyncio
import sys
import os
from unittest.mock import MagicMock
import types

# Add project root to path
# This script is at src/scripts/verify_refactor.py
script_path = os.path.abspath(__file__)
src_dir = os.path.dirname(os.path.dirname(script_path))
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Create a mock package for google
google = types.ModuleType("google")
google.cloud = types.ModuleType("google.cloud")
sys.modules["google"] = google
sys.modules["google.cloud"] = google.cloud

# Mock firestore
sys.modules["google.cloud.firestore"] = MagicMock()

# Mock aiplatform and vertexai
sys.modules["google.cloud.aiplatform"] = MagicMock()
sys.modules["vertexai"] = MagicMock()
sys.modules["vertexai.generative_models"] = MagicMock()
sys.modules["vertexai.preview"] = MagicMock()

# Mock google.oauth2
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.service_account"] = MagicMock()

async def main():
    print("Verifying Refactor Structure (Mocked DB & AI)...")
    
    try:
        # Mocking the database module to avoid actual initialization
        # We need to ensure src.database is mocked before any service imports it
        sys.modules["src.database"] = MagicMock()
        sys.modules["src.database"].db = MagicMock()
        
        # Now try importing from the new structure
        from src.services.db import get_current_season_id
        print("✅ src.services.db import successful")
        
        from src.repositories.user_repository import user_repository
        from src.repositories.message_repository import message_repository
        from src.repositories.agreement_repository import agreement_repository
        from src.repositories.fact_repository import fact_repository
        
        print("✅ Repositories import successful")
        
        from src.models.user import UserStats
        from src.models.message import MessageModel
        from src.models.agreement import AgreementModel
        from src.models.fact import FactModel
        
        print("✅ Models import successful")
        
        # Verify Phase 2 Services
        from src.services.chat_service import ChatService
        from src.services.game_service import GameService
        from src.services.report_service import ReportService
        
        print("✅ Phase 2 Services (Chat, Game, Report) import successful")
        
        # Verify Handler injection
        from src.bot.handlers import router
        print("✅ Handlers router imported successful (dependency injection worked)")

        print("\nAll checks passed! The refactoring structure is valid.")
        
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
