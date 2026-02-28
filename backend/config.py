# backend/config.py
"""
Configuration for Shiok Lah! backend.

This module contains LLM configuration settings.
"""


class LLM:
    """LLM configuration settings."""
    # Model names
    CHARACTER_MODEL = "mistral-tiny"  # dialogue generation
    SUSPICION_MODEL = "mistral-tiny"  # intent evaluation
    WIN_CHECK_MODEL = "mistral-tiny"  # secret detection
    
    # Temperature settings
    CHARACTER_TEMP = 0.7
    SUSPICION_TEMP = 0.1  # low for consistent JSON output
    WIN_CHECK_TEMP = 0.1
    
    # Token limits
    CHARACTER_TOKENS = 100  # max tokens per NPC response
    SUSPICION_TOKENS = 80
    WIN_CHECK_TOKENS = 100
    