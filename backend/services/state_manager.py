# backend/services/state_manager.py
"""
Game state management with SQLAlchemy ORM.

Provides CRUD operations for game sessions and character bubbles
with in-memory caching for performance.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from db.models import GameSession, CharacterBubble, Base, engine, init_db
from models.npcs import NPCS
import json


# Initialize database
init_db()

# In-memory cache
_game_cache = {}
_bubble_cache = {}


def _get_session() -> Session:
    """Get SQLAlchemy session."""
    return Session(engine)


def create_game(session_id: str) -> Dict[str, Any]:
    """Create a new game session with 3 character bubbles."""
    # Check cache first
    if session_id in _game_cache:
        return _game_cache[session_id]
    
    db_session = _get_session()
    try:
        # Create game session
        game = GameSession(
            session_id=session_id,
            global_step=0,
            max_steps=30,
            game_status='active',
            secrets_found='[]'
        )
        db_session.add(game)
        
        # Create character bubbles for all NPCs
        for character_id in NPCS.keys():
            bubble = CharacterBubble(
                session_id=session_id,
                character_id=character_id,
                suspicion=0.0,
                mood='neutral',
                history_json='[]',
                visit_count=0
            )
            db_session.add(bubble)
        
        db_session.commit()
        
        # Load and cache the created game
        game_data = get_game(session_id)
        return game_data
        
    finally:
        db_session.close()


def get_game(session_id: str) -> Dict[str, Any]:
    """Get game session data (cache-first)."""
    # Check cache
    if session_id in _game_cache:
        return _game_cache[session_id]
    
    db_session = _get_session()
    try:
        game = db_session.query(GameSession).filter_by(session_id=session_id).first()
        
        if not game:
            raise ValueError(f"Game session not found: {session_id}")
        
        game_data = {
            "session_id": game.session_id,
            "global_step": game.global_step,
            "max_steps": game.max_steps,
            "game_status": game.game_status,
            "loss_reason": game.loss_reason,
            "active_character": game.active_character,
            "secrets_found": json.loads(game.secrets_found or "[]"),
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "updated_at": game.updated_at.isoformat() if game.updated_at else None
        }
        
        # Cache the result
        _game_cache[session_id] = game_data
        return game_data
        
    finally:
        db_session.close()


def update_game(session_id: str, **kwargs) -> None:
    """Update game session fields."""
    if not kwargs:
        return
    
    db_session = _get_session()
    try:
        game = db_session.query(GameSession).filter_by(session_id=session_id).first()
        
        if not game:
            raise ValueError(f"Game session not found: {session_id}")
        
        # Handle special fields
        if "secrets_found" in kwargs:
            game.secrets_found = json.dumps(kwargs["secrets_found"])
            del kwargs["secrets_found"]
        
        # Update other fields
        for key, value in kwargs.items():
            if hasattr(game, key):
                setattr(game, key, value)
        
        db_session.commit()
        
        # Invalidate cache
        _game_cache.pop(session_id, None)
        
    finally:
        db_session.close()


def reset_game(session_id: str) -> None:
    """Delete and recreate game session."""
    db_session = _get_session()
    try:
        # Delete existing session (cascades to bubbles)
        game = db_session.query(GameSession).filter_by(session_id=session_id).first()
        if game:
            db_session.delete(game)
            db_session.commit()
        
        # Invalidate cache
        _game_cache.pop(session_id, None)
        _bubble_cache.pop(session_id, None)
        
        # Create fresh game
        create_game(session_id)
        
    finally:
        db_session.close()


def get_bubble(session_id: str, character_id: str) -> Dict[str, Any]:
    """Get character bubble data (cache-first)."""
    # Check cache
    cache_key = f"{session_id}:{character_id}"
    if cache_key in _bubble_cache:
        return _bubble_cache[cache_key]
    
    db_session = _get_session()
    try:
        bubble = db_session.query(CharacterBubble).filter_by(
            session_id=session_id, 
            character_id=character_id
        ).first()
        
        if not bubble:
            raise ValueError(f"Character bubble not found: {session_id}/{character_id}")
        
        bubble_data = {
            "session_id": bubble.session_id,
            "character_id": bubble.character_id,
            "suspicion": bubble.suspicion,
            "mood": bubble.mood,
            "prev_mood": bubble.prev_mood,
            "history": json.loads(bubble.history_json or "[]"),
            "secret_extracted": bubble.secret_extracted,
            "initiative_fired": bubble.initiative_fired,
            "last_seen_step": bubble.last_seen_step,
            "visit_count": bubble.visit_count,
            "created_at": bubble.created_at.isoformat() if bubble.created_at else None,
            "updated_at": bubble.updated_at.isoformat() if bubble.updated_at else None
        }
        
        # Cache the result
        _bubble_cache[cache_key] = bubble_data
        return bubble_data
        
    finally:
        db_session.close()


def update_bubble(session_id: str, character_id: str, **kwargs) -> None:
    """Update character bubble fields."""
    if not kwargs:
        return
    
    db_session = _get_session()
    try:
        bubble = db_session.query(CharacterBubble).filter_by(
            session_id=session_id, 
            character_id=character_id
        ).first()
        
        if not bubble:
            raise ValueError(f"Character bubble not found: {session_id}/{character_id}")
        
        # Handle special fields
        if "history" in kwargs:
            bubble.history_json = json.dumps(kwargs["history"])
            del kwargs["history"]
        
        # Update other fields
        for key, value in kwargs.items():
            if hasattr(bubble, key):
                setattr(bubble, key, value)
        
        db_session.commit()
        
        # Invalidate cache
        cache_key = f"{session_id}:{character_id}"
        _bubble_cache.pop(cache_key, None)
        
    finally:
        db_session.close()


def append_to_history(session_id: str, character_id: str, role: str, content: str) -> None:
    """Append a message to character's conversation history."""
    bubble = get_bubble(session_id, character_id)
    history = bubble["history"]
    history.append({"role": role, "content": content})
    
    update_bubble(session_id, character_id, history=history)


def increment_step(session_id: str) -> int:
    """Increment global step counter and return new value."""
    game = get_game(session_id)
    new_step = game["global_step"] + 1
    
    update_game(session_id, global_step=new_step)
    return new_step


def mark_secret_found(session_id: str, character_id: str, secret_index: int = 0) -> int:
    """Mark a secret as found and return total secrets found."""
    game = get_game(session_id)
    secret_key = f"{character_id}:{secret_index}"
    
    if secret_key not in game["secrets_found"]:
        updated_secrets = game["secrets_found"] + [secret_key]
        update_game(session_id, secrets_found=updated_secrets)
        return len(updated_secrets)
    
    return len(game["secrets_found"])


def evict_cache(session_id: str) -> None:
    """Clear all cache entries for a session."""
    _game_cache.pop(session_id, None)
    # Clear all bubble cache entries for this session
    keys_to_remove = [key for key in _bubble_cache.keys() if key.startswith(f"{session_id}:")]
    for key in keys_to_remove:
        _bubble_cache.pop(key, None)


# Database is initialized on import
