"""
character_node — LLM agent that generates in-character dialogue.
Handles both openers (click) and responses (message).
"""

from graph.state import GameGraphState
from agents.llm import build_llm
from models.npcs import get_npc
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import logging
import re

logger = logging.getLogger(__name__)


def _build_system_prompt(character: dict, mood: str, suspicion: float,
                         first_visit: bool, steps_away: int | None,
                         prev_mood: str | None = None) -> str:
    if suspicion < 0.25:
        suspicion_desc = "You feel relaxed and trusting toward this person."
    elif suspicion < 0.50:
        suspicion_desc = "You're not sure about this person. Stay friendly but guarded."
    elif suspicion < 0.70:
        suspicion_desc = "Something feels off. You're getting suspicious. Deflect and change subject."
    else:
        suspicion_desc = "You don't trust this person at all. Short answers. Tell them to leave."

    returning_context = ""
    if not first_visit and steps_away is not None:
        returning_context = (
            f"\nThis person has visited before. They came back after {steps_away} turns away. "
            "React naturally — acknowledge it or not, whatever feels right."
        )

    mood_shift_context = ""
    if prev_mood and prev_mood != mood:
        mood_shift_context = (
            f"\nYour emotional state just shifted — you were feeling {prev_mood} and now you feel {mood}. "
            "Let this show naturally. Do not announce it."
        )

    return f"""{character['persona']}

---
CURRENT STATE:
- Mood: {mood}
- {suspicion_desc}
{mood_shift_context}
{returning_context}

RULES:
- Respond ONLY with your in-character dialogue.
- HARD LIMIT: maximum 2 sentences, maximum 35 words total.
- No stage directions, markdown, emojis, bullet points, or brackets.
- Do not repeat yourself.
- No JSON, metadata, or out-of-character text.
- Do NOT break character.
- Do NOT try to sell food or take orders."""


def _sanitize_character_reply(raw_reply: str, suspicion: float) -> str:
    text = (raw_reply or "").strip()
    if not text:
        return "Can lah, what you want to ask?"

    text = re.split(r"\n\s*\n", text, maxsplit=1)[0].strip()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    max_sentences = 1 if suspicion >= 0.5 else 2
    trimmed = " ".join(parts[:max_sentences]).strip()

    words = trimmed.split()
    if len(words) > 35:
        trimmed = " ".join(words[:35]).rstrip(",;:") + "."

    return trimmed or "Can lah, what you want to ask?"


async def character_node(state: GameGraphState) -> dict:
    character = get_npc(state["character_id"])
    mood = state.get("mood", "neutral")
    suspicion = state.get("suspicion", 0.0)
    history = state.get("history", [])
    user_message = state.get("user_message")
    first_visit = state.get("first_visit", True)
    steps_away = state.get("steps_away")
    prev_mood = state.get("prev_mood")

    system_prompt = _build_system_prompt(
        character, mood, suspicion, first_visit, steps_away, prev_mood
    )
    messages = [SystemMessage(content=system_prompt)]

    for msg in history:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))

    if user_message is None:
        if first_visit:
            messages.append(HumanMessage(
                content="[A new customer just walked up to your stall. Greet them in character.]"
            ))
        else:
            messages.append(HumanMessage(
                content="[This customer just came back to your stall. React naturally.]"
            ))
    else:
        messages.append(HumanMessage(content=user_message))

    llm = build_llm(streaming=False)
    try:
        response = await llm.ainvoke(messages)
        reply = _sanitize_character_reply(response.content.strip(), suspicion)
    except Exception as e:
        logger.exception("[CHARACTER] LLM failed for %s: %s", state["character_id"], e)
        fallback = "Wah, my head not working now. Ask me again in a bit lah."
        if suspicion >= 0.7:
            fallback = "I busy now. You move on first."
        reply = fallback

    logger.info("[CHARACTER] character=%s mood=%s suspicion=%.2f | response=%r",
                state["character_id"], mood, suspicion, reply)

    updated_history = list(history)
    if user_message is not None:
        updated_history.append({"role": "user", "content": user_message})
    updated_history.append({"role": "assistant", "content": reply})

    return {"character_response": reply, "history": updated_history}
