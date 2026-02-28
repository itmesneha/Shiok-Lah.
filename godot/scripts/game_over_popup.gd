extends CanvasLayer

signal action_selected(restart: bool)

@onready var title_label: Label = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Title
@onready var message_label: Label = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Message
@onready var restart_button: Button = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Buttons/RestartButton

func _ready():
	if restart_button != null:
		restart_button.pressed.connect(_on_restart_pressed)
		restart_button.grab_focus()

func configure(is_win: bool, _reason: String = ""):
	if is_win:
		title_label.text = "You Won!"
		message_label.text = "You extracted 3 secrets! Hawker legend status unlocked!"
	else:
		title_label.text = "Game Over"
		message_label.text = "You got caught!!"

func _on_restart_pressed():
	action_selected.emit(true)
	queue_free()
