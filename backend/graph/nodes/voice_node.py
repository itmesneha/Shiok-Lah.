# backend/graph/nodes/voice_node.py
"""
Voice generation node using ElevenLabs TTS.
"""

import os
import requests
import base64
from ...config import API
from ..state import GameGraphState


def voice_node(state: GameGraphState) -> GameGraphState:
    """
    Generate TTS audio for character response using ElevenLabs.
    
    Args:
        state: Current game state
        
    Returns:
        State with audio_bytes populated (or None if voice disabled)"""
    
    # Check if voice is enabled and we have required data
    if not state.get("character_response"):
        return {
            **state,
            "audio_bytes": None,
            "voice_error": "No character response to synthesize"
        }
    
    voice_id = state.get("voice_id")
    if not voice_id:
        return {
            **state,
            "audio_bytes": None,
            "voice_error": "No voice ID configured for character"
        }
    
    if not API.ELEVENLABS_API_KEY:
        return {
            **state,
            "audio_bytes": None,
            "voice_error": "ElevenLabs API key not configured"
        }
    
    try:
        # ElevenLabs TTS API call
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": API.ELEVENLABS_API_KEY
        }
        data = {
            "text": state["character_response"],
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        # Return audio bytes
        return {
            **state,
            "audio_bytes": response.content,
            "voice_error": None
        }
        
    except requests.exceptions.RequestException as e:
        return {
            **state,
            "audio_bytes": None,
            "voice_error": f"ElevenLabs API error: {str(e)}"
        }
    except Exception as e:
        return {
            **state,
            "audio_bytes": None,
            "voice_error": f"Voice generation error: {str(e)}"
        }
