"""
preflight node — checks terminal conditions before running agents.
"""

from graph.state import GameGraphState


def preflight(state: GameGraphState) -> dict:
    # Already hit an error in load_state
    if state.get("error"):
        return {}

    # Game already over
    if state.get("game_status") != "active":
        return {"error": "Game is already over.", "game_over": True}

    # Only check step limit for messages (not clicks)
    if state.get("user_message") is not None:
        if state["global_step"] > state["max_steps"]:
            return {
                "game_over": True,
                "game_status": "lost",
                "loss_reason": "max_steps",
            }

    return {}
