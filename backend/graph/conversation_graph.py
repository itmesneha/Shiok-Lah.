"""
Conversation Graph — single LangGraph StateGraph that handles both
"user clicked a character" (opener) and "user sent a message" (conversation).

Graph structure:
  load_state → preflight → (error or game_over? → persist → END)
                         → gate
                            ↓                    ↓
                    character_node          suspicion_node   ← PARALLEL
                       ↓        ↓                ↓
                  voice_node  win_check     apply_suspicion
                       ↓        ↓                ↓
                      persist (3-way fan-in)
                          ↓
                         END

No cross-branch edges: win_check only needs character output;
apply_suspicion only needs suspicion_node output.
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


def after_preflight(state: GameGraphState) -> str:
    if state.get("error") or state.get("game_over"):
        return "persist"
    return "gate"


def build_conversation_graph() -> StateGraph:
    graph = StateGraph(GameGraphState)

    graph.add_node("load_state", load_state)
    graph.add_node("preflight", preflight)
    graph.add_node("gate", lambda state: {})
    graph.add_node("character_node", character_node)
    graph.add_node("voice_node", voice_node)
    graph.add_node("suspicion_node", suspicion_node)
    graph.add_node("apply_suspicion", apply_suspicion)
    graph.add_node("win_check", win_check)
    graph.add_node("persist", persist)

    graph.add_edge(START, "load_state")
    graph.add_edge("load_state", "preflight")

    graph.add_conditional_edges(
        "preflight",
        after_preflight,
        {"persist": "persist", "gate": "gate"},
    )

    # Parallel fan-out from gate — no cross-branch edges
    graph.add_edge("gate", "character_node")
    graph.add_edge("gate", "suspicion_node")

    # Character branch
    graph.add_edge("character_node", "voice_node")
    graph.add_edge("character_node", "win_check")

    # Suspicion branch
    graph.add_edge("suspicion_node", "apply_suspicion")

    # 3-way fan-in at persist
    graph.add_edge("voice_node", "persist")
    graph.add_edge("win_check", "persist")
    graph.add_edge("apply_suspicion", "persist")

    graph.add_edge("persist", END)

    return graph


def compile_conversation_graph():
    """Returns a compiled, ready-to-invoke graph."""
    return build_conversation_graph().compile()
