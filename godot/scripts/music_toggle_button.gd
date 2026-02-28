extends TextureButton

const DEFAULT_ICON_ON_PATH := "res://assets/ui/music_on.png"
const DEFAULT_ICON_OFF_PATH := "res://assets/ui/music_off.png"

var _is_muted: bool = false
var _bgm: AudioStreamPlayer = null

@export var icon_music_on: Texture2D
@export var icon_music_off: Texture2D


func _ready():
	_bgm = get_tree().current_scene.get_node_or_null("BackgroundMusic") as AudioStreamPlayer
	if _bgm == null:
		tooltip_text = "Music unavailable"
		disabled = true
		return

	if icon_music_on == null:
		icon_music_on = load(DEFAULT_ICON_ON_PATH) as Texture2D
	if icon_music_off == null:
		icon_music_off = load(DEFAULT_ICON_OFF_PATH) as Texture2D

	pressed.connect(_on_pressed)
	ignore_texture_size = true
	stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	_apply_button_ui()


func _on_pressed():
	_is_muted = not _is_muted
	if _bgm:
		_bgm.stream_paused = _is_muted
	_apply_button_ui()


func _apply_button_ui():
	tooltip_text = "Unmute music" if _is_muted else "Mute music"

	var icon: Texture2D = icon_music_off if _is_muted else icon_music_on
	if icon == null:
		icon = icon_music_on if icon_music_on != null else icon_music_off
	texture_normal = icon
	texture_hover = icon
	texture_pressed = icon
	texture_disabled = icon
