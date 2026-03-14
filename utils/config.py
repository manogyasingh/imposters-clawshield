"""
Centralized configuration for ClawShield.

Loads all runtime settings from environment variables (via .env).
This is the single source of truth for API keys and model selection.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "")
OPENROUTER_VISION_MODEL = os.environ.get(
    "OPENROUTER_VISION_MODEL", OPENROUTER_MODEL
)
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
