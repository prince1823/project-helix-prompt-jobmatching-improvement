import os
import base64
import requests
from datetime import datetime

from my_logger import logger
from models import LanguageEnum
from exceptions import MyException, ErrorMessages


class AudioService:
    def __init__(self):
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY")
        if not self.sarvam_api_key:
            raise ValueError("SARVAM_API_KEY environment variable is not set.")

    def sarvam_translate(self, byte_data: bytes) -> dict | None:
        """
        Transcribes audio content to text using the Sarvam API.
        :param byte_data: The audio content in bytes format.
        :return: Dictionary with the transcription result.
        """
        try:
            logger.info(
                f"[sarvam_translate] Transcribing audio content for byte_data: {byte_data}"
            )
            audio_bytes = base64.b64decode(byte_data)
            response = requests.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={
                    "api-subscription-key": os.getenv("SARVAM_API_KEY"),
                },
                files={
                    "file": ("audio.ogg", audio_bytes, "audio/wav"),
                },
            )
            if response.status_code == 200:
                response_data = response.json()
                return response_data
        except Exception as e:
            logger.error(f"[sarvam_translate] Error during audio transcription: {e}")
            raise MyException(
                block="sarvam_translate",
                error_code=ErrorMessages.AUDIO_TRANSLATION_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def sarvam_tts(self, message: str, locale: LanguageEnum) -> dict | None:
        """
        Converts text to speech using the Sarvam API.
        :param event: Dictionary containing 'content'
        :param locale: The target language code for the audio generation.
        :return: Dictionary with the audio generation result.
        """
        try:
            logger.info(
                f"[sarvam_tts] Generating audio for message: {message} in locale: {locale}"
            )
            response = requests.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": os.getenv("SARVAM_API_KEY"),
                },
                json={"text": message, "target_language_code": locale},
            )
            if response.status_code == 200:
                response_data = response.json()
                return response_data
        except Exception as e:
            logger.error(f"[sarvam_tts] Error during audio generation: {e}")
            raise MyException(
                block="sarvam_tts",
                error_code=ErrorMessages.AUDIO_SPEECH_GENERATION_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )


audio_service = AudioService()
