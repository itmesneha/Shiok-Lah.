# Shiok Lah! — Graph Nodes

## load_state
Loads the game session and the character bubble from SQLite at the start of every turn. In click mode it handles character switching (auto-exits the previous NPC); in message mode it increments the global step counter and validates that the player is still talking to the right character.

## preflight
Checks terminal conditions before any LLM work runs. Short-circuits to `persist` immediately if the game is already over or the step limit has been exceeded, avoiding wasted API calls.

## gate
A no-op pass-through node that acts as the parallel fan-out point. It has no logic of its own — it exists purely to split execution into two concurrent branches: `character_node` and `suspicion_node`.

## character_node
LLM agent (Mistral Medium) that generates the NPC's in-character spoken reply. It builds a system prompt from the character's persona, current mood, and suspicion level, appends conversation history, then sanitises the response to a hard limit of 2 sentences / 35 words.

## suspicion_node
LLM agent (Mistral Small) that runs in parallel with `character_node` and classifies the player's message intent. It returns a structured JSON delta (0–20) and an intent category (`casual`, `rapport`, `flattery`, `indirect_probe`, `direct_probe`, `deflection`) that reflects how suspicious the player's message is.

## voice_node
Streams the character's response text to ElevenLabs TTS and collects the raw PCM audio bytes. It runs after `character_node` and in parallel with the suspicion chain so audio generation overlaps with game logic rather than adding latency at the end.

## win_check
LLM judge (Mistral Small) that checks whether the character's response inadvertently revealed any of their secrets. It evaluates each unextracted secret individually and marks secrets found when confidence exceeds the configured threshold; sets `game_status = "won"` if all secrets across all NPCs are collected.

## apply_suspicion
Deterministic node that adds the suspicion delta to the running total (clamped 0–1), derives the new NPC mood via the mood engine, and sets `game_over = True` if suspicion crosses the game-over threshold.

## persist
Final fan-in node that writes all state changes to SQLite. Saves conversation history, updated suspicion and mood on the bubble, and any game-level changes (win, loss, active character) — leaves the graph state unchanged.
