"""
Context Manager — handles enter/exit logic for character conversations.
Sits on top of state_manager for higher-level bubble operations.
"""

from services import state_manager


def enter_character(session_id: str, character_id: str, global_step: int) -> dict:
    """
    Called when user clicks a character. Increments visit_count,
    calculates steps_away if returning. Returns bubble context for agents.
    """
    bubble = state_manager.get_bubble(session_id, character_id)
    if not bubble:
        return None

    first_visit = bubble["visit_count"] == 0
    steps_away = None
    if not first_visit and bubble["last_seen_step"] is not None:
        steps_away = global_step - bubble["last_seen_step"]

    state_manager.update_bubble(
        session_id, character_id,
        visit_count=bubble["visit_count"] + 1,
    )

    return {
        "first_visit": first_visit,
        "visit_count": bubble["visit_count"] + 1,
        "steps_away": steps_away,
        "suspicion": bubble["suspicion"],
        "mood": bubble["mood"],
        "history": bubble["history"],
        "secret_extracted": bubble["secret_extracted"],
        "initiative_fired": bubble["initiative_fired"],
    }


def exit_character(session_id: str, character_id: str, global_step: int) -> None:
    """
    Called when user leaves a character. Stamps last_seen_step.
    Suspicion/mood/history are already persisted per turn.
    """
    state_manager.update_bubble(
        session_id, character_id,
        last_seen_step=global_step,
    )
