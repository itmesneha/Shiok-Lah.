extends CanvasLayer

var npc_id: String = ""
var is_waiting = false  # prevent spamming requests
var current_mood: String = "neutral"
var voice_player: AudioStreamPlayer

@onready var dialogue_text = $DialoguePanel/VBoxContainer/DialogueText
@onready var npc_name_label = $DialoguePanel/VBoxContainer/NPCNameLabel
@onready var player_input = $DialoguePanel/VBoxContainer/PlayerInput
@onready var suspicion_segments = $SuspicionBar/SuspicionSegments
@onready var suspicion_label = $SuspicionBar/SuspicionLabel
@onready var mood_indicator = $MoodIndicator
@onready var npc_portrait = $NPCPortrait

const NPC_NAMES = {
	"uncle_robert": "Uncle Robert",
	"auntie_siti": "Auntie Siti",
	"ah_kow": "Ah Kow"
}
const SUSPICION_SEGMENT_COUNT = 10
const NPC_TYPEWRITER_DELAY := 0.02
const API_HOST := "localhost"
const API_PORT := 8000
const API_MESSAGE_PATH := "/api/game/message"

func _sanitize_display_text(text: String) -> String:
	# Remove wrapping quote glyphs that sometimes leak from model output.
	return text.replace("\"", "").replace("“", "").replace("”", "")

func _ready():
	var npc_name = NPC_NAMES.get(npc_id, npc_id)
	npc_name_label.text = npc_name
	mood_indicator.set_actor_name(npc_name)
	mood_indicator.set_mood(current_mood)
	voice_player = AudioStreamPlayer.new()
	voice_player.name = "NPCVoicePlayer"
	add_child(voice_player)
	_set_suspicion_display(0.0)
	player_input.text_submitted.connect(_on_message_submitted)
	_set_waiting(true)
	
	# Ensure backend session exists, then activate this NPC via /talk.
	_initialize_dialogue_session()

func _input(event):
	if Input.is_action_just_pressed("ui_cancel"):
		close_dialogue()

func _on_message_submitted(message: String):
	if message.strip_edges() == "" or is_waiting:
		return
	player_input.clear()
	_set_waiting(true)
	
	# Show player message
	dialogue_text.append_text("\n[color=cyan]You:[/color] " + message + "\n")
	
	await _send_message(message)

func _send_message(message: String):
	var body = JSON.stringify({
		"session_id": GameState.session_id,
		"character_id": npc_id,
		"message": message,
		"voice_enabled": true
	})

	var client = HTTPClient.new()
	var error = client.connect_to_host(API_HOST, API_PORT)
	if error != OK:
		dialogue_text.append_text("\n[color=red]Connection error. Is the backend running?[/color]\n")
		_re_enable_input()
		return

	while client.get_status() == HTTPClient.STATUS_RESOLVING or client.get_status() == HTTPClient.STATUS_CONNECTING:
		client.poll()
		await get_tree().process_frame

	if client.get_status() != HTTPClient.STATUS_CONNECTED:
		dialogue_text.append_text("\n[color=red]Connection error. Is the backend running?[/color]\n")
		_re_enable_input()
		return

	error = client.request(
		HTTPClient.METHOD_POST,
		API_MESSAGE_PATH,
		["Content-Type: application/json", "Accept: text/event-stream"],
		body
	)
	if error != OK:
		dialogue_text.append_text("\n[color=red]Could not send message request.[/color]\n")
		client.close()
		_re_enable_input()
		return

	while client.get_status() == HTTPClient.STATUS_REQUESTING:
		client.poll()
		await get_tree().process_frame

	var response_code = client.get_response_code()
	if response_code != 200:
		dialogue_text.append_text("\n[color=red]Server error: " + str(response_code) + "[/color]\n")
		client.close()
		_re_enable_input()
		return

	var sse_buffer = ""
	var dialogue = ""
	var state = {}
	var audio_bytes = PackedByteArray()
	var line_open = false
	var stream_done = false

	while client.get_status() == HTTPClient.STATUS_BODY and not stream_done:
		client.poll()
		var chunk = client.read_response_body_chunk()
		if chunk.size() == 0:
			await get_tree().process_frame
			continue

		sse_buffer += chunk.get_string_from_utf8()
		while sse_buffer.find("\n") != -1:
			var split_index = sse_buffer.find("\n")
			var line = sse_buffer.substr(0, split_index)
			sse_buffer = sse_buffer.substr(split_index + 1)
			if line.ends_with("\r"):
				line = line.substr(0, line.length() - 1)
			if line == "" or not line.begins_with("data: "):
				continue
			var data = _sanitize_display_text(line.substr(6))
			if data.begins_with("[STATE]"):
				var json = JSON.new()
				if json.parse(data.substr(8)) == OK:
					state = json.get_data()
			elif data.begins_with("[AUDIO]"):
				var b64 = data.substr(8).strip_edges()
				var audio_chunk = Marshalls.base64_to_raw(b64)
				if audio_chunk.size() > 0:
					audio_bytes.append_array(audio_chunk)
			elif data.begins_with("[ERROR]"):
				dialogue_text.append_text("\n[color=red]" + data.substr(7) + "[/color]\n")
			elif data == "[DONE]":
				stream_done = true
				break
			else:
				if not line_open:
					dialogue_text.append_text("\n[color=yellow]" + NPC_NAMES.get(npc_id, npc_id) + ":[/color] ")
					line_open = true
				dialogue_text.append_text(data)
				dialogue += data

	# Handle final partial line (if server closes without trailing newline).
	var trailing = sse_buffer.strip_edges()
	if trailing.begins_with("data: "):
		var trailing_data = _sanitize_display_text(trailing.substr(6))
		if trailing_data != "[DONE]" and not trailing_data.begins_with("[STATE]") and not trailing_data.begins_with("[AUDIO]") and not trailing_data.begins_with("[ERROR]"):
			if not line_open:
				dialogue_text.append_text("\n[color=yellow]" + NPC_NAMES.get(npc_id, npc_id) + ":[/color] ")
				line_open = true
			dialogue_text.append_text(trailing_data)
			dialogue += trailing_data

	if line_open:
		dialogue_text.append_text("\n")

	# Current backend sends MP3 as chunked bytes; play once fully assembled.
	if audio_bytes.size() > 0:
		_play_audio_bytes(audio_bytes)
	elif dialogue.strip_edges() != "":
		var mood_for_voice = str(state.get("mood", current_mood))
		_request_voice_line(dialogue.strip_edges(), mood_for_voice)
	
	# Update UI with new game state
	if state.size() > 0:
		_update_game_state(state)

	client.close()
	
	_re_enable_input()

func _update_game_state(state: Dictionary):
	# Update suspicion bar
	var suspicion = float(state.get("suspicion", state.get("new_suspicion", 0.0)))
	_set_suspicion_display(suspicion)
	
	# Flash red if suspicion spiked
	if suspicion > 0.6:
		_flash_suspicion_bar()
	
	# Update mood
	var mood = state.get("mood", state.get("new_mood", "neutral"))
	_set_mood(mood)

	# Normalize win key for existing GameState.gd flow.
	if state.has("win_detected") and not state.has("win"):
		state["win"] = state.get("win_detected", false)
	
	# Tell GameState to update
	GameState.update_npc_state(npc_id, state)
	
	# Handle win/lose
	if state.get("game_over", false):
		await get_tree().create_timer(1.5).timeout
		if state.get("win", false):
			_on_win()
		else:
			_on_lose()

func _on_win():
	dialogue_text.append_text("\n[color=green]🎉 You got the secret! The recipe has been revealed![/color]\n")
	await get_tree().create_timer(2.0).timeout
	close_dialogue()

func _on_lose():
	dialogue_text.append_text("\n[color=red]💀 Uncle Robert threw you out![/color]\n")
	await get_tree().create_timer(2.0).timeout
	close_dialogue()

func _flash_suspicion_bar():
	# Quick red flash to signal danger
	var tween = create_tween()
	tween.tween_property(suspicion_segments, "modulate", Color(1.0, 0.65, 0.65), 0.1)
	tween.tween_property(suspicion_segments, "modulate", Color.WHITE, 0.3)

func _initialize_dialogue_session():
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_state_checked.bind(http))
	http.request(
		"http://localhost:8000/api/game/state/" + GameState.session_id,
		["Content-Type: application/json"],
		HTTPClient.METHOD_GET
	)

func _on_state_checked(result, response_code, headers, body, http):
	http.queue_free()
	if response_code != 200:
		_start_game()
		return
	var json = JSON.new()
	json.parse(body.get_string_from_utf8())
	var game_state = json.get_data()
	if typeof(game_state) != TYPE_DICTIONARY:
		_start_game()
		return
	if game_state.has("error"):
		_start_game()
		return
	_apply_state_snapshot(game_state)
	_start_talk()

func _start_game():
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_game_started.bind(http))
	var body = JSON.stringify({
		"session_id": GameState.session_id
	})
	http.request(
		"http://localhost:8000/api/game/start",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		body
	)

func _on_game_started(result, response_code, headers, body, http):
	http.queue_free()
	if response_code != 200:
		dialogue_text.append_text("\n[color=red]Could not start game session (" + str(response_code) + ").[/color]\n")
		_set_waiting(false)
		return
	_start_talk()

func _start_talk():
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_talk_started.bind(http))
	var body = JSON.stringify({
		"session_id": GameState.session_id,
		"character_id": npc_id
	})
	http.request(
		"http://localhost:8000/api/game/talk",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		body
	)

func _on_talk_started(result, response_code, headers, body, http):
	http.queue_free()
	if response_code != 200:
		dialogue_text.append_text("\n[color=red]Could not start conversation (" + str(response_code) + ").[/color]\n")
		_set_waiting(false)
		return
	var json = JSON.new()
	json.parse(body.get_string_from_utf8())
	var data = json.get_data()
	if typeof(data) != TYPE_DICTIONARY:
		_set_waiting(false)
		return
	
	# /talk returns immediate dialogue opener in JSON.
	var opener = str(data.get("dialogue", ""))
	
	# /talk also returns mood + suspicion for this character bubble.
	_set_suspicion_display(float(data.get("suspicion", 0.0)))
	var mood = data.get("mood", "neutral")
	_set_mood(mood)
	if opener != "":
		await _present_npc_reply(opener, PackedByteArray(), str(mood))
	_set_waiting(false)

func _apply_state_snapshot(game_state: Dictionary):
	var characters = game_state.get("characters", [])
	if typeof(characters) != TYPE_ARRAY:
		return
	for character in characters:
		if typeof(character) == TYPE_DICTIONARY and character.get("character_id", "") == npc_id:
			_set_suspicion_display(float(character.get("suspicion", 0.0)))
			var mood = character.get("mood", "neutral")
			_set_mood(mood)
			return

func _re_enable_input():
	_set_waiting(false)

func _set_waiting(waiting: bool):
	is_waiting = waiting
	player_input.editable = not waiting
	mood_indicator.set_waiting(waiting)
	if not waiting:
		player_input.grab_focus()

func _set_mood(mood: String):
	current_mood = mood
	mood_indicator.set_mood(mood)

func _set_suspicion_display(suspicion: float):
	var clamped = clampf(suspicion, 0.0, 1.0)
	var percent = int(round(clamped * 100.0))
	_render_suspicion_segments(clamped)
	suspicion_label.text = "Suspicion: " + _suspicion_tier(clamped) + " (" + str(percent) + "%)"
	suspicion_label.modulate = _suspicion_color(clamped)

func _suspicion_tier(suspicion: float) -> String:
	if suspicion < 0.25:
		return "Calm"
	if suspicion < 0.5:
		return "Guarded"
	if suspicion < 0.75:
		return "Alert"
	return "Danger"

func _suspicion_color(suspicion: float) -> Color:
	if suspicion < 0.25:
		return Color(0.45, 0.86, 0.57)
	if suspicion < 0.5:
		return Color(0.95, 0.83, 0.42)
	if suspicion < 0.75:
		return Color(1.0, 0.63, 0.33)
	return Color(0.96, 0.36, 0.36)

func _render_suspicion_segments(suspicion: float):
	var filled = int(round(suspicion * SUSPICION_SEGMENT_COUNT))
	var on_color = _suspicion_color(suspicion)
	var off_color = Color(0.15, 0.15, 0.15, 0.95)
	var count = suspicion_segments.get_child_count()
	for i in range(count):
		var seg = suspicion_segments.get_child(i)
		if seg is ColorRect:
			seg.color = on_color if i < filled else off_color

func _play_audio_bytes(audio_bytes: PackedByteArray):
	if audio_bytes.size() == 0:
		return
	var stream = AudioStreamMP3.new()
	stream.data = audio_bytes
	voice_player.stop()
	voice_player.stream = stream
	voice_player.play()

func _present_npc_reply(text: String, audio_bytes: PackedByteArray, mood: String):
	if text.strip_edges() == "":
		return
	if audio_bytes.size() > 0:
		_play_audio_bytes(audio_bytes)
	else:
		# Fire TTS request before text reveal to overlap network + UI time.
		_request_voice_line(text, mood)
	await _append_npc_typewriter(text)

func _append_npc_typewriter(text: String):
	var npc_name = NPC_NAMES.get(npc_id, npc_id)
	var clean_text = _sanitize_display_text(text)
	dialogue_text.append_text("\n[color=yellow]" + npc_name + ":[/color] ")
	for i in range(clean_text.length()):
		var ch = clean_text.substr(i, 1)
		dialogue_text.append_text(ch)
		if ch != " ":
			await get_tree().create_timer(NPC_TYPEWRITER_DELAY).timeout
	dialogue_text.append_text("\n")

func _request_voice_line(text: String, mood: String):
	if text.strip_edges() == "":
		return
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_voice_response.bind(http))
	var body = JSON.stringify({
		"text": text,
		"npc_id": npc_id,
		"mood": mood
	})
	http.request(
		"http://localhost:8000/api/voice/speak",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		body
	)

func _on_voice_response(result, response_code, headers, body, http):
	http.queue_free()
	if response_code != 200:
		return
	_play_audio_bytes(body)

func close_dialogue():
	DialogueManager.end_conversation()
	queue_free()
