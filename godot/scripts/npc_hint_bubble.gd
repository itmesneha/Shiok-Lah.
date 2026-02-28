extends Node2D

@export_multiline var hint_text: String = ""
@export var world_offset: Vector2 = Vector2(0, -45)
@export var float_amplitude: float = 3.0
@export var float_speed: float = 0.003
@export var bubble_size: Vector2 = Vector2(360, 120)

@onready var hint_area: Area2D = $HintArea
var _player_nearby := false
var _overlay_label: Label

func _ready():
	_ensure_overlay_label()
	_overlay_label.visible = false
	hint_area.body_entered.connect(_on_body_entered)
	hint_area.body_exited.connect(_on_body_exited)

func _process(_delta):
	if _player_nearby:
		_update_overlay_position()

func _ensure_overlay_label():
	if is_instance_valid(_overlay_label):
		return
	var layer := get_tree().root.get_node_or_null("Game/HintOverlay")
	var host := layer if layer != null else get_tree().root
	_overlay_label = Label.new()
	_overlay_label.name = "HintLabel_" + str(get_instance_id())
	_overlay_label.visible = false
	_overlay_label.size = bubble_size
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.text = hint_text
	var settings := LabelSettings.new()
	settings.font = load("res://assets/fonts/Minecraft.ttf")
	settings.font_size = 20
	settings.font_color = Color(0.96, 0.91, 0.76, 1)
	settings.outline_size = 5
	settings.outline_color = Color(0.07, 0.07, 0.07, 1)
	settings.shadow_color = Color(0.07, 0.07, 0.07, 1)
	settings.shadow_offset = Vector2(2, 2)
	_overlay_label.label_settings = settings
	host.add_child(_overlay_label)

func _update_overlay_position():
	if not is_instance_valid(_overlay_label):
		return
	var bob = sin(Time.get_ticks_msec() * float_speed) * float_amplitude
	var world_pos = global_position + world_offset + Vector2(0, bob)
	var screen_pos = get_viewport().get_canvas_transform() * world_pos
	_overlay_label.position = Vector2(round(screen_pos.x - (_overlay_label.size.x * 0.5)), round(screen_pos.y))

func _on_body_entered(body):
	if body.name != "Player":
		return
	_player_nearby = true
	_ensure_overlay_label()
	_overlay_label.text = hint_text
	_overlay_label.visible = true
	_update_overlay_position()

func _on_body_exited(body):
	if body.name != "Player":
		return
	_player_nearby = false
	if is_instance_valid(_overlay_label):
		_overlay_label.visible = false

func _exit_tree():
	if is_instance_valid(_overlay_label):
		_overlay_label.queue_free()
