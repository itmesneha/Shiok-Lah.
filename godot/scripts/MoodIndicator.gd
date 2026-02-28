extends Control

@export var neutral_sprite_path: NodePath
@export var warm_sprite_path: NodePath
@export var suspicious_sprite_path: NodePath
@export var hostile_sprite_path: NodePath
@export var impressed_sprite_path: NodePath

@export var neutral_texture: Texture2D
@export var warm_texture: Texture2D
@export var suspicious_texture: Texture2D
@export var hostile_texture: Texture2D
@export var impressed_texture: Texture2D

@export var actor_font: Font
@export var status_font: Font
@export_range(8, 64, 1) var actor_font_size: int = 18
@export_range(8, 64, 1) var status_font_size: int = 16

@onready var actor_label: Label = $Panel/HBox/TextCol/ActorLabel
@onready var status_label: Label = $Panel/HBox/TextCol/StatusLabel
@onready var icon_rect: TextureRect = get_node_or_null("Panel/HBox/MoodIcon")

var _actor_name: String = "NPC"
var _mood: String = "neutral"
var _waiting: bool = false
var _elapsed: float = 0.0
var _neutral_sprite: CanvasItem
var _warm_sprite: CanvasItem
var _suspicious_sprite: CanvasItem
var _hostile_sprite: CanvasItem
var _impressed_sprite: CanvasItem

const MOOD_COLORS := {
	"neutral": Color(0.82, 0.84, 0.88),
	"warm": Color(0.58, 0.90, 0.67),
	"suspicious": Color(0.98, 0.79, 0.45),
	"hostile": Color(0.95, 0.53, 0.53),
	"impressed": Color(0.56, 0.78, 0.98)
}

func _ready():
	_resolve_sprite_refs()
	_apply_fonts()
	_refresh()

func _process(delta: float):
	if not _waiting:
		return
	_elapsed += delta
	var dots := ".".repeat(int(floor(_elapsed * 4.0)) % 4 + 1)
	status_label.text = "Thinking" + dots

func set_actor_name(name: String):
	_actor_name = name
	actor_label.text = _actor_name

func set_mood(mood: String):
	_mood = mood
	if not _waiting:
		_refresh()

func set_waiting(waiting: bool):
	_waiting = waiting
	if _waiting:
		_elapsed = 0.0
		status_label.modulate = Color(0.93, 0.93, 0.93)
		status_label.text = "Thinking."
	else:
		_refresh()

func _refresh():
	actor_label.text = _actor_name
	status_label.text = _mood.capitalize()
	status_label.modulate = MOOD_COLORS.get(_mood, MOOD_COLORS["neutral"])
	_set_active_mood_visual(_mood)

func _set_active_mood_visual(mood: String):
	var has_sprites = _has_any_sprite_refs()
	if has_sprites:
		_set_all_sprites_visible(false)
		var active = _sprite_for_mood(mood)
		if active != null:
			active.visible = true
		if icon_rect != null:
			icon_rect.visible = false
		return
	
	if icon_rect != null:
		icon_rect.visible = true
		icon_rect.texture = _texture_for_mood(mood)

func _sprite_for_mood(mood: String) -> CanvasItem:
	match mood:
		"warm":
			return _warm_sprite
		"suspicious":
			return _suspicious_sprite
		"hostile":
			return _hostile_sprite
		"impressed":
			return _impressed_sprite
		_:
			return _neutral_sprite

func _texture_for_mood(mood: String) -> Texture2D:
	match mood:
		"warm":
			return warm_texture
		"suspicious":
			return suspicious_texture
		"hostile":
			return hostile_texture
		"impressed":
			return impressed_texture
		_:
			return neutral_texture

func _resolve_sprite_refs():
	_neutral_sprite = _get_canvas_item(neutral_sprite_path)
	_warm_sprite = _get_canvas_item(warm_sprite_path)
	_suspicious_sprite = _get_canvas_item(suspicious_sprite_path)
	_hostile_sprite = _get_canvas_item(hostile_sprite_path)
	_impressed_sprite = _get_canvas_item(impressed_sprite_path)
	_set_all_sprites_visible(false)

func _get_canvas_item(path: NodePath) -> CanvasItem:
	if path.is_empty():
		return null
	var node = get_node_or_null(path)
	if node == null:
		return null
	return node as CanvasItem

func _set_all_sprites_visible(visible: bool):
	for item in [_neutral_sprite, _warm_sprite, _suspicious_sprite, _hostile_sprite, _impressed_sprite]:
		if item != null:
			item.visible = visible

func _has_any_sprite_refs() -> bool:
	return (
		_neutral_sprite != null
		or _warm_sprite != null
		or _suspicious_sprite != null
		or _hostile_sprite != null
		or _impressed_sprite != null
	)

func _apply_fonts():
	if actor_font != null:
		actor_label.add_theme_font_override("font", actor_font)
	actor_label.add_theme_font_size_override("font_size", actor_font_size)

	if status_font != null:
		status_label.add_theme_font_override("font", status_font)
	status_label.add_theme_font_size_override("font_size", status_font_size)
