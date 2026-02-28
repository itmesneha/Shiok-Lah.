extends CharacterBody2D
const SPEED = 130.0
@onready var sprite = $AnimatedSprite2D
@onready var interact_area: Area2D = $Area2D

var player_nearby = false
var in_dialogue = false
var _overlay_label: Label
var _label_base_offset := Vector2(0, -40)
var _float_amplitude := 4.0
var _float_speed := 0.003

func _ready():
	interact_area.body_entered.connect(_on_player_entered)
	interact_area.body_exited.connect(_on_player_exited)
	DialogueManager.conversation_ended.connect(_on_conversation_ended)
	_ensure_overlay_label()
	_overlay_label.visible = false

func _on_player_entered(body):
	if body.name == "Player":
		player_nearby = true
		_ensure_overlay_label()
		_overlay_label.visible = true
		_update_overlay_position()

func _on_player_exited(body):
	if body.name == "Player":
		player_nearby = false
		if is_instance_valid(_overlay_label):
			_overlay_label.visible = false

func _unhandled_input(event):
	if player_nearby and not in_dialogue and event.is_action_pressed("interact"):
		start_dialogue()
		get_viewport().set_input_as_handled()

func _process(_delta):
	if player_nearby:
		_update_overlay_position()

func start_dialogue():
	in_dialogue = true
	if is_instance_valid(_overlay_label):
		_overlay_label.visible = false
	get_node("/root/Game/Player").can_move = false
	DialogueManager.start_conversation("auntie_siti")

func _on_conversation_ended():
	in_dialogue = false
	if player_nearby and is_instance_valid(_overlay_label):
		_overlay_label.visible = true
		_update_overlay_position()

func _ensure_overlay_label():
	if is_instance_valid(_overlay_label):
		return
	var layer := get_tree().root.get_node_or_null("Game/HintOverlay")
	var host := layer if layer != null else get_tree().root
	_overlay_label = Label.new()
	_overlay_label.name = "InteractLabel_" + str(get_instance_id())
	_overlay_label.visible = false
	_overlay_label.size = Vector2(320, 80)
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_overlay_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_overlay_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_overlay_label.text = "Press E to interact"
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
	var bob = sin(Time.get_ticks_msec() * _float_speed) * _float_amplitude
	var world_pos = global_position + _label_base_offset + Vector2(0, bob)
	var screen_pos = get_viewport().get_canvas_transform() * world_pos
	_overlay_label.position = Vector2(round(screen_pos.x - (_overlay_label.size.x * 0.5)), round(screen_pos.y))

func _exit_tree():
	if is_instance_valid(_overlay_label):
		_overlay_label.queue_free()
