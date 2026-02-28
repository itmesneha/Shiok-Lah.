"""
Interactive test for Shiok Lah!
Run the backend first:  uvicorn main:app --reload
Then:                   python test_interactive.py

You play as the food blogger trying to extract secret recipes.
Type your messages, watch the NPCs respond in real-time via SSE.
Text and audio stream in parallel — audio starts playing as first chunk arrives.
"""

import httpx
import asyncio
import json
import uuid
import sys
import time
import base64
import os
import struct
import subprocess
import tempfile
import threading
from config import TIMEOUTS
from models.npcs import NPCS as NPC_DEFS

BASE = "http://127.0.0.1:8000"
SESSION_ID = str(uuid.uuid4())

TOTAL_SECRETS = sum(len(npc["secrets"]) for npc in NPC_DEFS.values())

NPCS = {
    "1": ("uncle_robert", "Uncle Robert -- Char Kway Teow @ Maxwell Food Centre"),
    "2": ("auntie_siti", "Auntie Siti -- Nasi Padang @ Geylang Serai Market"),
    "3": ("ah_kow",      "Ah Kow      -- Bak Chor Mee @ Tiong Bahru Market"),
}


def banner():
    print("\n" + "=" * 60)
    print("  SHIOK LAH!  -- Interactive Playtest")
    print("  Convince the hawker to reveal their secret recipe!")
    print("=" * 60)


def show_npcs():
    print("\n  Choose a hawker stall to visit:\n")
    for key, (_, desc) in NPCS.items():
        print(f"    [{key}]  {desc}")
    print(f"\n    [q]  Quit game")
    print(f"    [s]  Show game state")
    print(f"    [r]  Reset game\n")


def show_status(state: dict):
    suspicion = state.get("suspicion", 0.0)
    mood      = state.get("mood", "?")
    delta     = state.get("suspicion_delta", 0.0)
    reason    = state.get("suspicion_reason", "")
    intent    = state.get("intent_category", "")
    steps     = state.get("steps_remaining", "?")
    secrets   = state.get("secrets_found", 0)
    game_over = state.get("game_over", False)
    win       = state.get("win_detected", False)

    bar_len = 20
    filled  = int(suspicion * bar_len)
    bar     = "#" * filled + "-" * (bar_len - filled)

    sign      = "+" if delta > 0 else ("-" if delta < 0 else " ")
    delta_str = f"{sign}{abs(delta):.2f}"
    intent_str = f"[{intent}]" if intent else "[unknown]"
    reason_str = reason if reason else "--"

    prev_mood    = state.get("prev_mood")
    mood_display = f"{prev_mood} -> {mood} (!)" if prev_mood and prev_mood != mood else mood

    print(f"\n  +---------------------------------------------+")
    print(f"  |  Mood: {mood_display:<20}  Suspicion: [{bar}] {suspicion:.0%}")
    print(f"  |  Delta: {delta_str}  {intent_str}  {reason_str}")
    print(f"  |  Steps left: {steps}   Secrets found: {secrets}/{TOTAL_SECRETS}")
    if game_over:
        if win:
            print(f"  |  YOU WIN! Recipe extracted!")
        else:
            loss = state.get("loss_reason", "kicked out")
            print(f"  |  GAME OVER -- {loss}")
    if state.get("force_leave"):
        print(f"  |  Secret extracted! Conversation closed.")
    print(f"  +---------------------------------------------+")

    return game_over or state.get("force_leave", False)


async def start_game():
    async with httpx.AsyncClient(timeout=TIMEOUTS.DEFAULT) as client:
        r = await client.post(f"{BASE}/api/game/start", json={"session_id": SESSION_ID})
        if r.status_code != 200:
            print(f"  Failed to start game: {r.status_code} {r.text}")
            sys.exit(1)
        data = r.json()
        print(f"\n  Game started! Session: {SESSION_ID[:8]}...")
        print(f"  Max steps: {data['max_steps']}")
        return data


async def talk_to_npc(character_id: str):
    """Click mode — NPC greeting, no message."""
    async with httpx.AsyncClient(timeout=TIMEOUTS.TALK) as client:
        r = await client.post(f"{BASE}/api/game/talk", json={
            "session_id": SESSION_ID,
            "character_id": character_id,
        })
        if r.status_code != 200:
            print(f"  Talk failed: {r.status_code} {r.text}")
            return None
        data = r.json()
        name      = data.get("character_name", character_id)
        dialogue  = data.get("dialogue", "...")
        mood      = data.get("mood", "neutral")
        suspicion = data.get("suspicion", 0.0)
        visit     = data.get("visit_count", 1)

        visit_label = "first visit" if data.get("first_visit") else f"visit #{visit}"
        print(f"\n  [{name}] ({mood}, {visit_label})")
        print(f'  "{dialogue}"')

        bar_len = 20
        filled  = int(suspicion * bar_len)
        bar     = "#" * filled + "-" * (bar_len - filled)
        print(f"  Suspicion: [{bar}] {suspicion:.0%}")

        return data


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 22050) -> bytes:
    """Wrap raw signed-16-bit mono PCM in a WAV container so afplay can play it."""
    num_channels    = 1
    bits_per_sample = 16
    data_size       = len(pcm_bytes)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size,
        b"WAVE",
        b"fmt ", 16,
        1,                                                      # PCM
        num_channels,
        sample_rate,
        sample_rate * num_channels * bits_per_sample // 8,     # byte rate
        num_channels * bits_per_sample // 8,                   # block align
        bits_per_sample,
        b"data", data_size,
    )
    return header + pcm_bytes


def _play_pcm_thread(pcm_data: bytes) -> None:
    """Play raw PCM s16le 22050Hz mono in a background thread.
    Tries afplay+WAV first (always available on macOS), then ffplay.
    """
    # afplay + WAV — most reliable on macOS
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(_pcm_to_wav(pcm_data))
            tmp_path = f.name
        subprocess.run(["afplay", tmp_path], check=False)
        os.unlink(tmp_path)
        return
    except FileNotFoundError:
        pass

    # ffplay fallback — use communicate() to safely write large data
    try:
        proc = subprocess.Popen(
            ["ffplay", "-f", "s16le", "-ar", "22050", "-ac", "1",
             "-nodisp", "-autoexit", "-loglevel", "quiet", "pipe:0"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(input=pcm_data)
    except FileNotFoundError:
        pass


def _play_audio_bytes_fallback(pcm_bytes: bytes) -> None:
    """Write PCM as WAV and play with afplay (macOS). Used when ffplay is absent."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(_pcm_to_wav(pcm_bytes))
            tmp_path = f.name
        subprocess.run(["afplay", tmp_path], check=False)
    except FileNotFoundError:
        pass
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


async def send_message(character_id: str, message: str) -> dict | None:
    """
    SSE streamed response.
    PCM audio chunks arrive first and are collected in memory.
    On [AUDIO_DONE] a background thread starts playing all audio at once,
    then text words drip in — audio and text run concurrently.
    """
    final_state       = None
    pcm_chunks:  list[bytes] = []
    audio_done        = False
    audio_chunk_count = 0
    audio_byte_count  = 0

    npc_name = next(
        (desc.split(" -- ")[0] for _, (cid, desc) in NPCS.items() if cid == character_id),
        character_id,
    )

    print(f"\n  {npc_name}: ", end="", flush=True)

    t_start       = time.perf_counter()
    t_first_token = None

    async with httpx.AsyncClient(timeout=TIMEOUTS.MESSAGE) as client:
        async with client.stream(
            "POST",
            f"{BASE}/api/game/message",
            json={
                "session_id":   SESSION_ID,
                "character_id": character_id,
                "message":      message,
                "voice_enabled": True,
            },
        ) as response:
            if response.status_code != 200:
                print(f"\n  Message failed: {response.status_code}")
                return None

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)
                    if not event.startswith("data: "):
                        continue
                    data = event[6:]

                    if data.startswith("[ERROR]"):
                        print(f"\n  {data}")
                        return None

                    elif data.startswith("[STATE]"):
                        final_state = json.loads(data[8:])

                    elif data == "[DONE]":
                        pass

                    elif data.startswith("[AUDIO] "):
                        audio_chunk = base64.b64decode(data[8:])
                        pcm_chunks.append(audio_chunk)
                        audio_chunk_count += 1
                        audio_byte_count  += len(audio_chunk)

                    elif data == "[AUDIO_DONE]":
                        # All PCM received — start playback in background thread.
                        # Text words arrive next; they drip while audio plays.
                        audio_done = True
                        if pcm_chunks:
                            all_pcm = b"".join(pcm_chunks)
                            threading.Thread(
                                target=_play_pcm_thread,
                                args=(all_pcm,),
                                daemon=True,
                            ).start()

                    else:
                        # Text word
                        if t_first_token is None:
                            t_first_token = time.perf_counter()
                        print(data, end="", flush=True)

    if audio_done and pcm_chunks:
        print(f"\n  [audio: {audio_byte_count // 1024}KB PCM playing]", end="")
    elif not audio_done and not pcm_chunks:
        print(f"\n  [audio: none — check ELEVENLABS_API_KEY and voice_id in logs]", end="")

    t_total = time.perf_counter() - t_start
    ttft    = f"{t_first_token - t_start:.2f}s" if t_first_token else "N/A"
    print(f"\n  [TTFT: {ttft} | total: {t_total:.2f}s]")

    return final_state


async def leave_npc(character_id: str):
    async with httpx.AsyncClient(timeout=TIMEOUTS.DEFAULT) as client:
        await client.post(f"{BASE}/api/game/leave", json={
            "session_id":   SESSION_ID,
            "character_id": character_id,
        })


async def show_game_state():
    async with httpx.AsyncClient(timeout=TIMEOUTS.DEFAULT) as client:
        r = await client.get(f"{BASE}/api/game/state/{SESSION_ID}")
        if r.status_code != 200:
            print(f"  State fetch failed: {r.status_code}")
            return
        data = r.json()
        print(f"\n  -- Game State --")
        print(f"  Step: {data['global_step']}/{data['max_steps']}  "
              f"Status: {data['game_status']}  Secrets: {data['secrets_found']}/{TOTAL_SECRETS}")
        for c in data.get("characters", []):
            bar_len  = 15
            filled   = int(c["suspicion"] * bar_len)
            bar      = "#" * filled + "-" * (bar_len - filled)
            extracted = "YES" if c["secret_extracted"] else "no"
            print(f"    {c['name']:<18} Mood: {c['mood']:<12} "
                  f"Suspicion: [{bar}] {c['suspicion']:.0%}  "
                  f"Secret: {extracted}  Visits: {c['visit_count']}")


async def reset_game():
    async with httpx.AsyncClient(timeout=TIMEOUTS.DEFAULT) as client:
        r = await client.post(f"{BASE}/api/game/reset", json={"session_id": SESSION_ID})
        if r.status_code == 200:
            print("  Game reset!")
        else:
            print(f"  Reset failed: {r.status_code}")


async def conversation_loop(character_id: str):
    """Chat loop with a single NPC."""
    talk_data = await talk_to_npc(character_id)
    if not talk_data:
        return

    if talk_data.get("game_status", "active") != "active":
        print(f"\n  Game is {talk_data['game_status']}. Returning to menu.")
        return

    npc_name = talk_data.get("character_name", character_id)

    while True:
        print(f"\n  (Type your message to {npc_name}, or 'back' to leave)\n")
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("back", "leave", "exit"):
            await leave_npc(character_id)
            print(f"\n  You walk away from {npc_name}'s stall...")
            break

        state = await send_message(character_id, user_input)
        if state:
            game_over = show_status(state)
            if game_over:
                break
        else:
            print("  (no state returned)")


async def main():
    banner()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUTS.DEFAULT) as client:
            r = await client.get(f"{BASE}/")
            if r.status_code != 200:
                print(f"  Server not healthy: {r.status_code}")
                sys.exit(1)
    except httpx.ConnectError:
        print(f"\n  Cannot connect to {BASE}")
        print(f"  Start the backend first: uvicorn main:app --reload\n")
        sys.exit(1)

    await start_game()

    while True:
        show_npcs()
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if choice == "q":
            print("\n  Thanks for playing!")
            break
        elif choice == "s":
            await show_game_state()
        elif choice == "r":
            await reset_game()
        elif choice in NPCS:
            character_id, _ = NPCS[choice]
            await conversation_loop(character_id)
        else:
            print("  Invalid choice. Try 1, 2, 3, q, s, or r.")

    print()


if __name__ == "__main__":
    asyncio.run(main())
