# GameState.gd (autoload)
extends Node

var session_id: String = ""
var collected_secrets: Array = []
var npc_states: Dictionary = {}

const ALL_SECRETS = ["uncle_robert", "auntie_siti", "ah_kow"]

func _generate_uuid() -> String:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	
	var b = []
	for i in range(16):
		b.append(rng.randi() % 256)
	
	# Set version 4
	b[6] = (b[6] & 0x0f) | 0x40
	# Set variant
	b[8] = (b[8] & 0x3f) | 0x80
	
	return "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x" % [
		b[0], b[1], b[2], b[3],
		b[4], b[5],
		b[6], b[7],
		b[8], b[9],
		b[10], b[11], b[12], b[13], b[14], b[15]
	]
	
func _ready():
	# Generate or load session ID
	if FileAccess.file_exists("user://session.txt"):
		session_id = FileAccess.open("user://session.txt", FileAccess.READ).get_as_text()
	else:
		session_id = _generate_uuid()
		var f = FileAccess.open("user://session.txt", FileAccess.WRITE)
		f.store_string(session_id)

func collect_secret(npc_id: String):
	if npc_id not in collected_secrets:
		collected_secrets.append(npc_id)
		emit_signal("secret_collected", npc_id)
		
	if collected_secrets.size() == ALL_SECRETS.size():
		emit_signal("all_secrets_collected")  # triggers win screen

func update_npc_state(npc_id: String, state: Dictionary):
	npc_states[npc_id] = state
	if state.get("win", false):
		collect_secret(npc_id)
	
signal secret_collected(npc_id)
signal all_secrets_collected


#**The win condition flow end-to-end**
#```
#Player talks to Uncle Robert
#→ mood hits warm, suspicion drops low
#→ backend returns win=true in [STATE] block
#→ GameState.collect_secret("uncle_robert") called
#→ UI shows "🍳 Secret obtained: Duck fat & secret chilli blend!"
#→ Uncle Robert's stall icon gets a ✓ on the map
#
#Player collects all 3
#→ all_secrets_collected signal fires
#→ Scene transitions to WinScreen
#→ WinScreen shows all 3 recipes revealed
#→ Play victory sound via ElevenLabs ("Wah you very clever lah!")
