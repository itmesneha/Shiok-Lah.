"""
apply_suspicion node — deterministic.
Applies suspicion delta, derives mood, checks game-over threshold.
"""

from graph.state import GameGraphState
from services.mood_engine import derive_mood, is_game_over_suspicion


def apply_suspicion(state: GameGraphState) -> dict:
    current = state.get("suspicion", 0.0)
    delta = state.get("suspicion_delta", 0.0)

    new_suspicion = max(0.0, min(1.0, current + delta))
    intent = state.get("intent_category", "casual")
    new_mood = derive_mood(new_suspicion, intent, delta)

    result = {
        "suspicion": new_suspicion,
        "mood": new_mood,
    }

    if is_game_over_suspicion(new_suspicion):
        result["game_over"] = True
        result["game_status"] = "lost"
        result["loss_reason"] = "suspicion"

    return result
