extends CanvasLayer

var npc_id: String = ""
var is_waiting = false  # prevent spamming requests
var current_mood: String = "neutral"
var voice_player: AudioStreamPlayer
var voice_stream: AudioStreamGenerator
var voice_playback: AudioStreamGeneratorPlayback
var pcm_carry_byte: int = -1
var pcm_pending_samples: Array[float] = []
var pcm_sample_read_index: int = 0
var pcm_stream_active: bool = false

# ── Voice input (Voxtral realtime transcription) ──
var ws := WebSocketPeer.new()
var mic_capture: AudioEffectCapture
var mic_player: AudioStreamPlayer
var is_recording: bool = false
var transcript: String = ""
var ptt_submit_pending: bool = false
var ws_connect_start_ms: int = 0

const VOXTRAL_SAMPLE_RATE := 16000
const WS_URL := "ws://127.0.0.1:8000/api/voice/transcribe/realtime"

@onready var dialogue_text = $DialoguePanel/VBoxContainer/DialogueText
@onready var npc_name_label = $DialoguePanel/VBoxContainer/NPCNameLabel
@onready var player_input = $DialoguePanel/VBoxContainer/PlayerInput
@onready var suspicion_segments = $SuspicionBar/SuspicionSegments
@onready var suspicion_label = $SuspicionBar/SuspicionLabel
@onready var mood_indicator = $MoodIndicator

const NPC_NAMES = {
	"uncle_robert": "Uncle Robert",
	"auntie_siti": "Auntie Siti",
	"ah_kow": "Ah Kow"
}
const SUSPICION_SEGMENT_COUNT = 10
const NPC_TYPEWRITER_DELAY := 0.02
const API_HOST := "127.0.0.1"
const API_PORT := 8000
const API_MESSAGE_PATH := "/api/game/message"
const API_HISTORY_PATH := "/api/game/history/"
const GAME_OVER_POPUP_SCENE := preload("res://scenes/GameOverPopup.tscn")
const START_MENU_SCENE_PATH := "res://scenes/start_screen.tscn"
const TTS_PCM_SAMPLE_RATE := 22050
const TTS_BUFFER_SECONDS := 0.2
const TTS_PCM_BIG_ENDIAN := false
const SECRET_POPUP_SECONDS := 1.6

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
	set_process(true)
	_set_suspicion_display(0.0)
	player_input.text_submitted.connect(_on_message_submitted)
	player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."
	_set_waiting(true)
	_setup_mic_bus()

	# Ensure backend session exists, then activate this NPC via /talk.
	_initialize_dialogue_session()

func _setup_mic_bus():
	ProjectSettings.set_setting("audio/driver/enable_input", true)
	# Reuse the existing bus if it was left over from a previous dialogue session.
	# Always adding a new bus means mic_player routes to the first "MicCapture"
	# while mic_capture ends up on the latest one — different buses, so no audio captured.
	var bus_idx = AudioServer.get_bus_index("MicCapture")
	if bus_idx == -1:
		bus_idx = AudioServer.bus_count
		AudioServer.add_bus(bus_idx)
		AudioServer.set_bus_name(bus_idx, "MicCapture")
		AudioServer.set_bus_mute(bus_idx, true)

	# Replace the capture effect so we get a clean buffer each session.
	while AudioServer.get_bus_effect_count(bus_idx) > 0:
		AudioServer.remove_bus_effect(bus_idx, 0)
	var effect = AudioEffectCapture.new()
	effect.buffer_length = 0.1
	AudioServer.add_bus_effect(bus_idx, effect)
	mic_capture = effect

	mic_player = AudioStreamPlayer.new()
	mic_player.stream = AudioStreamMicrophone.new()
	mic_player.bus = "MicCapture"
	add_child(mic_player)
	mic_player.play()

func _start_recording():
	if is_waiting or is_recording:
		return
	ptt_submit_pending = false
	transcript = ""
	player_input.text = ""
	player_input.placeholder_text = "🎤 Listening..."
	is_recording = true
	if mic_capture:
		mic_capture.clear_buffer()
	# Close any existing connection before opening a new one.
	# Leaving the old peer open causes the new handshake to hang in CONNECTING.
	var old_state = ws.get_ready_state()
	if old_state != WebSocketPeer.STATE_CLOSED:
		ws.close()
	ws = WebSocketPeer.new()
	ws_connect_start_ms = Time.get_ticks_msec()
	ws.connect_to_url(WS_URL)

func _stop_recording():
	is_recording = false
	player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."
	if ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		ws.send_text("STOP")
	# If still CONNECTING, _process() will send STOP as soon as the handshake completes.

func _input(event):
	if Input.is_action_just_pressed("ui_cancel"):
		close_dialogue()
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F9:
		await _show_game_over_popup({
			"game_over": true,
			"win": false,
			"loss_reason": "Manual test popup"
		})
	# Push-to-talk: hold Shift+Space to record, release to auto-submit transcript.
	# shift_pressed is only checked on press; release works regardless of Shift state
	# so that releasing Shift before Space still stops recording correctly.
	if event is InputEventKey and event.keycode == KEY_SPACE and not event.echo and not is_waiting:
		if event.pressed and event.shift_pressed and not is_recording:
			_start_recording()
			get_viewport().set_input_as_handled()
		elif not event.pressed and is_recording:
			_stop_recording()
			ptt_submit_pending = true
			player_input.placeholder_text = "Processing..."
			get_viewport().set_input_as_handled()

func _on_message_submitted(message: String):
	if message.strip_edges() == "" or is_waiting:
		return
	ptt_submit_pending = false
	_stop_recording()
	transcript = ""
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
	var got_audio = false
	var line_open = false
	var stream_done = false
	pcm_carry_byte = -1

	while client.get_status() == HTTPClient.STATUS_BODY and not stream_done:
		client.poll()
		var chunk = client.read_response_body_chunk()
		if chunk.size() == 0:
			await get_tree().process_frame
			continue

		sse_buffer += chunk.get_string_from_utf8()
		var parsed_lines: int = 0
		while sse_buffer.find("\n") != -1:
			var split_index = sse_buffer.find("\n")
			var line = sse_buffer.substr(0, split_index)
			sse_buffer = sse_buffer.substr(split_index + 1)
			parsed_lines += 1
			if line.ends_with("\r"):
				line = line.substr(0, line.length() - 1)
			if line == "" or not line.begins_with("data: "):
				continue
			var raw_data = line.substr(6)
			if raw_data.begins_with("[STATE]"):
				var json = JSON.new()
				if json.parse(raw_data.substr(8)) == OK:
					state = json.get_data()
			elif raw_data.begins_with("[AUDIO] "):
				var b64 = raw_data.substr(8).strip_edges()
				var audio_chunk = Marshalls.base64_to_raw(b64)
				if audio_chunk.size() > 0:
					got_audio = true
					_queue_pcm_chunk(audio_chunk)
			elif raw_data == "[AUDIO_DONE]":
				pass
			elif raw_data.begins_with("[ERROR]"):
				dialogue_text.append_text("\n[color=red]" + raw_data.substr(7) + "[/color]\n")
			elif raw_data == "[DONE]":
				stream_done = true
				break
			else:
				var data = _sanitize_display_text(raw_data)
				if not line_open:
					dialogue_text.append_text("\n[color=yellow]" + NPC_NAMES.get(npc_id, npc_id) + ":[/color] ")
					line_open = true
				dialogue_text.append_text(data)
				dialogue += data

			if parsed_lines % 8 == 0:
				await get_tree().process_frame

		# Yield each network chunk so _process() can push queued PCM in real time.
		await get_tree().process_frame

	# Handle final partial line (if server closes without trailing newline).
	var trailing = sse_buffer.strip_edges()
	if trailing.begins_with("data: "):
		var trailing_raw = trailing.substr(6)
		if trailing_raw != "[DONE]" and trailing_raw != "[AUDIO_DONE]" and not trailing_raw.begins_with("[STATE]") and not trailing_raw.begins_with("[AUDIO]") and not trailing_raw.begins_with("[ERROR]"):
			var trailing_data = _sanitize_display_text(trailing_raw)
			if not line_open:
				dialogue_text.append_text("\n[color=yellow]" + NPC_NAMES.get(npc_id, npc_id) + ":[/color] ")
				line_open = true
			dialogue_text.append_text(trailing_data)
			dialogue += trailing_data

	if line_open:
		dialogue_text.append_text("\n")

	# Fallback: if no streamed audio arrived, request /voice/speak.
	if not got_audio and dialogue.strip_edges() != "":
		var mood_for_voice = str(state.get("mood", current_mood))
		_request_voice_line(dialogue.strip_edges(), mood_for_voice)
	
	# Update UI with new game state
	if state.size() > 0:
		_update_game_state(state)
		if is_queued_for_deletion():
			client.close()
			return

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
	var secret_extracted := bool(state.get("secret_extracted", false))

	# Tell GameState to update
	GameState.update_npc_state(npc_id, state)
	
	# Handle terminal state (backend payload can vary by route/version).
	var is_terminal = bool(state.get("game_over", false))
	var game_status = str(state.get("game_status", "active"))
	if game_status == "lost" or game_status == "won" or game_status == "game_over":
		is_terminal = true
	if state.get("loss_reason", null) != null:
		is_terminal = true
	if suspicion >= 0.95:
		is_terminal = true

	if is_terminal:
		await _show_game_over_popup(state)
		return

	if secret_extracted:
		await _show_secret_extracted_popup()
		close_dialogue()
		return

func _show_game_over_popup(state: Dictionary):
	var popup = GAME_OVER_POPUP_SCENE.instantiate()
	get_tree().root.add_child(popup)
	var did_win = str(state.get("game_status", "")) == "won" or bool(state.get("win", false))
	var loss_reason = str(state.get("loss_reason", ""))
	popup.configure(did_win, loss_reason)
	var go_to_menu = await popup.action_selected
	_clear_dialogue_ui()
	await _reset_current_round()
	if go_to_menu:
		close_dialogue()
		get_tree().change_scene_to_file(START_MENU_SCENE_PATH)
		return
	close_dialogue()

func _reset_current_round():
	var http = HTTPRequest.new()
	add_child(http)
	var body = JSON.stringify({
		"session_id": GameState.session_id
	})
	var error = http.request(
		"http://127.0.0.1:8000/api/game/reset",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		body
	)
	if error != OK:
		http.queue_free()
		dialogue_text.append_text("\n[color=red]Could not reset the round.[/color]\n")
		return
	var response = await http.request_completed
	http.queue_free()
	var response_code = int(response[1])
	if response_code != 200:
		dialogue_text.append_text("\n[color=red]Reset failed (" + str(response_code) + ").[/color]\n")
		return
	GameState.collected_secrets.clear()
	GameState.npc_states.clear()

func _flash_suspicion_bar():
	# Quick red flash to signal danger
	var tween = create_tween()
	tween.tween_property(suspicion_segments, "modulate", Color(1.0, 0.65, 0.65), 0.1)
	tween.tween_property(suspicion_segments, "modulate", Color.WHITE, 0.3)

func _show_secret_extracted_popup():
	var existing = get_node_or_null("SecretExtractedToast")
	if existing != null:
		existing.queue_free()

	var toast := PanelContainer.new()
	toast.name = "SecretExtractedToast"
	toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast.anchor_left = 0.5
	toast.anchor_right = 0.5
	toast.anchor_top = 0.0
	toast.anchor_bottom = 0.0
	toast.offset_left = -260
	toast.offset_right = 260
	toast.offset_top = 74
	toast.offset_bottom = 126
	toast.modulate = Color(1, 1, 1, 0)

	var label := Label.new()
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.text = "Congratulations! Secret extracted from " + NPC_NAMES.get(npc_id, npc_id) + "'s stall."
	var settings := LabelSettings.new()
	var font := load("res://assets/fonts/Minecraft.ttf") as Font
	if font != null:
		settings.font = font
	settings.font_size = 16
	settings.font_color = Color(0.96, 0.91, 0.76, 1)
	settings.outline_size = 2
	settings.outline_color = Color(0.07, 0.07, 0.07, 1)
	label.label_settings = settings
	toast.add_child(label)

	var host := get_tree().root.get_node_or_null("Game/HintOverlay")
	if host == null:
		add_child(toast)
	else:
		host.add_child(toast)

	var tween = create_tween()
	tween.tween_property(toast, "modulate:a", 1.0, 0.15)
	tween.tween_interval(SECRET_POPUP_SECONDS)
	tween.tween_property(toast, "modulate:a", 0.0, 0.25)
	await tween.finished
	if is_instance_valid(toast):
		toast.queue_free()

func _initialize_dialogue_session():
	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_state_checked.bind(http))
	http.request(
		"http://127.0.0.1:8000/api/game/state/" + GameState.session_id,
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

	# If session is already terminal, show popup immediately.
	var loaded_status = str(game_state.get("game_status", "active"))
	if loaded_status != "active":
		await _show_game_over_popup({
			"game_over": true,
			"win": loaded_status == "won",
			"loss_reason": "Round already ended. Restart to play again."
		})
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
		"http://127.0.0.1:8000/api/game/start",
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
		"http://127.0.0.1:8000/api/game/talk",
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
	var first_visit = bool(data.get("first_visit", true))

	# /talk also returns mood + suspicion for this character bubble.
	_set_suspicion_display(float(data.get("suspicion", 0.0)))
	var mood = data.get("mood", "neutral")
	_set_mood(mood)

	# Only show history on return visits. The current opener is already persisted
	# as the last history entry, so exclude it — it will be shown by _present_npc_reply.
	if not first_visit:
		await _load_and_display_history(true)

	if opener != "":
		await _present_npc_reply(opener, PackedByteArray(), str(mood))
	_re_enable_input()

func _load_and_display_history(exclude_last: bool = false):
	var client = HTTPClient.new()
	var error = client.connect_to_host(API_HOST, API_PORT)
	if error != OK:
		return

	while client.get_status() == HTTPClient.STATUS_RESOLVING or client.get_status() == HTTPClient.STATUS_CONNECTING:
		client.poll()
		await get_tree().process_frame

	if client.get_status() != HTTPClient.STATUS_CONNECTED:
		return

	error = client.request(
		HTTPClient.METHOD_GET,
		API_HISTORY_PATH + GameState.session_id + "/" + npc_id,
		["Accept: application/json"]
	)
	if error != OK:
		client.close()
		return

	while client.get_status() == HTTPClient.STATUS_REQUESTING:
		client.poll()
		await get_tree().process_frame

	if client.get_response_code() != 200:
		client.close()
		return

	var body_bytes = PackedByteArray()
	while client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		var chunk = client.read_response_body_chunk()
		if chunk.size() > 0:
			body_bytes.append_array(chunk)
		else:
			await get_tree().process_frame

	client.close()

	var json = JSON.new()
	if json.parse(body_bytes.get_string_from_utf8()) != OK:
		return
	var data = json.get_data()
	if typeof(data) != TYPE_DICTIONARY:
		return

	var history = data.get("history", [])
	if typeof(history) != TYPE_ARRAY or history.size() == 0:
		return

	# Drop the last entry when it is the current opener already saved by persist.
	var display_history: Array = history.slice(0, history.size() - 1) if exclude_last else history
	if display_history.size() == 0:
		return

	var npc_name = NPC_NAMES.get(npc_id, npc_id)
	dialogue_text.append_text(" Previous conversation \n")
	for entry in display_history:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var role = str(entry.get("role", ""))
		var content = _sanitize_display_text(str(entry.get("content", "")))
		if content == "":
			continue
		if role == "user":
			dialogue_text.append_text("[color=cyan]You:[/color] " + content + "\n")
		elif role == "assistant":
			dialogue_text.append_text("[color=yellow]" + npc_name + ":[/color] " + content + "\n")
	dialogue_text.append_text(" Continuing... \n")


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
	_play_pcm_bytes(audio_bytes)

func _ensure_pcm_stream():
	if voice_stream == null:
		voice_stream = AudioStreamGenerator.new()
		voice_stream.mix_rate = TTS_PCM_SAMPLE_RATE
		voice_stream.buffer_length = TTS_BUFFER_SECONDS
	if voice_player.stream != voice_stream:
		voice_player.stream = voice_stream
	if not voice_player.playing:
		voice_player.play()
	voice_playback = voice_player.get_stream_playback() as AudioStreamGeneratorPlayback

func _on_npc_audio_finished():
	if mic_capture:
		mic_capture.clear_buffer()

func _queue_pcm_chunk(pcm_chunk: PackedByteArray):
	if pcm_chunk.size() == 0:
		return
	_ensure_pcm_stream()
	if not pcm_stream_active and mic_capture:
		mic_capture.clear_buffer()  # clear before NPC starts speaking
	pcm_stream_active = true
	_decode_and_queue_pcm(pcm_chunk)
	_drain_pcm_queue()

func _decode_and_queue_pcm(pcm_chunk: PackedByteArray):
	var index_byte: int = 0

	if pcm_carry_byte >= 0 and pcm_chunk.size() > 0:
		var carry_sample: int = _decode_pcm_sample(pcm_carry_byte, int(pcm_chunk[0]))
		pcm_pending_samples.append(clampf(float(carry_sample) / 32768.0, -1.0, 1.0))
		pcm_carry_byte = -1
		index_byte = 1

	var remainder: int = (pcm_chunk.size() - index_byte) % 2
	var end_exclusive: int = pcm_chunk.size() - remainder
	if remainder == 1:
		pcm_carry_byte = int(pcm_chunk[pcm_chunk.size() - 1])

	while index_byte + 1 < end_exclusive:
		var sample: int = _decode_pcm_sample(int(pcm_chunk[index_byte]), int(pcm_chunk[index_byte + 1]))
		pcm_pending_samples.append(clampf(float(sample) / 32768.0, -1.0, 1.0))
		index_byte += 2

func _process(_delta: float):
	var was_streaming = pcm_stream_active
	if pcm_stream_active:
		_drain_pcm_queue()
	if was_streaming and not pcm_stream_active:
		_on_npc_audio_finished()

	# ── Voxtral WebSocket ──
	var pre_poll_state = ws.get_ready_state()
	if pre_poll_state == WebSocketPeer.STATE_CLOSED:
		if is_recording:
			is_recording = false
		if ptt_submit_pending:
			ptt_submit_pending = false
			var pending_text = player_input.text.strip_edges()
			if pending_text != "":
				_on_message_submitted(pending_text)
			else:
				player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."
		return

	ws.poll()
	var ws_state = ws.get_ready_state()  # re-read after poll so state is current

	if pre_poll_state == WebSocketPeer.STATE_CONNECTING and ws_state == WebSocketPeer.STATE_OPEN:
		# Discard audio buffered during the handshake delay so we only send fresh speech.
		if mic_capture:
			mic_capture.clear_buffer()
		# If the user released Shift+Space before the handshake finished, send STOP now.
		if not is_recording:
			ws.send_text("STOP")

	# Connect timeout: if handshake takes >4 s, abort so the user can try again.
	if ws_state == WebSocketPeer.STATE_CONNECTING and Time.get_ticks_msec() - ws_connect_start_ms > 4000:
		is_recording = false
		ptt_submit_pending = false
		ws.close()
		player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."
		return

	# Send mic samples while recording.
	# NPC audio plays on the Master/output bus; mic capture is on the isolated "MicCapture" bus,
	# so there is no feedback regardless of NPC playback state — no need to gate on pcm_stream_active.
	if is_recording and ws_state == WebSocketPeer.STATE_OPEN and mic_capture != null:
		var frames_available = mic_capture.get_frames_available()
		if frames_available > 0:
			var frames = mic_capture.get_buffer(frames_available)
			var engine_rate = float(AudioServer.get_mix_rate())
			var step = engine_rate / float(VOXTRAL_SAMPLE_RATE)
			var pcm_bytes := PackedByteArray()
			var pos := 0.0
			while pos < frames.size():
				var frame: Vector2 = frames[int(pos)]
				var mono := clampf((frame.x + frame.y) * 0.5, -1.0, 1.0)
				var s := int(mono * 32767.0)
				if s < 0:
					s += 65536
				pcm_bytes.append(s & 0xFF)
				pcm_bytes.append((s >> 8) & 0xFF)
				pos += step
			if pcm_bytes.size() > 0:
				ws.send(pcm_bytes)


	# Handle incoming transcription events
	while ws.get_available_packet_count() > 0:
		var raw = ws.get_packet().get_string_from_utf8()
		var json = JSON.new()
		if json.parse(raw) != OK:
			continue
		var msg = json.get_data()
		match msg.get("type", ""):
			"delta":
				transcript += str(msg.get("text", ""))
				player_input.text = transcript
			"done":
				is_recording = false
				ws.close()
				if ptt_submit_pending:
					ptt_submit_pending = false
					var done_text = player_input.text.strip_edges()
					if done_text != "":
						_on_message_submitted(done_text)
					else:
						player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."
			"error":
				is_recording = false
				ptt_submit_pending = false
				ws.close()
				player_input.placeholder_text = "Hold Shift+Space to speak, or type here..."

func _drain_pcm_queue():
	_ensure_pcm_stream()
	if voice_playback == null:
		return

	var available: int = voice_playback.get_frames_available()
	if available <= 0:
		return

	var buffered_samples: int = pcm_pending_samples.size() - pcm_sample_read_index
	if buffered_samples <= 0:
		if pcm_carry_byte < 0:
			pcm_stream_active = false
		return

	var frames_to_push: int = mini(available, buffered_samples)
	for i in range(frames_to_push):
		var v: float = pcm_pending_samples[pcm_sample_read_index + i]
		voice_playback.push_frame(Vector2(v, v))
	pcm_sample_read_index += frames_to_push

	if pcm_sample_read_index >= pcm_pending_samples.size():
		pcm_pending_samples.clear()
		pcm_sample_read_index = 0
		if pcm_carry_byte < 0:
			pcm_stream_active = false

func _decode_pcm_sample(byte0: int, byte1: int) -> int:
	var sample: int
	if TTS_PCM_BIG_ENDIAN:
		sample = (byte0 << 8) | byte1
	else:
		sample = byte0 | (byte1 << 8)
	if sample >= 32768:
		sample -= 65536
	return sample

func _play_pcm_bytes(pcm_bytes: PackedByteArray):
	if pcm_bytes.size() == 0:
		return
	voice_player.stop()
	voice_playback = null
	pcm_carry_byte = -1
	pcm_pending_samples.clear()
	pcm_sample_read_index = 0
	_queue_pcm_chunk(pcm_bytes)

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
		"http://127.0.0.1:8000/api/voice/speak",
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		body
	)

func _on_voice_response(result, response_code, headers, body, http):
	http.queue_free()
	if response_code != 200:
		return
	_play_pcm_bytes(body)

func _clear_dialogue_ui():
	dialogue_text.clear()
	player_input.clear()

func close_dialogue():
	_clear_dialogue_ui()
	DialogueManager.end_conversation()
	queue_free()
