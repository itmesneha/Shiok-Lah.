# backend/graph/nodes/load_state.py
"""
Load game state from database into graph state.
"""

from typing import Dict, Any
from ...services.state_manager import get_game, get_bubble
from ...models.npcs import get_npc
from ..state import GameGraphState


def load_state_node(state: GameGraphState) -> GameGraphState:
    """
    Load game and character state from database.
    
    Args:
        state: Input state with session_id and character_id
        
    Returns:
        State with loaded game data and character bubble
    """
    session_id = state["session_id"]
    character_id = state["character_id"]
    
    # Load game session
    game_data = get_game(session_id)
    
    # Load character bubble
    bubble_data = get_bubble(session_id, character_id)
    
    # Get NPC definition
    npc = get_npc(character_id)
    
    # Calculate derived fields
    first_visit = bubble_data.get("visit_count", 0) == 0
    steps_away = None
    if bubble_data.get("last_seen_step"):
        steps_away = game_data["global_step"] - bubble_data["last_seen_step"]
    
    # Build updated state
    updated_state = {
        **state,
        # Game state
        "global_step": game_data["global_step"],
        "max_steps": game_data["max_steps"],
        "game_status": game_data["game_status"],
        "secrets_found": game_data["secrets_found"],
        "active_character": game_data["active_character"],
        
        # Character bubble state
        "suspicion": bubble_data["suspicion"],
        "mood": bubble_data["mood"],
        "prev_mood": bubble_data.get("prev_mood"),
        "history": bubble_data["history"],
        "secret_extracted": bubble_data["secret_extracted"],
        "visit_count": bubble_data["visit_count"],
        "first_visit": first_visit,
        "steps_away": steps_away,
        
        # NPC data for reference
        "npc_name": npc["name"],
        "npc_persona": npc["persona"],
        "npc_secrets": npc["secrets"],
    }
    
    return updated_state
