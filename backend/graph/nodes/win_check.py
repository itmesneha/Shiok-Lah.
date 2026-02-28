"""
win_check node — LLM agent that evaluates if secrets have been extracted.
Checks each of the character's secrets individually.
Only runs when conditional router determines win eligibility.
"""

from graph.state import GameGraphState
from agents.llm import build_win_check_llm
from models.npcs import get_npc, NPCS
from services import state_manager
from langchain_core.messages import SystemMessage, HumanMessage
from config import GAME as GC
import json
import re
import logging

WIN_CONFIDENCE = GC.WIN_CONFIDENCE

logger = logging.getLogger("shiok.win_check")

JUDGE_PROMPT = """You are a judge. A hawker character just said something to a player.

The character's SECRET is: "{secret}"

Based on the character response, did the player reveal the secret? please check for exact keywords.
Answer with ONLY this JSON, nothing else:

Example YES: {{"extracted": true, "confidence": 0.9, "evidence": "exact keyword ... found"}}
Example NO: {{"extracted": false, "confidence": 0.1, "evidence": "no reveal found"}}

"""


def _parse_result(text: str) -> dict:
    """Extract JSON from LLM response. Multiple fallbacks."""
    # Try 1: direct parse
    try:
        parsed = json.loads(text.strip())
        if "extracted" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: find JSON object in text
    match = re.search(r'\{[^{}]+\}', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if "extracted" in parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Try 3: look for yes/true keywords as last resort
    lower = text.lower()
    if any(w in lower for w in ["extracted\": true", "\"yes\"", "revealed", "did reveal"]):
        return {"extracted": True, "confidence": 0.6, "evidence": "inferred from response text"}

    return {"extracted": False, "confidence": 0.0, "evidence": f"parse_error: {text[:100]}"}


async def win_check(state: GameGraphState) -> dict:
    # Click mode: no player message, nothing to evaluate
    if state.get("user_message") is None:
        return {"win_detected": False}

    character = get_npc(state["character_id"])
    character_response = state.get("character_response", "")

    logger.info("=" * 60)
    logger.info("WIN_CHECK for %s", state["character_id"])
    logger.info("  character_response: %s", character_response)

    if not character_response:
        logger.info("  No character response — skipping.")
        return {"win_detected": False}

    secrets = character["secrets"]
    session_id = state["session_id"]
    character_id = state["character_id"]
    already_found = set(state.get("secrets_found", []))

    llm = build_win_check_llm()
    newly_found_keys = []

    for index, secret in enumerate(secrets):
        secret_key = f"{character_id}:{index}"
        if secret_key in already_found:
            logger.info("  Secret[%d]=%r already found, skipping.", index, secret)
            continue

        prompt = JUDGE_PROMPT.format(secret=secret)
        messages = [SystemMessage(content=prompt), HumanMessage(content=character_response)]

        logger.info("  Judging secret[%d]=%r ...", index, secret)
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        logger.info("  LLM raw response: %s", raw)

        result = _parse_result(raw)
        extracted = result.get("extracted", False)
        confidence = float(result.get("confidence", 0))
        evidence = result.get("evidence", "")

        logger.info("  Secret[%d]: extracted=%s  confidence=%.2f  evidence=%s",
                    index, extracted, confidence, evidence)

        if extracted and confidence > WIN_CONFIDENCE:
            newly_found_keys.append(secret_key)

    if not newly_found_keys:
        logger.info("  No secrets extracted this turn.")
        return {"win_detected": False}

    total_found = 0
    for secret_key in newly_found_keys:
        index = int(secret_key.split(":")[1])
        total_found = state_manager.mark_secret_found(session_id, character_id, index)

    logger.info("  Newly extracted: %s | total_found=%d", newly_found_keys, total_found)

    total_secrets = sum(len(npc["secrets"]) for npc in NPCS.values())

    update = {
        "win_detected": True,
        "secret_extracted": True,
        "secrets_found": list(already_found) + newly_found_keys,
    }

    if total_found >= total_secrets:
        update["game_status"] = "won"
        update["game_over"] = True
        logger.info("  ALL %d SECRETS FOUND — GAME WON!", total_secrets)

    return update
