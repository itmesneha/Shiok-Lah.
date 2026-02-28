"""
persist node — final node. Saves everything to SQLite.
Handles both opener mode (click) and message mode.
"""

from graph.state import GameGraphState
from services import state_manager


def persist(state: GameGraphState) -> dict:
    session_id = state["session_id"]
    character_id = state["character_id"]
    user_message = state.get("user_message")
    character_response = state.get("character_response")

    if user_message is None:
        # ── OPENER MODE (click) ──
        if character_response:
            state_manager.append_to_history(session_id, character_id, "assistant", character_response)
            state_manager.update_bubble(session_id, character_id, initiative_fired=True)
        state_manager.update_game(session_id, active_character=character_id)

    else:
        # ── MESSAGE MODE ──
        # Save user message
        state_manager.append_to_history(session_id, character_id, "user", user_message)

        # Save character response
        if character_response:
            state_manager.append_to_history(session_id, character_id, "assistant", character_response)

        # Update bubble state
        # prev_mood = what mood was loaded at the start of this turn (pre-apply_suspicion)
        # mood     = new mood derived by apply_suspicion
        state_manager.update_bubble(
            session_id, character_id,
            suspicion=state.get("suspicion", 0.0),
            mood=state.get("mood", "neutral"),
            prev_mood=state.get("prev_mood"),
        )

        # Update game state if terminal
        game_updates = {}
        if state.get("game_over"):
            game_updates["game_status"] = state.get("game_status", "lost")
            game_updates["loss_reason"] = state.get("loss_reason")
        if state.get("secrets_found"):
            game_updates["secrets_found"] = state["secrets_found"]

        # If a secret was extracted this turn:
        #   - mark the bubble so the character is deactivated on the map
        #   - clear active_character so the backend drives conversation close
        if state.get("win_detected"):
            state_manager.update_bubble(session_id, character_id, secret_extracted=True)
            game_updates["active_character"] = None

        if game_updates or state.get("win_detected"):
            state_manager.update_game(session_id, **game_updates)

    return {}
