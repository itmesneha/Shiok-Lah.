import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from mistralai import Mistral
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)
from models.schemas import VoiceRequest, SoundEffectRequest, Mood
from models.npcs import get_npc
from dotenv import load_dotenv
import os
import httpx

load_dotenv()

router = APIRouter()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# Supported sample rates: 8000, 16000, 22050, 44100, 48000
VOXTRAL_SAMPLE_RATE = 16000
VOXTRAL_MODEL = "voxtral-mini-transcribe-realtime-2602"

# Mood -> ElevenLabs voice settings
# stability: lower = more expressive/variable. similarity_boost: higher = stays truer to voice
MOOD_VOICE_SETTINGS = {
    Mood.NEUTRAL:    {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
    Mood.WARM:       {"stability": 0.4, "similarity_boost": 0.80, "style": 0.3},
    Mood.SUSPICIOUS: {"stability": 0.6, "similarity_boost": 0.70, "style": 0.1},
    Mood.HOSTILE:    {"stability": 0.3, "similarity_boost": 0.65, "style": 0.5},
    Mood.IMPRESSED:  {"stability": 0.35, "similarity_boost": 0.80, "style": 0.4},
}

# Ambiance sound effect prompts per scene
AMBIANCE_PROMPTS = {
    "hawker_centre_busy": "Busy hawker centre, wok sizzling, distant chatter, clinking bowls, exhaust fans humming",
    "hawker_centre_quiet": "Quiet hawker centre morning, occasional footsteps, distant radio playing old Mandarin song",
    "market_morning": "Wet market morning ambiance, vegetable vendors calling out, dripping water, bustling crowd",
}


async def tts_stream_chunks(voice_id: str, text: str, mood_str: str):
    """Async generator — yields raw PCM byte chunks (signed 16-bit, 22050 Hz, mono)."""
    settings = MOOD_VOICE_SETTINGS.get(Mood(mood_str), MOOD_VOICE_SETTINGS[Mood.NEUTRAL])
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream(
            "POST",
            f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}/stream",
            params={"output_format": "pcm_22050"},
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": settings,
            },
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                raise RuntimeError(f"ElevenLabs {response.status_code}: {error_body.decode()[:200]}")
            async for chunk in response.aiter_bytes(4096):
                yield chunk


@router.post("/speak")
async def speak(req: VoiceRequest):
    """Stream TTS audio from ElevenLabs for an NPC line"""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ElevenLabs API key not set")

    try:
        npc = get_npc(req.npc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    voice_id = npc.get("voice_id")
    if not voice_id:
        raise HTTPException(status_code=400, detail=f"Voice ID not set for {req.npc_id}. Run Voice Design first.")

    settings = MOOD_VOICE_SETTINGS.get(req.mood, MOOD_VOICE_SETTINGS[Mood.NEUTRAL])

    payload = {
        "text": req.text,
        "model_id": "eleven_turbo_v2_5",  # lowest latency model
        "voice_settings": settings,
    }

    async def stream_audio():
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream(
                "POST",
                f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}/stream",
                params={"output_format": "pcm_22050"},
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    raise HTTPException(status_code=response.status_code, detail=error.decode())
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream_audio(),
        media_type="audio/L16",  # raw signed 16-bit PCM
        headers={"X-NPC-Mood": req.mood.value},
    )


@router.post("/ambiance")
async def get_ambiance(req: SoundEffectRequest):
    """Generate ambient sound for a scene using ElevenLabs Sound Effects API"""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ElevenLabs API key not set")

    try:
        npc = get_npc(req.npc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    ambiance_key = npc.get("ambiance", "hawker_centre_busy")
    prompt = AMBIANCE_PROMPTS.get(ambiance_key, AMBIANCE_PROMPTS["hawker_centre_busy"])

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{ELEVENLABS_BASE}/sound-generation",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": prompt,
                "duration_seconds": 22,  # ElevenLabs max is 22s, loop on frontend
                "prompt_influence": 0.3,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return StreamingResponse(
        iter([response.content]),
        media_type="audio/mpeg",
    )


@router.get("/voices")
async def list_voices():
    """List available ElevenLabs voices - useful for Voice Design setup"""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ElevenLabs API key not set")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ELEVENLABS_BASE}/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
        )
    return response.json()


@router.websocket("/transcribe/realtime")
async def transcribe_realtime(websocket: WebSocket):
    """
    Realtime speech-to-text via Mistral Voxtral.

    Protocol:
      Client → binary frames : raw PCM (pcm_s16le, 16kHz, mono)
      Client → text "STOP"   : signal end of speech
      Server → {"type": "delta", "text": "..."}  : partial transcript
      Server → {"type": "done"}                  : transcription complete
      Server → {"type": "error", "message": "..."}: error
    """
    await websocket.accept()

    if not MISTRAL_API_KEY:
        await websocket.send_json({"type": "error", "message": "MISTRAL_API_KEY not set"})
        await websocket.close()
        return

    client = Mistral(api_key=MISTRAL_API_KEY)
    audio_queue: asyncio.Queue = asyncio.Queue()

    async def audio_stream():
        """Feed queued PCM chunks into the Voxtral SDK async iterable."""
        while True:
            chunk = await audio_queue.get()
            if chunk is None:   # None = sentinel signalling end of stream
                return
            yield chunk

    async def receive_loop():
        """Pump incoming WebSocket messages into the audio queue."""
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    await audio_queue.put(None)
                    return
                if "bytes" in message and message["bytes"]:
                    await audio_queue.put(message["bytes"])
                elif "text" in message and message.get("text") == "STOP":
                    await audio_queue.put(None)
                    return
        except WebSocketDisconnect:
            await audio_queue.put(None)

    receive_task = asyncio.create_task(receive_loop())

    try:
        audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=VOXTRAL_SAMPLE_RATE)
        async for event in client.audio.realtime.transcribe_stream(
            audio_stream=audio_stream(),
            model=VOXTRAL_MODEL,
            audio_format=audio_format,
            target_streaming_delay_ms=240,
        ):
            if isinstance(event, TranscriptionStreamTextDelta):
                await websocket.send_json({"type": "delta", "text": event.text})
            elif isinstance(event, TranscriptionStreamDone):
                await websocket.send_json({"type": "done"})
                break
            elif isinstance(event, RealtimeTranscriptionError):
                await websocket.send_json({"type": "error", "message": str(event)})
                break
            elif isinstance(event, (RealtimeTranscriptionSessionCreated, UnknownRealtimeEvent)):
                pass  # no-op — session setup and unknown events are safe to ignore
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        receive_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
