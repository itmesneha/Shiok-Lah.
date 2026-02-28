"""
Game routes — uses LangGraph conversation graph for talk + message flows.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import base64
import logging

log = logging.getLogger("shiok.game")

from models.schemas import (
    StartGameRequest, StartGameResponse,
    TalkRequest, TalkResponse,
    MessageRequest, LeaveRequest, GameStateResponse,
)
from models.npcs import NPCS
from services import state_manager, context_manager
from graph.conversation_graph import compile_conversation_graph
router = APIRouter()

DRIP_DELAY = 0.08   # seconds per word
AUDIO_CHUNK = 4096  # bytes per [AUDIO] SSE event


def sse(data: str) -> str:
    return f"data: {data}\n\n"


graph = compile_conversation_graph()


async def _stream_pregenerated(text: str, audio_bytes: bytes | None, voice_enabled: bool):
    """Sends all PCM audio chunks first, signals [AUDIO_DONE], then drips text word-by-word.
    Godot starts AudioStreamGenerator playback on [AUDIO_DONE] so audio and
    typewriter text run simultaneously.
    """
    if voice_enabled and audio_bytes:
        for i in range(0, len(audio_bytes), AUDIO_CHUNK):
            b64 = base64.b64encode(audio_bytes[i:i + AUDIO_CHUNK]).decode()
            yield sse(f"[AUDIO] {b64}")
            await asyncio.sleep(0)  # yield between chunks so the event loop stays responsive
        yield sse("[AUDIO_DONE]")

    for word in text.split():
        yield sse(word + " ")
        await asyncio.sleep(DRIP_DELAY)


@router.post("/start", response_model=StartGameResponse)
async def start_game(req: StartGameRequest):
    """Create a new game session with 3 character bubbles."""
    game = state_manager.create_game(req.session_id)
    characters = [
        {"character_id": cid, "name": npc["name"], "stall": npc["stall"], "location": npc["location"]}
        for cid, npc in NPCS.items()
    ]
    return StartGameResponse(
        session_id=game["session_id"],
        game_status=game["game_status"],
        characters=characters,
        max_steps=game["max_steps"],
    )


@router.post("/talk", response_model=TalkResponse)
async def talk(req: TalkRequest):
    """User clicked a character. Graph runs with user_message=None."""
    result = await graph.ainvoke({
        "session_id": req.session_id,
        "character_id": req.character_id,
        "user_message": None,
    })

    npc = NPCS.get(req.character_id, {})
    return TalkResponse(
        character_name=npc.get("name", req.character_id),
        dialogue=result.get("error") or result.get("character_response"),
        mood=result.get("mood", "neutral"),
        suspicion=result.get("suspicion", 0.0),
        visit_count=result.get("visit_count", 0),
        first_visit=result.get("first_visit", True),
        game_status=result.get("game_status", "active"),
    )


@router.post("/message")
async def message(req: MessageRequest):
    """User sent a message. SSE streaming via graph.astream_events()."""

    async def stream():
        try:
            final_state = None

            # Wait for the full graph response — no mid-run token streaming
            async for event in graph.astream_events(
                {
                    "session_id": req.session_id,
                    "character_id": req.character_id,
                    "user_message": req.message,
                },
                version="v2",
            ):
                if event["event"] == "on_chain_end" and event.get("name") == "LangGraph":
                    final_state = event["data"].get("output", {})

            if final_state:
                text = final_state.get("character_response", "")

                if text:
                    audio_bytes = final_state.get("audio_bytes")
                    async for chunk in _stream_pregenerated(text, audio_bytes, req.voice_enabled):
                        yield chunk

                state_payload = {
                    "suspicion":        final_state.get("suspicion", 0.0),
                    "suspicion_delta":  final_state.get("suspicion_delta", 0.0),
                    "suspicion_reason": final_state.get("suspicion_reason", ""),
                    "intent_category":  final_state.get("intent_category", "casual"),
                    "mood":             final_state.get("mood", "neutral"),
                    "prev_mood":        final_state.get("prev_mood"),
                    "steps_remaining":  final_state.get("max_steps", 30) - final_state.get("global_step", 0),
                    "game_status":      final_state.get("game_status", "active"),
                    "game_over":        final_state.get("game_over", False),
                    "loss_reason":      final_state.get("loss_reason"),
                    "secrets_found":    len(final_state.get("secrets_found", [])),
                    "win_detected":     final_state.get("win_detected", False),
                    "force_leave":      final_state.get("win_detected", False),
                }
                yield sse(f"[STATE] {json.dumps(state_payload)}")

            yield sse("[DONE]")

        except Exception as e:
            yield sse(f"[ERROR] {e}")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/leave")
async def leave(req: LeaveRequest):
    """User clicked away from character. Snapshot bubble."""
    game = state_manager.get_game(req.session_id)
    if game:
        context_manager.exit_character(req.session_id, req.character_id, game["global_step"])
        state_manager.update_game(req.session_id, active_character=None)
    return {"saved": True}


@router.get("/state/{session_id}", response_model=GameStateResponse)
async def get_state(session_id: str):
    """Return full game state (no secrets)."""
    game = state_manager.get_game(session_id)
    if not game:
        return {"error": "Game not found"}

    characters = []
    for char_id in NPCS:
        bubble = state_manager.get_bubble(session_id, char_id)
        if bubble:
            characters.append({
                "character_id": char_id,
                "name": NPCS[char_id]["name"],
                "suspicion": bubble["suspicion"],
                "mood": bubble["mood"],
                "visit_count": bubble["visit_count"],
                "secret_extracted": bubble["secret_extracted"],
                "history_length": len(bubble["history"]),
            })

    return GameStateResponse(
        session_id=session_id,
        global_step=game["global_step"],
        max_steps=game["max_steps"],
        game_status=game["game_status"],
        secrets_found=len(game["secrets_found"]),
        characters=characters,
    )


@router.post("/reset")
async def reset(req: StartGameRequest):
    """Reset a game session."""
    state_manager.reset_game(req.session_id)
    return {"reset": True, "session_id": req.session_id}
