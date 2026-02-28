"""
Shared state that flows through every node in the Conversation Graph.
"""

from typing import TypedDict


class GameGraphState(TypedDict, total=False):
    # ── Inputs (set before graph runs) ──
    session_id: str
    character_id: str
    user_message: str | None          # None = click (opener), str = message

    # ── Game state (loaded from DB by load_state) ──
    global_step: int
    max_steps: int
    game_status: str                  # "active" | "won" | "lost"
    secrets_found: list[str]
    active_character: str | None

    # ── Character bubble (loaded from DB) ──
    suspicion: float
    mood: str
    prev_mood: str | None           # mood at start of turn, before apply_suspicion ran
    history: list[dict]
    secret_extracted: bool
    visit_count: int
    first_visit: bool
    steps_away: int | None

    # ── Agent outputs (written by nodes) ──
    character_response: str | None
    suspicion_delta: float
    suspicion_reason: str
    intent_category: str
    win_detected: bool
    audio_bytes: bytes | None         # pre-generated TTS audio, set by voice_node

    # ── Control flow ──
    error: str | None
    game_over: bool
    loss_reason: str | None
