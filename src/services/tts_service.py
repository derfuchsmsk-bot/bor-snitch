import re
import logging
import httpx
from google.cloud import texttospeech_v1 as texttospeech
from src.utils.config import settings
from src.utils.game_config import config

logger = logging.getLogger(__name__)

class TTSService:
    _google_client = None

    @classmethod
    def _get_google_client(cls):
        if cls._google_client is None:
            cls._google_client = texttospeech.TextToSpeechAsyncClient()
        return cls._google_client

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
    async def synthesize_elevenlabs(
        cls,
        text: str,
        voice_id: str = None,
        api_key: str = None
    ) -> bytes:
        """
        Synthesizes spoken audio from text using ElevenLabs API (eleven_multilingual_v2).
        Outputs high quality MP3 audio.
        """
        key = api_key or settings.ELEVENLABS_API_KEY
        if not key:
            raise ValueError("ELEVENLABS_API_KEY is not configured")

        v_id = voice_id or getattr(config, "ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
        model = getattr(config, "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        stability = getattr(config, "ELEVENLABS_STABILITY", 0.45)
        similarity = getattr(config, "ELEVENLABS_SIMILARITY_BOOST", 0.85)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}?output_format=mp3_44100_128"
        headers = {
            "xi-api-key": key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
                "style": 0.25,
                "use_speaker_boost": True
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 402 and v_id != "pNInz6obpgDQGcFmaJgB":
                logger.warning(f"Voice {v_id} requires paid ElevenLabs plan (HTTP 402). Retrying with standard ElevenLabs Adam voice...")
                fallback_url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB?output_format=mp3_44100_128"
                resp = await client.post(fallback_url, headers=headers, json=payload)

            if resp.status_code != 200:
                err = resp.text
                logger.error(f"ElevenLabs API error ({resp.status_code}): {err}")
                raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {err}")
            logger.info(f"Synthesized {len(resp.content)} bytes of MP3 audio via ElevenLabs")
            return resp.content

    @classmethod
    async def synthesize_google_tts(
        cls,
        text: str,
        voice_name: str = None,
        pitch: float = None,
        speaking_rate: float = None
    ) -> bytes:
        """
        Synthesizes spoken audio from text in OGG_OPUS format using Google Cloud Text-to-Speech.
        """
        voice_id = voice_name or getattr(config, "VOICE_DIGEST_VOICE", "ru-RU-Wavenet-D")
        pitch_val = pitch if pitch is not None else getattr(config, "VOICE_DIGEST_PITCH", -1.5)
        rate_val = speaking_rate if speaking_rate is not None else getattr(config, "VOICE_DIGEST_SPEED", 1.05)

        # Detect gender from voice name
        gender = texttospeech.SsmlVoiceGender.MALE
        if voice_id.endswith("-A") or voice_id.endswith("-C") or voice_id.endswith("-E") or "Aoede" in voice_id or "Kore" in voice_id or "Leda" in voice_id or "Zephyr" in voice_id:
            gender = texttospeech.SsmlVoiceGender.FEMALE

        input_text = texttospeech.SynthesisInput(text=text)

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

        client = cls._get_google_client()
        response = await client.synthesize_speech(
            request={
                "input": input_text,
                "voice": voice,
                "audio_config": audio_config
            }
        )
        logger.info(f"Synthesized {len(response.audio_content)} bytes of OGG_OPUS audio via Google TTS (voice: {voice_id})")
        return response.audio_content

    @classmethod
    async def synthesize_speech(
        cls,
        text: str,
        preferred_provider: str = None
    ) -> tuple[bytes, str]:
        """
        Synthesizes speech using the configured provider (ElevenLabs or Google TTS).
        Returns a tuple of (audio_bytes, format_extension) e.g. (bytes, 'mp3') or (bytes, 'ogg').
        Automatically falls back to Google TTS if ElevenLabs fails or lacks API key.
        """
        cleaned_text = cls.clean_text_for_speech(text)
        if not cleaned_text:
            raise ValueError("Empty text for speech synthesis")

        provider = preferred_provider or getattr(config, "TTS_PROVIDER", "elevenlabs").lower()

        if provider == "elevenlabs":
            if settings.ELEVENLABS_API_KEY:
                try:
                    audio_bytes = await cls.synthesize_elevenlabs(cleaned_text)
                    return audio_bytes, "mp3"
                except Exception as e:
                    logger.warning(f"ElevenLabs synthesis failed: {e}. Falling back to Google Cloud TTS.")
            else:
                logger.info("ELEVENLABS_API_KEY is not configured. Falling back to Google Cloud TTS.")

        # Fallback to Google Cloud TTS
        audio_bytes = await cls.synthesize_google_tts(cleaned_text)
        return audio_bytes, "ogg"

    @classmethod
    async def synthesize_voice_ogg(
        cls,
        text: str,
        voice_name: str = None,
        pitch: float = None,
        speaking_rate: float = None
    ) -> bytes:
        """Backwards compatibility alias returning raw audio bytes."""
        audio_bytes, _ = await cls.synthesize_speech(text)
        return audio_bytes
