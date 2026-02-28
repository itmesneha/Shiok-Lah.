extends Node2D

@onready var bgm: AudioStreamPlayer = $BackgroundMusic
@export var restart_grace_seconds: float = 0.05

var _restart_queued: bool = false
var _restart_elapsed: float = 0.0

func _ready() -> void:
	if bgm == null:
		return
	_enable_stream_loop()
	if not bgm.finished.is_connected(_on_background_music_finished):
		bgm.finished.connect(_on_background_music_finished)
	set_process(true)

func _process(delta: float) -> void:
	if bgm == null:
		return
	if bgm.stream_paused:
		return

	if _restart_queued:
		_restart_elapsed += delta
		if _restart_elapsed < restart_grace_seconds:
			return
		_restart_queued = false

	if not bgm.playing:
		bgm.play()

func _on_background_music_finished() -> void:
	if bgm == null:
		return
	_restart_queued = true
	_restart_elapsed = 0.0

func _enable_stream_loop() -> void:
	if bgm == null or bgm.stream == null:
		return
	if bgm.stream is AudioStreamOggVorbis:
		var ogg_stream: AudioStreamOggVorbis = bgm.stream as AudioStreamOggVorbis
		ogg_stream.loop = true
	elif bgm.stream is AudioStreamWAV:
		var wav_stream: AudioStreamWAV = bgm.stream as AudioStreamWAV
		wav_stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
