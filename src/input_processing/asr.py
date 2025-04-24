import logging
import sys
import os
import subprocess
from google.cloud import speech
from src.utils.helpers import LANGUAGE_MAP


class UnicodeSafeStreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__(stream=sys.stdout)
        if sys.stdout.encoding.lower() != "utf-8":
            self.stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        UnicodeSafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")


def convert_oga_to_wav(input_path: str, output_path: str) -> bool:
    """
    Convert .oga file to WAV using FFmpeg.
    Args:
        input_path: Path to .oga file
        output_path: Path to output WAV file
    Returns:
        True if successful, False otherwise
    """
    ffmpeg_path = r"C:\ffmpeg-2025-03-27-git-114fccc4a5-essentials_build\bin\ffmpeg.exe"
    if not os.path.exists(ffmpeg_path):
        logger.error(f"FFmpeg not found at: {ffmpeg_path}")
        return False
    try:
        subprocess.run(
            [ffmpeg_path, "-i", input_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", output_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Converted {input_path} to {output_path}")
        return True
    except Exception as e:
        logger.error(f"FFmpeg conversion error: {str(e)}", exc_info=True)
        return False


def transcribe_audio(file_path: str, lang: str) -> str:
    """
    Transcribe audio file to text using Google Speech-to-Text API.
    Args:
        file_path: Path to the audio file (.oga)
        lang: Language code (e.g., 'ml')
    Returns:
        Transcribed text
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return ""

        # Convert .oga to WAV
        wav_path = file_path.replace(".oga", ".wav")
        if not convert_oga_to_wav(file_path, wav_path):
            logger.error(f"Failed to convert {file_path} to WAV")
            return ""

        # Initialize Google Speech-to-Text client
        client = speech.SpeechClient()
        speech_code = LANGUAGE_MAP.get(lang, {"speech_code": "en-IN"})["speech_code"]
        logger.info(f"Transcribing audio with language code: {speech_code}")

        # Read WAV file
        with open(wav_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=speech_code,
            enable_automatic_punctuation=True
        )

        # Transcribe
        response = client.recognize(config=config, audio=audio)
        transcribed_text = "".join(result.alternatives[0].transcript for result in response.results).strip()

        if not transcribed_text:
            logger.warning(f"Empty transcription for audio: {file_path}")
            return ""

        logger.info(f"Transcribed audio to: {transcribed_text[:50]}...")
        return transcribed_text

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}", exc_info=True)
        return ""
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)