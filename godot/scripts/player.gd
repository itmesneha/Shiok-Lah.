extends CharacterBody2D
var can_move = true

const SPEED = 130.0

@onready var sprite = $AnimatedSprite2D

func _physics_process(_delta: float) -> void:
	if not can_move:
		velocity = Vector2.ZERO
		move_and_slide()
		return

	# Get the input vector
	var direction := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	
	if direction != Vector2.ZERO:
		# --- RUNNING STATE ---
		velocity = direction * SPEED
		
		# Check which direction is the most dominant to pick the right animation
		if abs(direction.x) > abs(direction.y):
			# Horizontal movement is stronger
			if direction.x > 0:
				sprite.play("run_right")
			else:
				sprite.play("run_left")
		else:
			# Vertical movement is stronger
			if direction.y > 0:
				sprite.play("run_down")
			else:
				sprite.play("run_up")
				
	else:
		# --- IDLE STATE ---
		velocity = velocity.move_toward(Vector2.ZERO, SPEED)
		sprite.play("idle")

	move_and_slide()
