from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Mood(str, Enum):
    NEUTRAL = "neutral"
    WARM = "warm"
    SUSPICIOUS = "suspicious"
    HOSTILE = "hostile"
    IMPRESSED = "impressed"


# ── Game API schemas ──

class StartGameRequest(BaseModel):
    session_id: str


class StartGameResponse(BaseModel):
    session_id: str
    game_status: str
    characters: list[dict]
    max_steps: int


class TalkRequest(BaseModel):
    session_id: str
    character_id: str


class TalkResponse(BaseModel):
    character_name: str
    dialogue: str | None
    mood: str
    suspicion: float
    visit_count: int
    first_visit: bool
    game_status: str


class MessageRequest(BaseModel):
    session_id: str
    character_id: str
    message: str
    voice_enabled: bool = True


class LeaveRequest(BaseModel):
    session_id: str
    character_id: str


class GameStateResponse(BaseModel):
    session_id: str
    global_step: int
    max_steps: int
    game_status: str
    secrets_found: int
    characters: list[dict]


# ── Voice API schemas (unchanged) ──

class VoiceRequest(BaseModel):
    text: str
    npc_id: str
    mood: Mood = Mood.NEUTRAL


class SoundEffectRequest(BaseModel):
    npc_id: str
