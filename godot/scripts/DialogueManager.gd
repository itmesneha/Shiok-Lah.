# DialogueManager.gd
extends Node

signal conversation_ended

var conversation_open := false

func start_conversation(npc_id: String):
	if conversation_open:
		return
	conversation_open = true
	print("npc dialogue starting.")
	var dialogue_scene = preload("res://scenes/NPCDialogue.tscn").instantiate()
	dialogue_scene.npc_id = npc_id
	get_tree().root.add_child(dialogue_scene)

func end_conversation():
	conversation_open = false
	get_node("/root/Game/Player").can_move = true
	emit_signal("conversation_ended")
