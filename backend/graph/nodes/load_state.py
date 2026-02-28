"""
load_state node — first node in the graph.
Loads game session + character bubble from DB.
Handles character switching for clicks vs message validation.
"""

from graph.state import GameGraphState
from services import state_manager, context_manager


def load_state(state: GameGraphState) -> dict:
    session_id = state["session_id"]
    character_id = state["character_id"]
    user_message = state.get("user_message")

    # Load game session
    game = state_manager.get_game(session_id)
    if not game:
        return {"error": f"No game found for session {session_id}"}

    result = {
        "global_step": game["global_step"],
        "max_steps": game["max_steps"],
        "game_status": game["game_status"],
        "secrets_found": game["secrets_found"],
        "active_character": game["active_character"],
        "error": None,
        "game_over": game["game_status"] != "active",
        "loss_reason": game.get("loss_reason"),
    }

    if user_message is None:
        # ── CLICK MODE: user clicked a character ──
        # Auto-exit previous character if switching
        old_char = game["active_character"]
        if old_char and old_char != character_id:
            context_manager.exit_character(session_id, old_char, game["global_step"])

        # Enter the new character
        ctx = context_manager.enter_character(session_id, character_id, game["global_step"])
        if not ctx:
            return {**result, "error": f"Unknown character: {character_id}"}

        # Set as active
        state_manager.update_game(session_id, active_character=character_id)

        result.update({
            "active_character": character_id,
            "suspicion": ctx["suspicion"],
            "mood": ctx["mood"],
            "history": ctx["history"],
            "secret_extracted": ctx["secret_extracted"],
            "visit_count": ctx["visit_count"],
            "first_visit": ctx["first_visit"],
            "steps_away": ctx["steps_away"],
        })

    else:
        # ── MESSAGE MODE: user sent a message ──
        if game["active_character"] != character_id:
            return {**result, "error": "Not talking to this character. Call /talk first."}

        # Increment step
        new_step = state_manager.increment_step(session_id)
        result["global_step"] = new_step

        # Load bubble
        bubble = state_manager.get_bubble(session_id, character_id)
        if not bubble:
            return {**result, "error": f"No bubble found for {character_id}"}

        result.update({
            "suspicion": bubble["suspicion"],
            "mood": bubble["mood"],
            "prev_mood": bubble.get("prev_mood"),
            "history": bubble["history"],
            "secret_extracted": bubble["secret_extracted"],
            "visit_count": bubble["visit_count"],
            "first_visit": False,
            "steps_away": None,
        })

    return result
