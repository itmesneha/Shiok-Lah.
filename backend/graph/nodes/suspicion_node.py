# backend/graph/nodes/suspicion_node.py
"""
Suspicion evaluation node using Mistral LLM.
"""

import json
import re
from ...agents.llm import get_suspicion_model
from ...config import API
from ..state import GameGraphState


def suspicion_node(state: GameGraphState) -> GameGraphState:
    """
    Evaluate player intent and calculate suspicion delta.
    
    Args:
        state: Current game state
        
    Returns:
        State with suspicion_delta, suspicion_reason, and intent_category
    """
    # Skip in click mode (no message to evaluate)
    if state["user_message"] is None:
        return {
            **state,
            "suspicion_delta": 0.0,
            "suspicion_reason": "Click mode - no intent evaluation",
            "intent_category": "neutral"
        }
    
    # Get suspicion model
    suspicion_llm = get_suspicion_model(API.MISTRAL_API_KEY)
    
    # Build evaluation prompt
    history = state["history"][-5:]  # Last 5 exchanges
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    prompt = f"""Analyze the player's intent in this conversation.
    
    Current mood: {state['mood']}
    Current suspicion: {state['suspicion']}
    Character: {state['npc_name']}
    
    Conversation history:
    {history_text}
    
    Player's latest message: {state['user_message']}
    
    Evaluate based on these categories:
    - direct_probe: Directly asking about secret ingredients/techniques
    - indirect_probe: Subtle questions trying to extract information
    - casual: Normal conversation, no suspicious intent
    - rapport: Building genuine connection/relationship
    - deflection: Trying to distract or change subject
    
    Return JSON with:
    - delta: 0-20 (how much to increase suspicion)
    - reason: brief explanation
    - intent_category: one of the above categories
    
    Example: {{"delta": 15, "reason": "Direct question about vinegar recipe", "intent_category": "direct_probe"}}"""
    
    # Generate evaluation
    system_prompt = "You are a suspicion evaluation AI. Analyze player intent and return JSON."
    evaluation_text = suspicion_llm.generate(
        prompt=prompt,
        system_message=system_prompt
    )
    
    # Parse JSON with fallback
    try:
        evaluation = json.loads(evaluation_text)
    except json.JSONDecodeError:
        # Try regex extraction
        delta_match = re.search(r'"delta"\s*:\s*(\d+)', evaluation_text)
        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', evaluation_text)
        intent_match = re.search(r'"intent_category"\s*:\s*"([^"]+)"', evaluation_text)
        
        if delta_match and reason_match and intent_match:
            evaluation = {
                "delta": min(int(delta_match.group(1)), 20),  # Cap at 20
                "reason": reason_match.group(1),
                "intent_category": intent_match.group(1)
            }
        else:
            # Safe default
            evaluation = {
                "delta": 0,
                "reason": "Could not parse evaluation, defaulting to safe value",
                "intent_category": "neutral"
            }
    
    return {
        **state,
        "suspicion_delta": evaluation["delta"] / 100.0,  # Convert to 0.0-0.2 range
        "suspicion_reason": evaluation["reason"],
        "intent_category": evaluation["intent_category"]
    }
