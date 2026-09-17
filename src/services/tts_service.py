import re
import logging
from google.cloud import texttospeech_v1 as texttospeech
from src.utils.game_config import config

logger = logging.getLogger(__name__)

class TTSService:
    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            cls._client = texttospeech.TextToSpeechAsyncClient()
        return cls._client

    @classmethod
    def clean_text_for_speech(cls, text: str) -> str:
        """Removes markdown syntax, urls, and emojis that might disrupt text-to-speech pronunciation."""
        # Remove markdown bold/italic/code markers
        cleaned = re.sub(r'[*_`#~]', '', text)
        # Remove URLs
        cleaned = re.sub(r'https?://\S+', '', cleaned)
        # Remove usernames @mentions -> just the name
        cleaned = re.sub(r'@([a-zA-Z0-9_]+)', r'\1', cleaned)
        # Collapse whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @classmethod
    async def synthesize_voice_ogg(
        cls,
        text: str,
        voice_name: str = None,
        pitch: float = None,
        speaking_rate: float = None
    ) -> bytes:
        """
        Synthesizes spoken audio from text in OGG_OPUS format (natively supported by Telegram send_voice).
        """
        cleaned_text = cls.clean_text_for_speech(text)
        if not cleaned_text:
            raise ValueError("Empty text for speech synthesis")

        voice_id = voice_name or getattr(config, "VOICE_DIGEST_VOICE", "ru-RU-Wavenet-D")
        pitch_val = pitch if pitch is not None else getattr(config, "VOICE_DIGEST_PITCH", -1.5)
        rate_val = speaking_rate if speaking_rate is not None else getattr(config, "VOICE_DIGEST_SPEED", 1.05)

        # Detect gender from voice name
        gender = texttospeech.SsmlVoiceGender.MALE
        if voice_id.endswith("-A") or voice_id.endswith("-C") or voice_id.endswith("-E") or "Aoede" in voice_id or "Kore" in voice_id or "Leda" in voice_id or "Zephyr" in voice_id:
            gender = texttospeech.SsmlVoiceGender.FEMALE

        input_text = texttospeech.SynthesisInput(text=cleaned_text)

        voice = texttospeech.VoiceSelectionParams(
            language_code="ru-RU",
            name=voice_id,
            ssml_gender=gender
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            pitch=pitch_val,
            speaking_rate=rate_val
        )

        client = cls._get_client()
        try:
            response = await client.synthesize_speech(
                request={
                    "input": input_text,
                    "voice": voice,
                    "audio_config": audio_config
                }
            )
            logger.info(f"Synthesized {len(response.audio_content)} bytes of OGG_OPUS audio with voice {voice_id}")
            return response.audio_content
        except Exception as e:
            logger.error(f"Failed to synthesize speech: {e}")
            raise
