from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
OUTPUT_DIR = str(ROOT_DIR / "output")

IDINCODE_API = os.getenv("IDINCODE_API", "").strip()

KIE_AI_BASE_URL = os.getenv("KIE_AI_BASE_URL", "https://api.kie.ai").strip()
KIE_AI_MESSAGES_PATH = os.getenv("KIE_AI_MESSAGES_PATH", "/api/v1/claude/messages").strip()
KIE_AI_MODEL = os.getenv("KIE_AI_MODEL", "claude-sonnet-4-20250514").strip()

_raw_thinking = os.getenv("KIE_AI_THINKING", "false").strip().lower()
KIE_AI_THINKING = _raw_thinking in {"1", "true", "yes", "on"}

PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "").strip()

NICHE_CONFIG_DIR = Path(
    os.getenv("NICHE_CONFIG_DIR", str(SRC_DIR / "config" / "niches"))
)
DEFAULT_NICHE_CONFIG = os.getenv("DEFAULT_NICHE_CONFIG", "default").strip() or "default"

TIER_CONFIGS: list[dict[str, object]] = [
    {
        "label": "Starter",
        "filename": "leads_starter.csv",
        "min_score": 0.30,
        "limit": 1000,
    },
    {
        "label": "Pro",
        "filename": "leads_pro.csv",
        "min_score": 0.50,
        "limit": 250,
    },
    {
        "label": "Premium Gold",
        "filename": "leads_premium_gold.csv",
        "min_score": 0.70,
        "limit": 100,
    },
]

DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
NICHE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
