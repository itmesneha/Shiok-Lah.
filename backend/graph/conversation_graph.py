"""
Conversation Graph — single LangGraph StateGraph that handles both
"user clicked a character" (opener) and "user sent a message" (conversation).

Graph structure:
  load_state → preflight → (error? → persist → END)
                         → gate
                            ↓                    ↓
                    character_node          suspicion_node   ← PARALLEL
                       ↓        ↓                ↓      ↓
                  voice_node  win_check     win_check  apply_suspicion
                       ↓        ↓                ↓      ↓
                      persist (fan-in: voice_node + win_check + apply_suspicion)
                          ↓
                         END

voice_node runs after character_node, in parallel with the suspicion chain.
In click mode, suspicion_node short-circuits (returns delta=0) and win_check
skips its LLM call.
"""

from langgraph.graph import StateGraph, START, END
import logging

from graph.state import GameGraphState
from graph.nodes.load_state import load_state
from graph.nodes.preflight import preflight
from graph.nodes.character_node import character_node
from graph.nodes.voice_node import voice_node
from graph.nodes.suspicion_node import suspicion_node
from graph.nodes.apply_suspicion import apply_suspicion
from graph.nodes.win_check import win_check
from graph.nodes.persist import persist

logger = logging.getLogger("shiok.graph")


# ── Conditional edge functions ──

def after_preflight(state: GameGraphState) -> str:
    """Route after preflight checks."""
    if state.get("error") or state.get("game_over"):
        return "persist"
    return "gate"


# ── Build the graph ──

def build_conversation_graph() -> StateGraph:
    graph = StateGraph(GameGraphState)

    # Add all nodes
    graph.add_node("load_state", load_state)
    graph.add_node("preflight", preflight)
    graph.add_node("gate", lambda state: {})  # no-op pass-through
    graph.add_node("character_node", character_node)
    graph.add_node("voice_node", voice_node)
    graph.add_node("suspicion_node", suspicion_node)
    graph.add_node("win_check", win_check)
    graph.add_node("apply_suspicion", apply_suspicion)
    graph.add_node("persist", persist)

    # ── Edges ──

    graph.add_edge(START, "load_state")
    graph.add_edge("load_state", "preflight")

    # Preflight → conditional: error/game_over → persist, else → gate
    graph.add_conditional_edges(
        "preflight",
        after_preflight,
        {
            "persist": "persist",
            "gate": "gate",
        },
    )

    # gate → character_node and suspicion_node in parallel
    graph.add_edge("gate", "character_node")
    graph.add_edge("gate", "suspicion_node")

    # character_node → voice_node (starts TTS as soon as dialogue is ready)
    graph.add_edge("character_node", "voice_node")

    # Both character_node + suspicion_node fan-in to win_check and apply_suspicion
    graph.add_edge("character_node", "win_check")
    graph.add_edge("suspicion_node", "win_check")
    graph.add_edge("character_node", "apply_suspicion")
    graph.add_edge("suspicion_node", "apply_suspicion")

    # persist waits for voice_node, win_check, AND apply_suspicion (3-way fan-in)
    graph.add_edge("voice_node", "persist")
    graph.add_edge("win_check", "persist")
    graph.add_edge("apply_suspicion", "persist")

    graph.add_edge("persist", END)

    return graph


def compile_conversation_graph():
    """Returns a compiled, ready-to-invoke graph."""
    graph = build_conversation_graph()
    return graph.compile()
