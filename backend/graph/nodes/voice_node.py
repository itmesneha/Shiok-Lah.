"""
voice_node — pre-generates ElevenLabs TTS audio for the character response.
Runs after character_node, in parallel with the suspicion evaluation chain,
so TTS generation overlaps with game logic rather than following it.
"""

import logging
from graph.state import GameGraphState
from models.npcs import get_npc
from routes.voice import tts_stream_chunks, ELEVENLABS_API_KEY

log = logging.getLogger("shiok.voice")


async def voice_node(state: GameGraphState) -> dict:
    text = state.get("character_response", "")
    if not text:
        return {"audio_bytes": None}

    character_id = state["character_id"]
    mood = state.get("mood", "neutral")

    try:
        npc = get_npc(character_id)
        voice_id = npc.get("voice_id", "")
        if not voice_id or not ELEVENLABS_API_KEY:
            return {"audio_bytes": None}

        chunks = []
        async for chunk in tts_stream_chunks(voice_id, text, mood):
            chunks.append(chunk)

        audio = b"".join(chunks)
        log.info("[VOICE] %s | %d bytes", character_id, len(audio))
        return {"audio_bytes": audio}

    except Exception as e:
        log.warning("[VOICE] TTS failed (%s): %s", character_id, e)
        return {"audio_bytes": None}
