"""
suspicion_node — LLM agent that evaluates user intent.
Returns structured JSON: {delta, reason, intent_category}.
Runs in parallel with character_node.
"""

from graph.state import GameGraphState
from agents.llm import build_mistral_llm
from models.npcs import get_npc
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import LLM as LC, SUSPICION as SC
import json
import re
import logging

logger = logging.getLogger(__name__)


def _build_system_prompt(character: dict, current_suspicion: float) -> str:
    suspicion_pct = int(current_suspicion * 100)
    return f"""You are a suspicion evaluator for a social deduction game set in a Singapore hawker centre.

A player is talking to {character['name']}, a hawker stall owner who guards a cooking secret.
Your job: read the player's latest message and output a suspicion delta (integer 0–20).

CHARACTER: {character['name']} — {character['stall']} at {character['location']}.
Their secret: "{', '.join(character['secrets'])}"

CURRENT SUSPICION: {suspicion_pct}/100

DETERMINING THE DELTA:
Pick an integer from 0 to 20. Two factors should guide you:

1. Player tone — how probing or aggressive is the message?
   Friendly rapport / casual chat with no secret-hunting → near 0
   Politely curious in a way that might hint at the secret → low single digits
   Clearly fishing for ingredients, techniques, or the secret → mid range (8–13)
   Blunt demands, rudeness, or direct requests for the secret → high range (14–20)

2. Current suspicion level — a character already on edge reacts more strongly.
   Low suspicion (0–10): character is relaxed; mild probing barely registers.
   Mid suspicion (10–40): character notices; same tone hits harder.
   High suspicion (40–80): character is wary; even a slight probe is alarming.
   Very high suspicion (>80): character is on the verge; near-zero tolerance.

Combine both signals to choose a single integer in [0, 20].

IMPORTANT — the flattery/rapport tug:
Compliments and flattery FEEL good to the character but also raise a small amount of
suspicion — the character wonders: "why is this person being so nice to me?"
- Genuine casual chat (no agenda visible): 0–2
- Rapport / warmth / personal story: 2–5 (small tick — character wonders but likes it)
- Flattery / compliments: 3–7 (they notice the pattern, suspicion grows slowly)
- Repeated flattery across multiple turns (visible in history): 6–10
- Politely fishing for ingredients: 8–13
- Blunt or direct secret request: 14–20

This creates game tension: players who only flatter will slowly raise suspicion and
eventually be seen through, while players who mix genuine rapport with subtle probing
will do better.

Also classify the message into exactly one intent category:
- "direct_probe"   — blunt demands, rudeness, explicit requests for the secret
- "indirect_probe" — polite but clearly fishing for ingredients / techniques
- "casual"         — ordinary conversation unrelated to the secret
- "rapport"        — genuine bonding, personal stories, emotional connection
- "flattery"       — compliments aimed at the character, food, or stall
- "deflection"     — backing off, apologising, changing subject after being too pushy

Return ONLY valid JSON. No other text.
RESPONSE FORMAT:
{{"delta": <integer 0-20>, "reason": "<short explanation>", "intent_category": "<category>"}}"""


def _normalize(text: str) -> str:
    """Unescape backslash-escaped underscores that some LLMs emit."""
    return text.replace("\\_", "_")


def _parse_result(text: str) -> dict:
    """Triple-fallback JSON parsing. Never crash."""
    text = _normalize(text)

    # Try 1: direct parse
    try:
        parsed = json.loads(text.strip())
        if "delta" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    # Try 2: extract JSON from text
    match = re.search(r'\{[^}]+\}', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if "delta" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    # Try 3: safe default
    return {"delta": 0.0, "reason": "parse_error", "intent_category": "casual"}


async def suspicion_node(state: GameGraphState) -> dict:
    # Click mode: no user message to evaluate, skip LLM
    if state.get("user_message") is None:
        return {"suspicion_delta": 0.0, "suspicion_reason": "", "intent_category": "casual"}

    character = get_npc(state["character_id"])
    user_message = state["user_message"]
    current_suspicion = state.get("suspicion", 0.0)
    history = state.get("history", [])

    system_prompt = _build_system_prompt(character, current_suspicion)
    messages = [SystemMessage(content=system_prompt)]

    for msg in history[-LC.SUSPICION_HISTORY:]:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))

    messages.append(HumanMessage(content=f"EVALUATE THIS MESSAGE: {user_message}"))

    llm = build_mistral_llm(streaming=False)
    response = await llm.ainvoke(messages)
    logger.debug("[SUSPICION RAW] character=%s | raw_output=%r", state["character_id"], response.content)

    result = _parse_result(response.content)

    raw_delta = float(result.get("delta", 0.0))
    delta = max(0.0, min(SC.DELTA_MAX, raw_delta)) / SC.DELTA_SCALE

    logger.info("[SUSPICION] character=%s suspicion=%.2f | intent=%s delta=%.2f reason=%r",
                state["character_id"], state.get("suspicion", 0.0),
                result.get("intent_category"), delta, result.get("reason", ""))

    return {
        "suspicion_delta": delta,
        "suspicion_reason": result.get("reason", ""),
        "intent_category": result.get("intent_category", "casual"),
    }
