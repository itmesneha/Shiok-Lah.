# backend/graph/nodes/preflight.py
"""
Preflight checks: terminal conditions and validation.
"""

from ...config import GAME
from ..state import GameGraphState


def preflight_node(state: GameGraphState) -> GameGraphState:
    """
    Check for terminal conditions and validate state.
    
    Args:
        state: Current game state
        
    Returns:
        State with game_over flag set if terminal condition met
    """
    # Check if game is already over
    if state["game_status"] in ["won", "lost"]:
        return {
            **state,
            "game_over": True,
            "error": "Game already completed"
        }
    
    # Check step limit
    if state["global_step"] >= state["max_steps"]:
        return {
            **state,
            "game_over": True,
            "loss_reason": "max_steps",
            "game_status": "lost"
        }
    
    # Check suspicion threshold
    if state["suspicion"] >= GAME.GAME_OVER_SUSPICION:
        return {
            **state,
            "game_over": True,
            "loss_reason": "suspicion",
            "game_status": "lost"
        }
    
    # If character already extracted secret, force leave
    if state.get("secret_extracted", False):
        return {
            **state,
            "game_over": True,
            "force_leave": True
        }
    
    # Continue normally
    return {
        **state,
        "game_over": False
    }
