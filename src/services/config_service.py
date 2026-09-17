import logging
from ..database import db
from ..utils.game_config import config, DEFAULT_CONFIG_VALUES

logger = logging.getLogger(__name__)

CONFIG_COLLECTION = "system_config"
CONFIG_DOC = "game_config"

class ConfigService:
    @staticmethod
    async def load_config() -> dict:
        """
        Loads configuration from Firestore into the global `config` singleton.
        If no configuration exists in DB yet, keeps default in-memory values and seeds DB.
        """
        try:
            doc_ref = db.collection(CONFIG_COLLECTION).document(CONFIG_DOC)
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                config.update_from_dict(data)
                logger.info("Successfully loaded dynamic GameConfig from Firestore.")
            else:
                logger.info("No saved GameConfig found in Firestore. Seeding defaults...")
                initial_data = config.to_dict()
                await doc_ref.set(initial_data)
        except Exception as e:
            logger.warning(f"Could not load GameConfig from Firestore (using defaults): {e}")

        return config.to_dict()

    @staticmethod
    async def save_config(updates: dict) -> dict:
        """
        Updates the global in-memory `config` and persists the updated settings to Firestore.
        """
        config.update_from_dict(updates)
        current_data = config.to_dict()

        try:
            doc_ref = db.collection(CONFIG_COLLECTION).document(CONFIG_DOC)
            await doc_ref.set(current_data, merge=True)
            logger.info("Saved dynamic GameConfig to Firestore.")
        except Exception as e:
            logger.error(f"Failed to save GameConfig to Firestore: {e}")
            raise

        return current_data

    @staticmethod
    async def reset_config() -> dict:
        """
        Resets `config` to factory defaults and updates Firestore.
        """
        config.reset_to_defaults()
        current_data = config.to_dict()

        try:
            doc_ref = db.collection(CONFIG_COLLECTION).document(CONFIG_DOC)
            await doc_ref.set(current_data)
            logger.info("Reset dynamic GameConfig to defaults in Firestore.")
        except Exception as e:
            logger.error(f"Failed to reset GameConfig in Firestore: {e}")
            raise

        return current_data
