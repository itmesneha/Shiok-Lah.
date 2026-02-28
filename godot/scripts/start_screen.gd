extends Control

const GAME_SCENE_PATH := "res://scenes/game.tscn"

@onready var start_button: Button = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Buttons/StartButton
@onready var quit_button: Button = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Buttons/QuitButton
@onready var robert_preview: AnimatedSprite2D = $CenterContainer/PanelContainer/CharacterPreviews/RobertPreview
@onready var ah_kow_preview: AnimatedSprite2D = $CenterContainer/PanelContainer/CharacterPreviews/AhKowPreview
@onready var siti_preview: AnimatedSprite2D = $CenterContainer/PanelContainer/CharacterPreviews/SitiPreview

func _ready():
	start_button.pressed.connect(_on_start_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	_play_preview(robert_preview)
	_play_preview(ah_kow_preview)
	_play_preview(siti_preview)
	start_button.grab_focus()

func _unhandled_input(event):
	if event.is_action_pressed("ui_accept"):
		_on_start_pressed()

func _on_start_pressed():
	get_tree().change_scene_to_file(GAME_SCENE_PATH)

func _on_quit_pressed():
	get_tree().quit()

func _play_preview(sprite: AnimatedSprite2D):
	if sprite == null or sprite.sprite_frames == null:
		return
	var names = sprite.sprite_frames.get_animation_names()
	if names.is_empty():
		return
	var preferred = "idle"
	if sprite.sprite_frames.has_animation(preferred):
		sprite.play(preferred)
	else:
		sprite.play(names[0])
