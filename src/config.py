# src/config.py
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

IDINCODE_API = os.getenv("IDINCODE_API", "").strip()

KIE_AI_BASE_URL = os.getenv("KIE_AI_BASE_URL", "https://api.kie.ai").strip()
KIE_AI_MESSAGES_PATH = os.getenv("KIE_AI_MESSAGES_PATH", "/api/v1/claude/messages").strip()
KIE_AI_MODEL = os.getenv("KIE_AI_MODEL", "claude-sonnet-4-20250514").strip()

_raw_thinking = os.getenv("KIE_AI_THINKING", "false").strip().lower()
KIE_AI_THINKING = _raw_thinking in {"1", "true", "yes", "on"}

NICHE_CONFIG_DIR = Path(
    os.getenv("NICHE_CONFIG_DIR", str(ROOT_DIR / "src" / "config" / "niches"))
)
DEFAULT_NICHE_CONFIG = os.getenv("DEFAULT_NICHE_CONFIG", "default").strip() or "default"
