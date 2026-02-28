extends Button

const MUSIC_ICON := "♪"
const COLOR_ON := Color(0.63, 0.93, 0.67, 1.0)
const COLOR_OFF := Color(0.18, 0.18, 0.18, 1.0)
const COLOR_OFF_HOVER := Color(0.25, 0.25, 0.25, 1.0)
const COLOR_TEXT := Color(0.06, 0.06, 0.06, 1.0)
const COLOR_TEXT_OFF := Color(0.9, 0.9, 0.9, 1.0)

var _is_muted: bool = false
var _bgm: AudioStreamPlayer = null


func _ready():
	_bgm = get_tree().current_scene.get_node_or_null("BackgroundMusic") as AudioStreamPlayer
	if _bgm == null:
		text = MUSIC_ICON
		tooltip_text = "Music unavailable"
		disabled = true
		return

	pressed.connect(_on_pressed)
	_apply_button_ui()


func _on_pressed():
	_is_muted = not _is_muted
	if _bgm:
		_bgm.stream_paused = _is_muted
	_apply_button_ui()


func _apply_button_ui():
	text = MUSIC_ICON
	tooltip_text = "Unmute music" if _is_muted else "Mute music"
	_apply_button_colors()


func _apply_button_colors():
	var music_on := _bgm != null and _bgm.playing and not _is_muted and not _bgm.stream_paused
	var base := COLOR_ON if music_on else COLOR_OFF
	var hover := base.lightened(0.07) if music_on else COLOR_OFF_HOVER
	var pressed := base.darkened(0.12)
	var border := base.darkened(0.35)
	var font_col := COLOR_TEXT if music_on else COLOR_TEXT_OFF

	var normal_sb := StyleBoxFlat.new()
	normal_sb.bg_color = base
	normal_sb.corner_radius_top_left = 8
	normal_sb.corner_radius_top_right = 8
	normal_sb.corner_radius_bottom_left = 8
	normal_sb.corner_radius_bottom_right = 8
	normal_sb.border_width_left = 1
	normal_sb.border_width_top = 1
	normal_sb.border_width_right = 1
	normal_sb.border_width_bottom = 1
	normal_sb.border_color = border

	var hover_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	hover_sb.bg_color = hover

	var pressed_sb: StyleBoxFlat = normal_sb.duplicate() as StyleBoxFlat
	pressed_sb.bg_color = pressed

	add_theme_stylebox_override("normal", normal_sb)
	add_theme_stylebox_override("hover", hover_sb)
	add_theme_stylebox_override("pressed", pressed_sb)
	add_theme_stylebox_override("focus", hover_sb)
	add_theme_stylebox_override("disabled", normal_sb)
	add_theme_color_override("font_color", font_col)
	add_theme_color_override("font_hover_color", font_col)
	add_theme_color_override("font_pressed_color", font_col)
