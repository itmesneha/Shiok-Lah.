# Shiok Lah!

A conversational social-deduction game set in a Singapore hawker centre. You play as an undercover food journalist trying to extract secret recipes from three stubborn hawker stall owners — without getting caught. A hawker-center heist game powered by Agentic AI!

Demo Video:
[![SHIOK-LAH DEMO](https://img.youtube.com/vi/IKr7yX__eQw/0.jpg)](https://www.youtube.com/watch?v=IKr7yX__eQw)


<img width="1468" height="794" alt="Screenshot 2026-03-01 at 3 19 03 PM" src="https://github.com/user-attachments/assets/b73e4a1f-3b8a-4371-bccc-0a209b70bb76" />

<img width="1468" height="794" alt="Screenshot 2026-03-01 at 3 18 51 PM" src="https://github.com/user-attachments/assets/a7331947-0312-45cc-967e-5d609fe1968f" />

---

## Table of Contents

- [Gameplay](#gameplay)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How to Run](#how-to-run)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Gameplay

You have **30 total turns** spread across three NPCs:

| NPC | Stall | Location | Secret |
|-----|-------|----------|--------|
| Uncle Robert | Robert's Char Kway Teow | Maxwell Food Centre, Stall 17 | Fish sauce (splashed before final wok toss) |
| Auntie Siti | Siti's Nasi Padang | Geylang Serai Market | Fresh hand-pressed coconut milk (last 10 min) |
| Ah Kow | Ah Kow Bak Chor Mee | Tiong Bahru Market | Aged plum vinegar blended with black vinegar |

### Win Condition
Extract all three secrets. Each NPC has a **reveal ladder** — they only open up when you build genuine rapport. Direct questions always get deflected. Flattery without substance raises suspicion.

### Lose Conditions
- **Suspicion reaches 95%** on any NPC → kicked out
- **30 turns used up** before all secrets are found

### Suspicion System
Every message you send is evaluated by an LLM judge. Your intent is classified as one of:
`direct_probe` / `indirect_probe` / `casual` / `rapport` / `flattery` / `deflection`

Each category moves suspicion differently. NPCs transition through moods as suspicion rises:

```
warm (0–20%) → neutral (20–45%) → suspicious (45–85%) → hostile (85–95%)
```

A special `impressed` mood triggers when you build genuine rapport while keeping suspicion below 40%.

### Push-to-Talk
Hold **Shift+Space** while the dialogue box is open to speak. Release to auto-submit the transcribed text. Or just type and press **Enter**.

---

## Features

### Game
- Three fully voiced NPC characters with distinct Singlish personalities
- Per-NPC suspicion tracking with 10-segment visual bar
- Mood indicator that updates in real time (warm / neutral / suspicious / hostile / impressed)
- Secret extraction reveal ladder — NPCs gradually open up over multiple visits
- 30-turn global limit shared across all characters
- Win screen showing all three recipes revealed
- Game over popup with reason (suspicion caught / out of turns)
- Round reset — play again from the same session

### Dialogue
- **Streaming NPC responses** — words appear one at a time as the LLM generates them
- **Simultaneous audio + text** — TTS audio plays while text streams, no waiting
- **Full conversation history** loaded on each visit so NPCs remember previous exchanges
- Mood-aware TTS voice settings (different expressiveness per mood)
- Fallback TTS via `/api/voice/speak` if inline audio fails

### Voice Input
- **Push-to-talk** with **Shift+Space** — hold to record, release to auto-submit
- Realtime transcription via Mistral Voxtral over WebSocket
- Transcript appears live in the text field as you speak
- Auto-submits after transcription finishes (waits for `done` event, not immediate)
- Graceful fallback: if WebSocket fails, type manually

### Backend
- LangGraph parallel orchestration: NPC response + suspicion evaluation run simultaneously
- SSE streaming: text tokens, PCM audio chunks, and game state in one response
- SQLite persistence with in-memory cache — state survives backend restarts
- Session-based — one UUID per player, multiple characters per session

---

## Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│         Godot 4.6 Client        │     │         FastAPI Backend               │
│                                 │     │                                       │
│  Player → NPC click             │────▶│  POST /api/game/talk                  │
│  NPCDialogue opens              │◀────│  LangGraph: load → preflight →        │
│                                 │     │  character_node → persist             │
│  Player types / Shift+Space     │     │                                       │
│  ↓ Voxtral WebSocket            │────▶│  WS /api/voice/transcribe/realtime   │
│  transcript → player_input      │◀────│  Mistral Voxtral STT                  │
│                                 │     │                                       │
│  Player submits message         │────▶│  POST /api/game/message (SSE)         │
│  SSE parsing loop               │     │  LangGraph parallel:                  │
│    data: word tokens            │◀────│    ├─ character_node (LLM response)   │
│    data: [AUDIO] base64_pcm     │     │    ├─ suspicion_node (intent eval)    │
│    data: [STATE] json           │     │    ├─ voice_node (ElevenLabs TTS)     │
│    data: [DONE]                 │     │    └─ win_check (secret detection)    │
│                                 │     │  → persist (DB write)                 │
│  PCM playback (22050 Hz mono)   │     │                                       │
│  Suspicion bar update           │     │  SQLite: game_sessions                │
│  Mood indicator update          │     │         character_bubbles             │
└─────────────────────────────────┘     └──────────────────────────────────────┘
```

### LangGraph Conversation Graph

```
                      START
                        │
                        ▼
                    load_state
                        │
                        ▼
                     preflight
                        │
           ┌────────────┴────────────┐
           │ error / game_over       │ continue
           ▼                         ▼
        persist                    gate
           │                   ┌────┴────┐
          END                  ▼         ▼          ← parallel branches
                        character_node  suspicion_node
                           │      │         │
                           ▼      ▼         ▼
                      voice_node win_check apply_suspicion
                           │         │         │
                           └────┬────┘─────────┘   ← 3-way fan-in
                                ▼
                             persist
                                │
                               END
```

| Node | What it does |
|------|-------------|
| `load_state` | Loads GameSession + CharacterBubble from DB, increments visit count |
| `preflight` | Validates session, checks terminal conditions (suspicion ≥ 95%, steps exhausted) |
| `character_node` | Mistral LLM generates NPC dialogue (120 tokens, temp 0.7) |
| `suspicion_node` | Mistral LLM evaluates player intent → suspicion delta + intent category |
| `voice_node` | ElevenLabs TTS pre-generates PCM audio with mood-aware voice settings |
| `win_check` | LLM judges whether secret was revealed (confidence > 0.40 required) |
| `apply_suspicion` | Applies delta to suspicion, clamps to [0, 1], derives new mood |
| `persist` | Writes all state back to DB, appends messages to history, increments step |

### SSE Event Format (`/api/game/message`)

```
data: Hello lah, what you want?       ← plain text word tokens (80ms drip)
data: [AUDIO] <base64_pcm_chunk>      ← 4096-byte PCM chunks (22050 Hz, 16-bit mono)
data: [AUDIO_DONE]                    ← audio stream finished
data: [STATE] {"suspicion": 0.12, "mood": "warm", "secret_extracted": false, ...}
data: [DONE]                          ← stream complete
data: [ERROR] something went wrong    ← on error
```

---

## Project Structure

```
Shiok-Lah./
├── godot/                          # Godot 4.6 game
│   ├── project.godot               # Main scene: start_screen.tscn
│   ├── scenes/
│   │   ├── start_screen.tscn       # Main menu
│   │   ├── game.tscn               # Game world (player + NPCs)
│   │   ├── NPCDialogue.tscn        # Dialogue UI overlay
│   │   ├── MoodIndicator.tscn      # Mood visual
│   │   └── GameOverPopup.tscn      # Win/lose screen
│   ├── scripts/
│   │   ├── NPCDialogue.gd          # Core dialogue controller (SSE, PCM, PTT)
│   │   ├── GameState.gd            # Autoload: session ID, secrets tracking
│   │   ├── DialogueManager.gd      # Autoload: dialogue scene lifecycle
│   │   ├── player.gd               # Player movement
│   │   ├── uncle_robert_npc.gd     # NPC interaction area
│   │   ├── auntie_siti_npc.gd
│   │   ├── uncle_ah_kow.gd
│   │   └── MoodIndicator.gd        # Mood indicator logic
│   └── assets/
│       ├── fonts/Minecraft.ttf
│       ├── background_score/swing_jazz.ogg
│       └── characters/             # NPC + player sprites
│
└── backend/                        # FastAPI + LangGraph server
    ├── main.py                     # App entry point, CORS, routers
    ├── config.py                   # All tunable game parameters
    ├── pyproject.toml
    ├── .env.example
    ├── routes/
    │   ├── game.py                 # /api/game/* endpoints
    │   └── voice.py                # /api/voice/* endpoints + WS
    ├── graph/
    │   ├── conversation_graph.py   # LangGraph compile function
    │   └── nodes/
    │       ├── load_state.py
    │       ├── preflight.py
    │       ├── character_node.py
    │       ├── suspicion_node.py
    │       ├── voice_node.py
    │       ├── win_check.py
    │       ├── apply_suspicion.py
    │       └── persist.py
    ├── models/
    │   ├── npcs.py                 # NPC personas, secrets, voice IDs
    │   └── schemas.py              # Pydantic request/response models
    ├── services/
    │   ├── state_manager.py        # DB CRUD + in-memory cache
    │   ├── context_manager.py      # visit tracking, steps_away
    │   └── mood_engine.py          # Suspicion → mood derivation
    └── db/
        └── models.py               # SQLAlchemy models (GameSession, CharacterBubble)
```

---

## How to Run

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Godot 4.6 editor
- API keys: `MISTRAL_API_KEY` (required), `ELEVENLABS_API_KEY` (required for voice)

### 1. Start the Backend

```bash
cd backend

# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env and fill in your API keys:
#   MISTRAL_API_KEY=...
#   ELEVENLABS_API_KEY=...

# Start the server
uv run uvicorn main:app --reload --port 8000
```

Verify it's running:
```bash
curl http://localhost:8000/
# → {"status": "Shiok!"}
```

The backend must be running before you open the Godot game. It listens on `http://127.0.0.1:8000`.

### 2. Open the Godot Game

```bash
# Open in Godot editor
open godot/project.godot
```

Then press **F5** (or the Play button) to run the game.

> The game window opens at 1280×720. The backend URL is hardcoded to `http://127.0.0.1:8000` — no configuration needed in Godot.

### Controls

| Key | Action |
|-----|--------|
| **Arrow Keys** | Move player |
| **E** | Interact with NPC (when nearby) |
| **Shift+Space** (hold) | Push-to-talk — speak to transcribe |
| **Shift+Space** (release) | Stop recording, auto-submit transcript |
| **Enter** | Submit typed message |
| **Escape** | Close dialogue |

---

## API Reference

### Game Endpoints

#### `POST /api/game/start`
Create a new game session.
```json
{ "session_id": "uuid-string" }
```
Returns: session details + list of 3 characters.

#### `POST /api/game/talk`
Activate a character (no player message) — triggers NPC opener.
```json
{ "session_id": "...", "character_id": "uncle_robert" }
```
Returns: `{ character_name, dialogue, mood, suspicion, visit_count, first_visit, game_status }`

#### `POST /api/game/message`
Send a player message. Returns an SSE stream.
```json
{ "session_id": "...", "character_id": "uncle_robert", "message": "Your kway teow very shiok!", "voice_enabled": true }
```
SSE stream: plain text tokens + `[AUDIO]` + `[STATE]` + `[DONE]`

#### `GET /api/game/state/{session_id}`
Get full game state including all NPC suspicion/mood/secrets.

#### `POST /api/game/leave`
Notify server that player left a character's stall.
```json
{ "session_id": "...", "character_id": "uncle_robert" }
```

#### `POST /api/game/reset`
Reset a session to a fresh game state.
```json
{ "session_id": "..." }
```

### Voice Endpoints

#### `POST /api/voice/speak`
Generate TTS audio for a line (fallback when SSE audio is unavailable).
```json
{ "text": "...", "npc_id": "uncle_robert", "mood": "warm" }
```
Returns: raw PCM audio stream (22050 Hz, 16-bit mono).

#### `WS /api/voice/transcribe/realtime`
Realtime Voxtral speech-to-text.

**Protocol:**
- Client sends **binary frames**: raw PCM (16kHz, 16-bit mono, little-endian)
- Client sends **text `"STOP"`**: end of speech
- Server sends `{"type": "delta", "text": "..."}`: partial transcript
- Server sends `{"type": "done"}`: transcription complete
- Server sends `{"type": "error", "message": "..."}`: on error

---

## Environment Variables

Create `backend/.env` from `backend/.env.example`:

| Variable | Required | Description |
|----------|----------|-------------|
| `MISTRAL_API_KEY` | Yes | Used for LLM (NPC dialogue, suspicion eval, win check) and Voxtral STT |
| `ELEVENLABS_API_KEY` | Yes (for audio) | NPC text-to-speech. Game works without it but NPCs will be silent |
| `DB_PATH` | No | SQLite database path. Defaults to `shiok_lah.db` |

---

## Troubleshooting

### "Could not start game session" in Godot
Backend is not running. Start it:
```bash
cd backend && uv run uvicorn main:app --reload --port 8000
```

### No NPC voice / silent game
- Check `ELEVENLABS_API_KEY` is set in `backend/.env`
- Check that NPCs have `voice_id` set in `backend/models/npcs.py`
- Check that your Godot system audio is not muted

### Push-to-talk not working / no transcription
- Check `MISTRAL_API_KEY` is set (Voxtral uses the same key)
- On macOS, grant Godot microphone permission: System Settings → Privacy & Security → Microphone
- Hold **Shift+Space** (both keys together), speak clearly, then release



### Game state is stale after pulling new code
Delete `backend/shiok_lah.db` to start fresh, then restart the backend.
```bash
rm backend/shiok_lah.db
uv run uvicorn main:app --reload --port 8000
```
