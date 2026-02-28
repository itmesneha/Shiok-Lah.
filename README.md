# Shiok Lah! 🍜

Conversation game set in Singapore hawker centres.  
You talk to NPC hawkers, manage suspicion, and try to extract recipe secrets before getting kicked out.

This repo now contains:
- `backend/`: FastAPI + LangGraph game server with SSE text/state/audio events
- `godot/`: in-game playable client (current primary frontend)
- `frontend/`: early React/Vite frontend work
- `sample_frontend.py` and `sample_frontend_grid.py`: Streamlit test clients

## Current Architecture

### Backend
- FastAPI app in [backend/main.py](/Users/snehas/Documents/GitHub/Shiok-Lah!/backend/main.py)
- Main routers:
  - `/api/game/*` in [backend/routes/game.py](/Users/snehas/Documents/GitHub/Shiok-Lah!/backend/routes/game.py)
  - `/api/voice/*` in [backend/routes/voice.py](/Users/snehas/Documents/GitHub/Shiok-Lah!/backend/routes/voice.py)
- State: SQLite via SQLAlchemy (`backend/shiok_lah.db`)
- Graph orchestration: LangGraph (`backend/graph/*`)
- TTS: ElevenLabs (optional but integrated)

### Godot client
- Main dialogue client logic in [godot/scripts/NPCDialogue.gd](/Users/snehas/Documents/GitHub/Shiok-Lah!/godot/scripts/NPCDialogue.gd)
- NPC interaction scripts in `godot/scripts/*npc*.gd`
- Supports:
  - `/api/game/talk` opener
  - `/api/game/message` SSE parsing
  - SSE `[AUDIO]` playback
  - `/api/voice/speak` fallback for opener/replies

## API (what clients should call)

### Game
- `POST /api/game/start`
- `POST /api/game/talk`
- `POST /api/game/message`
- `POST /api/game/leave`
- `GET /api/game/state/{session_id}`
- `POST /api/game/reset`

### Voice
- `POST /api/voice/speak`
- `POST /api/voice/ambiance`
- `GET /api/voice/voices`

## SSE format (`/api/game/message`)

Events are sent as `data: ...` lines:
- Plain text tokens/word-drip
- `[AUDIO] <base64_mp3_chunk>`
- `[STATE] { ...json... }`
- `[DONE]`
- `[ERROR] ...`

Client rule:
- Render plain text only
- Decode and play `[AUDIO]`
- Parse `[STATE]` for suspicion/mood/game flags

## Quick Start

### 1. Backend
```bash
cd backend
uv sync
cp .env.example .env
# add required keys (at least ELEVENLABS_API_KEY if you want voice)
uv run uvicorn main:app --reload --port 8000
```

Health check:
```bash
curl http://localhost:8000/
```

### 2. Godot
```bash
open godot/project.godot
```
Run from Godot editor.

## Environment

Backend `.env` commonly used keys:
- `ELEVENLABS_API_KEY`
- `OPENROUTER_API_KEY` (if used by your selected LLM config)

## Troubleshooting

### 404 on `/api/chat/*`
Old routes were removed. Use `/api/game/*`.

### `UNIQUE constraint failed: game_sessions.session_id`
Handled in current code via idempotent `create_game()`, but restart backend after pulling latest.

### `no such column: character_bubbles.prev_mood`
Startup now patches this column in `init_db()`. Restart backend.

### No audio in Godot
Check:
- backend has `ELEVENLABS_API_KEY`
- NPC has `voice_id` in [backend/models/npcs.py](/Users/snehas/Documents/GitHub/Shiok-Lah!/backend/models/npcs.py)
- Godot audio bus/device not muted

## Repo Notes

- `godot/` is now tracked as normal files in this repo (not a submodule).
- `godot/.godot/` is ignored (cache/editor artifacts).
- Root README is intentionally high-level; backend deep details remain in [backend/README.md](/Users/snehas/Documents/GitHub/Shiok-Lah!/backend/README.md).
