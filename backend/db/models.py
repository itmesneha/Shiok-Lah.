"""
SQLAlchemy ORM models for Shiok Lah! game state.

Two tables:
- game_sessions: one row per game (tracks global step, status, active character)
- character_bubbles: one row per session-character pair (tracks conversation, suspicion, mood)
"""

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from datetime import datetime, timezone
import os
from config import GAME as GC

DB_PATH = os.getenv("DB_PATH", "shiok_lah.db")
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    pass


class GameSession(Base):
    __tablename__ = "game_sessions"

    session_id = Column(String, primary_key=True)
    global_step = Column(Integer, default=0)
    max_steps = Column(Integer, default=GC.MAX_STEPS)
    game_status = Column(String, default="active")          # active | won | lost
    loss_reason = Column(String, nullable=True)              # suspicion | max_steps | None
    active_character = Column(String, nullable=True)         # character_id currently talking to
    secrets_found = Column(Text, default="[]")               # JSON list of character_ids
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    bubbles = relationship(
        "CharacterBubble",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class CharacterBubble(Base):
    __tablename__ = "character_bubbles"

    session_id = Column(String, ForeignKey("game_sessions.session_id"), primary_key=True)
    character_id = Column(String, primary_key=True)
    suspicion = Column(Float, default=0.0)
    mood = Column(String, default="neutral")
    prev_mood = Column(String, nullable=True)
    history_json = Column(Text, default="[]")                # JSON list of {role, content}
    secret_extracted = Column(Boolean, default=False)
    initiative_fired = Column(Boolean, default=False)
    last_seen_step = Column(Integer, nullable=True)
    visit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    session = relationship("GameSession", back_populates="bubbles")


def init_db():
    """Create all tables if they don't exist, and patch missing columns."""
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        # Lightweight migration for existing local SQLite DBs.
        table_cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(character_bubbles)").fetchall()
        }
        if table_cols and "prev_mood" not in table_cols:
            conn.exec_driver_sql("ALTER TABLE character_bubbles ADD COLUMN prev_mood VARCHAR")
        conn.commit()
    Base.metadata.create_all(engine)
