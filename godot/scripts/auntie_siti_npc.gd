extends CharacterBody2D
const SPEED = 130.0
@onready var sprite = $AnimatedSprite2D
@onready var interact_label = $InteractLabel

var player_nearby = false
var in_dialogue = false

func _ready():
	$Area2D.body_entered.connect(_on_player_entered)
	$Area2D.body_exited.connect(_on_player_exited)
	interact_label.visible = false

func _on_player_entered(body):
	if body.name == "Player":
		player_nearby = true
		interact_label.visible = true

func _on_player_exited(body):
	if body.name == "Player":
		player_nearby = false
		interact_label.visible = false

func _unhandled_input(event):
	if player_nearby and not in_dialogue and event.is_action_pressed("interact"):
		start_dialogue()
		get_viewport().set_input_as_handled()

func _process(_delta):
	if player_nearby:
		interact_label.position.y = -40 + sin(Time.get_ticks_msec() * 0.003) * 4

func start_dialogue():
	in_dialogue = true
	interact_label.visible = false
	get_node("/root/Game/Player").can_move = false
	DialogueManager.start_conversation("auntie_siti")
