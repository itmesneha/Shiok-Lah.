extends CanvasLayer

signal action_selected(restart: bool)

@onready var title_label: Label = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Title
@onready var message_label: Label = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Message
@onready var restart_button: Button = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Buttons/RestartButton
@onready var close_button: Button = $CenterContainer/PanelContainer/MarginContainer/VBoxContainer/Buttons/CloseButton

func _ready():
	restart_button.pressed.connect(_on_restart_pressed)
	close_button.pressed.connect(_on_close_pressed)
	restart_button.grab_focus()

func configure(is_win: bool, reason: String = ""):
	if is_win:
		title_label.text = "You Won!"
		message_label.text = "You extracted enough secrets. Hawker legend status unlocked."
	else:
		title_label.text = "Game Over"
		var detail = reason.strip_edges()
		if detail == "":
			detail = "Suspicion got too high."
		message_label.text = "You got caught. " + detail

func _on_restart_pressed():
	action_selected.emit(true)
	queue_free()

func _on_close_pressed():
	action_selected.emit(false)
	queue_free()
