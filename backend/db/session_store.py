"""
SQLite session store.
Stores conversation history + game state per (session_id, npc_id) pair.
One row per player-NPC relationship.
"""

from sqlalchemy import create_engine, Column, String, Float, Boolean, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Session
from datetime import datetime, timezone
import json
import os

DB_PATH = os.getenv("DB_PATH", "shiok_lah.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class NPCSession(Base):
    __tablename__ = "npc_sessions"

    session_id = Column(String, primary_key=True)
    npc_id = Column(String, primary_key=True)
    history_json = Column(Text, default="[]")       # list of {role, content}
    mood = Column(String, default="neutral")
    suspicion = Column(Float, default=0.0)
    game_over = Column(Boolean, default=False)
    win = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(engine)


def get_session(session_id: str, npc_id: str) -> NPCSession:
    """Get existing session or create a fresh one."""
    with Session(engine) as db:
        row = db.get(NPCSession, (session_id, npc_id))
        if not row:
            row = NPCSession(session_id=session_id, npc_id=npc_id)
            db.add(row)
            db.commit()
            db.refresh(row)
        return _detach(row)


def append_message(session_id: str, npc_id: str, role: str, content: str):
    """Append a single message to history."""
    with Session(engine) as db:
        row = db.get(NPCSession, (session_id, npc_id))
        if not row:
            row = NPCSession(session_id=session_id, npc_id=npc_id)
            db.add(row)
        history = json.loads(row.history_json or "[]")
        history.append({"role": role, "content": content})
        row.history_json = json.dumps(history)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()


def update_game_state(session_id: str, npc_id: str, mood: str,
                      suspicion: float, game_over: bool, win: bool):
    with Session(engine) as db:
        row = db.get(NPCSession, (session_id, npc_id))
        if row:
            row.mood = mood
            row.suspicion = suspicion
            row.game_over = game_over
            row.win = win
            row.updated_at = datetime.now(timezone.utc)
            db.commit()


def reset_session(session_id: str, npc_id: str):
    """Reset a player's conversation with a specific NPC."""
    with Session(engine) as db:
        row = db.get(NPCSession, (session_id, npc_id))
        if row:
            row.history_json = "[]"
            row.mood = "neutral"
            row.suspicion = 0.0
            row.game_over = False
            row.win = False
            row.updated_at = datetime.now(timezone.utc)
            db.commit()


def _detach(row: NPCSession) -> dict:
    """Convert ORM row to plain dict so it's usable outside the session."""
    return {
        "session_id": row.session_id,
        "npc_id": row.npc_id,
        "history": json.loads(row.history_json or "[]"),
        "mood": row.mood,
        "suspicion": row.suspicion,
        "game_over": row.game_over,
        "win": row.win,
    }