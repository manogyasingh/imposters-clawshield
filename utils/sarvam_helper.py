"""
Sarvam AI API Helper for Speech-to-Text and Text-to-Speech

Uses Sarvam AI's Saarika model for STT and Bulbul model for TTS.
"""

import tempfile
import os
from sarvamai import SarvamAI


def get_sarvam_client(api_key: str) -> SarvamAI:
    """Initialize and return a Sarvam AI client."""
    return SarvamAI(api_subscription_key=api_key)


def speak_text(text: str, api_key: str, language: str = "en-IN", speaker: str = "anushka") -> bytes:
    """
    Convert text to speech using Sarvam TTS (Bulbul model).
    
    Args:
        text: The text to convert to speech
        api_key: Sarvam AI API key
        language: Target language code (e.g., 'en-IN', 'hi-IN')
        speaker: Voice to use (meera, pavithra, maitreyi, arvind, karthik)
    
    Returns:
        Audio data as bytes (WAV format)
    """
    client = get_sarvam_client(api_key)
    
    response = client.text_to_speech.convert(
        text=text,
        target_language_code=language,
        speaker=speaker,
        enable_preprocessing=True,
    )
    
    # The response contains audio data that can be saved
    # We need to save it temporarily and read back as bytes
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        from sarvamai.play import save
        save(response, tmp.name)
        tmp_path = tmp.name
    
    with open(tmp_path, "rb") as f:
        audio_bytes = f.read()
    
    os.unlink(tmp_path)
    return audio_bytes


def transcribe_audio(audio_path: str, api_key: str, language: str = "en-IN") -> str:
    """
    Convert speech to text using Sarvam STT (Saarika model).
    
    Args:
        audio_path: Path to the audio file (WAV or MP3)
        api_key: Sarvam AI API key
        language: Language code for transcription (e.g., 'en-IN', 'hi-IN', 'unknown' for auto-detect)
    
    Returns:
        Transcribed text string
    """
    client = get_sarvam_client(api_key)
    
    with open(audio_path, "rb") as audio_file:
        response = client.speech_to_text.transcribe(
            file=audio_file,
            model="saarika:v2.5",
            language_code=language
        )
    
    # Extract transcript from response
    if hasattr(response, 'transcript'):
        return response.transcript
    elif isinstance(response, dict):
        return response.get('transcript', '')
    else:
        return str(response)


def transcribe_audio_bytes(audio_bytes: bytes, api_key: str, language: str = "hi-IN") -> str:
    """
    Convert speech to text from audio bytes.
    
    Args:
        audio_bytes: Audio data as bytes
        api_key: Sarvam AI API key
        language: Language code for transcription (default: hi-IN for Hindi)
    
    Returns:
        Transcribed text string
    """
    # Save bytes to temp file for API
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    
    try:
        result = transcribe_audio(tmp_path, api_key, language)
    finally:
        os.unlink(tmp_path)
    
    return result


def clean_transcribed_value(
    raw_text: str,
    field_label: str,
    api_base: str = None,
    api_key: str = None,
    model: str = None,
) -> str:
    """
    Clean and format the transcribed text based on the field label using an LLM.
    
    Args:
        raw_text: Raw transcribed text (may be in Hindi or mixed language)
        field_label: The form field label (e.g., "Date of Birth", "Phone Number")
        api_base: Override for API base URL (defaults to env config)
        api_key: Override for API key (defaults to env config)
        model: Override for model (defaults to env config)
    
    Returns:
        Cleaned and formatted value in English
    """
    from openai import OpenAI
    from utils.config import OPENROUTER_API_BASE, OPENROUTER_API_KEY, OPENROUTER_MODEL

    api_base = api_base or OPENROUTER_API_BASE
    api_key = api_key or OPENROUTER_API_KEY
    model = model or OPENROUTER_MODEL

    if not api_key or not raw_text.strip():
        return raw_text

    client = OpenAI(base_url=api_base, api_key=api_key)
    
    prompt = f"""You are a form-filling assistant. Clean and format the following spoken/transcribed input for a form field.

Field Label: {field_label}
Raw Input (may be in Hindi, English, or mixed): {raw_text}

Instructions:
1. Translate to English if needed
2. Format appropriately based on the field type:
   - Names: Capitalize properly (e.g., "John Doe")
   - Dates: Use DD/MM/YYYY format
   - Phone numbers: Remove spaces, keep only digits with country code if given
   - Addresses: Proper capitalization, remove filler words
   - Numbers: Convert words to digits (e.g., "twenty three" → "23")
   - Email: lowercase, ensure valid format
3. Remove filler words like "um", "uh", "so", etc.
4. Return ONLY the cleaned value, nothing else. No explanations.

Cleaned Value:"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.1
        )
        cleaned = response.choices[0].message.content.strip()
        # Remove any quotes that might be added
        cleaned = cleaned.strip('"\'')
        return cleaned
    except Exception as e:
        print(f"Error cleaning text: {e}")
        return raw_text
