# backend/config.py
"""
Configuration for Shiok Lah! backend.

This module contains all tunable parameters for the game,
including LLM settings, suspicion thresholds, game parameters,
and timeout values.
"""


class LLM:
    """LLM configuration settings."""
    # Model names
    CHARACTER_MODEL = "mistral-medium-latest"  # dialogue generation
    SUSPICION_MODEL = "mistral-small-latest"  # intent evaluation
    WIN_CHECK_MODEL = "mistral-small-latest"  # secret detection
    
    # Temperature settings
    CHARACTER_TEMP = 0.7
    SUSPICION_TEMP = 0.1  # low for consistent JSON output
    WIN_CHECK_TEMP = 0.1
    
    # Token limits
    CHARACTER_TOKENS = 120  # max tokens per NPC response
    SUSPICION_TOKENS = 80
    WIN_CHECK_TOKENS = 100
    
    # History context
    SUSPICION_HISTORY = 5  # last N turns fed to suspicion evaluator


class SUSPICION:
    """Suspicion system configuration."""
    DELTA_MAX = 20  # max LLM-returned delta value
    DELTA_SCALE = 100.0  # delta / scale = suspicion change


class MOOD:
    """Mood threshold configuration."""
    WARM_MAX = 0.20
    NEUTRAL_MAX = 0.45
    SUSPICIOUS_MAX = 0.85
    IMPRESSED_CAP = 0.40  # suspicion must be below this for "impressed"


class GAME:
    """Game mechanics configuration."""
    MAX_STEPS = 30  # total turns per game
    GAME_OVER_SUSPICION = 0.95  # suspicion threshold for game over
    WIN_MAX_SUSPICION = 0.50  # max suspicion to allow win
    WIN_MIN_TURNS = 3  # minimum visits before win eligible
    WIN_CONFIDENCE = 0.40  # minimum LLM confidence to count as extracted


class TIMEOUTS:
    """API timeout configuration (in seconds)."""
    MESSAGE = 300  # SSE stream timeout
    TALK = 300
    DEFAULT = 10


class API:
    """API configuration."""
    MISTRAL_API_KEY = ""  # Will be loaded from environment or passed directly
    ELEVENLABS_API_KEY = ""  # For voice synthesis
    DB_PATH = "shiok_lah.db"  # SQLite database path
    