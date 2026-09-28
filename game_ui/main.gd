extends Node3D

# ChaosticTool — poste d'opérateur Cyberpunk.
# Décor resserré : une console avec une table holographique comme unique point
# d'intérêt. La caméra est calme au repos et accompagne chaque section par un
# court déplacement. L'interface s'anime surtout à l'interaction ; les textes,
# formulaires et résultats restent sur des surfaces lisibles.

const GOLD = Color("f2d64b")
const CYAN = Color("6fe0da")
const WHITE = Color("e6efe9")
const MUTED = Color("93abae")
const INK = Color("06121a")

var camera: Camera3D
var cam_target := Vector3(2.4, 1.9, -2.0)
var holo: Node3D
var holo_globe: Node3D
var holo_glow: OmniLight3D
var key_light: DirectionalLight3D
var page: Control
var root_ui: Control
var title: Label
var subtitle: Label
var back_button: Button
var scene_tween: Tween
var target_tween: Tween
var ui_tween: Tween
var display_font = preload("res://assets/Orbitron.ttf")
var body_font = preload("res://assets/Exo2.ttf")
var mono_font = preload("res://assets/ShareTechMono-Regular.ttf")
var config = ConfigFile.new()
var settings = {"fullscreen":true,"master":0.45,"ui":0.5,"ambience":0.18,"mute":false,"motion":true,"fps":60}
var players = {}
var ambience: AudioStreamPlayer
var tick = 0.0
var current_page = "home"
var catalog = []
var qa_dir = ""
var settings_path = "user://settings.cfg"
var status_label: Label
var selected_tool := 0
var focus_pulse := 0.0

# Cadrage caméra par section : position et cible du regard. La table holo reste
# à droite pour laisser la colonne de texte à gauche parfaitement lisible.
const FRAMES = {
	"home":     {"pos": Vector3(-5.4, 3.35, 8.6), "look": Vector3(2.6, 1.85, -2.2)},
	"arsenal":  {"pos": Vector3(-3.4, 3.05, 7.4), "look": Vector3(2.9, 1.75, -2.4)},
	"fiche":    {"pos": Vector3(-1.2, 2.75, 6.2), "look": Vector3(3.1, 1.85, -2.6)},
	"settings": {"pos": Vector3(-6.2, 3.6, 8.8),  "look": Vector3(1.8, 1.7, -2.0)},
}

func _ready():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="): qa_dir = arg.trim_prefix("--qa-dir=")
	if not qa_dir.is_empty(): settings_path = qa_dir.path_join("settings.cfg")
	config.load(settings_path)
	for key in settings: settings[key] = config.get_value("preferences",key,settings[key])
	catalog = JSON.parse_string(FileAccess.get_file_as_string("res://catalog.json"))
	build_audio()
	build_world()
	build_ui()
	apply_settings()
	show_page("home")
	if not qa_dir.is_empty(): run_qa.call_deferred()

# ------------------------------------------------------------------ matériaux

func material(color: Color, emission = 0.0, rough = 0.42, metal = 0.5):
	var m = StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	if emission > 0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission
	return m

func box(parent: Node3D, pos: Vector3, size: Vector3, mat: Material, rot_y = 0.0):
	var node = MeshInstance3D.new()
	var mesh = BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.material_override = mat
	node.position = pos
	node.rotation_degrees.y = rot_y
	parent.add_child(node)
	return node

func cyl(parent: Node3D, pos: Vector3, height: float, top_r: float, bottom_r: float, mat: Material):
	var node = MeshInstance3D.new()
	var mesh = CylinderMesh.new()
	mesh.height = height
	mesh.top_radius = top_r
	mesh.bottom_radius = bottom_r
	mesh.radial_segments = 48
	node.mesh = mesh
	node.material_override = mat
	node.position = pos
	parent.add_child(node)
	return node

func ring(parent: Node3D, y: float, inner: float, outer: float, mat: Material):
	var node = MeshInstance3D.new()
	var torus = TorusMesh.new()
	torus.inner_radius = inner
	torus.outer_radius = outer
	torus.rings = 40
	torus.ring_segments = 10
	node.mesh = torus
	node.material_override = mat
	node.position.y = y
	parent.add_child(node)
	return node

# --------------------------------------------------------------------- monde

func build_world():
	var env_node = WorldEnvironment.new()
	var env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("050e14")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("2c4a52")
	env.ambient_light_energy = 0.5
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 1.1
	env.fog_enabled = true
	env.fog_light_color = Color("0c2029")
	env.fog_density = 0.02
	env.fog_aerial_perspective = 0.4
	env_node.environment = env
	add_child(env_node)

	key_light = DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-52,-38,0)
	key_light.light_color = Color("9fd3d8")
	key_light.light_energy = 1.15
	key_light.shadow_enabled = true
	add_child(key_light)

	var fill = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20,120,0)
	fill.light_color = Color("2b6f78")
	fill.light_energy = 0.35
	add_child(fill)

	build_room()
	build_console()
	build_hologram()

	camera = Camera3D.new()
	camera.fov = 52
	camera.position = FRAMES.home.pos
	cam_target = FRAMES.home.look
	add_child(camera)
	camera.look_at(cam_target)
	camera.current = true

func build_room():
	# Sol : dalle sombre + grille discrète en shader, sans barres qui rampent.
	var floor_plane = MeshInstance3D.new()
	var pm = PlaneMesh.new()
	pm.size = Vector2(46, 46)
	floor_plane.mesh = pm
	var floor_mat = ShaderMaterial.new()
	var floor_shader = Shader.new()
	floor_shader.code = """
shader_type spatial;
render_mode cull_disabled;
uniform vec3 base_color = vec3(0.030, 0.055, 0.066);
uniform vec3 line_color = vec3(0.16, 0.44, 0.47);
void fragment() {
	vec2 g = abs(fract(UV * 46.0) - 0.5) / fwidth(UV * 46.0);
	float line = 1.0 - min(min(g.x, g.y), 1.0);
	float dist = length(UV - vec2(0.5));
	float fade = smoothstep(0.52, 0.14, dist);
	ALBEDO = base_color;
	EMISSION = line_color * line * fade * 0.6;
	ROUGHNESS = 0.65;
	METALLIC = 0.2;
}
"""
	floor_mat.shader = floor_shader
	floor_plane.material_override = floor_mat
	add_child(floor_plane)

	var wall_mat = material(Color("0b1a22"), 0.0, 0.7, 0.15)
	var trim = material(CYAN, 1.1)

	# Mur du fond avec un grand écran d'opérateur en veille (sombre, discret).
	box(self, Vector3(1.5, 4.2, -13.6), Vector3(30, 9.2, 0.6), wall_mat)
	var screen = box(self, Vector3(1.5, 4.4, -13.2), Vector3(13.5, 5.4, 0.12), material(Color("081f27"), 0.35, 0.3, 0.2))
	screen.name = "OperatorScreen"
	# Cadre sobre et épais autour de l'écran, non émissif : pas de liseré rasant.
	box(self, Vector3(1.5, 7.25, -13.15), Vector3(14.0, 0.18, 0.16), material(Color("13323b"), 0.0, 0.5, 0.3))
	box(self, Vector3(1.5, 1.55, -13.15), Vector3(14.0, 0.18, 0.16), material(Color("13323b"), 0.0, 0.5, 0.3))
	# Fines colonnes de données sur l'écran, statiques et sobres.
	for i in range(9):
		var h = 0.6 + fmod(float(i) * 1.7, 3.0)
		box(self, Vector3(-4.4 + i * 1.35, 2.4 + h * 0.5, -13.1), Vector3(0.7, h, 0.05), material(Color("0e343f"), 0.5, 0.3, 0.2))

	# Parois latérales suggérées, tenues en retrait — pièce fermée, pas de couloir.
	# Aucun liseré rasant : les néons de mur balayaient l'écran, on les retire.
	for side in [-1, 1]:
		var x = side * 12.5
		box(self, Vector3(x, 4.2, -6.0), Vector3(0.6, 9.2, 16), wall_mat, side * 6.0)

	# Plafond simple, sans réglette lumineuse : la lumière vient de la scène.
	box(self, Vector3(1.5, 8.7, -6.0), Vector3(30, 0.5, 16), wall_mat)

func build_console():
	var desk_dark = material(Color("101f27"), 0.0, 0.5, 0.55)
	var desk_metal = material(Color("1b2d34"), 0.0, 0.35, 0.7)
	var edge = material(CYAN, 1.4)
	var edge_gold = material(GOLD, 1.1)

	# Table opérateur : un plateau incliné, travaillé, plutôt qu'un empilement.
	var deck = Node3D.new()
	deck.position = Vector3(3.0, 0, -2.4)
	add_child(deck)
	# Socle et pieds.
	box(deck, Vector3(0, 0.35, 0), Vector3(6.4, 0.7, 3.6), desk_metal)
	box(deck, Vector3(0, 0.06, 0), Vector3(6.8, 0.12, 4.0), material(Color("0a151b")))
	box(deck, Vector3(0, 0.74, 0), Vector3(6.0, 0.06, 3.2), edge)
	# Plateau incliné vers l'opérateur.
	var top = box(deck, Vector3(0, 1.12, 0.35), Vector3(6.0, 0.16, 2.6), desk_dark)
	top.rotation_degrees.x = -14
	# Bandeau lumineux sur l'arête avant du plateau.
	var lip = box(deck, Vector3(0, 0.86, 1.5), Vector3(6.0, 0.05, 0.12), edge_gold)
	lip.rotation_degrees.x = -14
	# Deux petits panneaux latéraux d'instruments, sobres.
	box(deck, Vector3(-2.5, 1.0, 0.9), Vector3(0.9, 0.5, 0.7), desk_metal, 16)
	box(deck, Vector3(2.5, 1.0, 0.9), Vector3(0.9, 0.5, 0.7), desk_metal, -16)
	box(deck, Vector3(-2.5, 1.27, 0.92), Vector3(0.7, 0.02, 0.5), edge, 16)
	box(deck, Vector3(2.5, 1.27, 0.92), Vector3(0.7, 0.02, 0.5), edge_gold, -16)

func build_hologram():
	# Table holographique : émetteur sur la console + projection volumétrique
	# tenue. Elle tourne lentement au repos et se resserre quand on ouvre une fiche.
	holo = Node3D.new()
	holo.position = Vector3(3.0, 1.35, -2.1)
	add_child(holo)

	var emitter = material(CYAN, 2.2)
	cyl(holo, Vector3(0, 0.02, 0), 0.06, 0.95, 1.05, material(Color("0c2830"), 0.6, 0.3, 0.6))
	ring(holo, 0.09, 0.86, 0.95, emitter)

	# Cône de projection additif, très transparent, plus dense en bas.
	var cone = MeshInstance3D.new()
	var cone_mesh = CylinderMesh.new()
	cone_mesh.height = 2.5
	cone_mesh.top_radius = 0.95
	cone_mesh.bottom_radius = 0.7
	cone_mesh.radial_segments = 40
	cone_mesh.cap_top = false
	cone_mesh.cap_bottom = false
	cone.mesh = cone_mesh
	var cone_mat = ShaderMaterial.new()
	var cone_shader = Shader.new()
	cone_shader.code = """
shader_type spatial;
render_mode blend_add, cull_disabled, unshaded, depth_draw_never, shadows_disabled;
uniform vec3 tint = vec3(0.43, 0.88, 0.86);
varying float vy;
void vertex() { vy = UV.y; }
void fragment() {
	float fres = pow(1.0 - abs(dot(normalize(NORMAL), normalize(VIEW))), 1.6);
	float vfade = smoothstep(0.0, 1.0, vy);
	ALBEDO = tint;
	ALPHA = clamp((fres * 0.42 + 0.06) * vfade, 0.0, 0.5);
}
"""
	cone_mat.shader = cone_shader
	cone.material_override = cone_mat
	cone.position.y = 1.3
	holo.add_child(cone)

	# Globe filaire lent : anneaux croisés + noyau — c'est le point d'intérêt.
	holo_globe = Node3D.new()
	holo_globe.position.y = 1.35
	holo.add_child(holo_globe)
	var wire = material(CYAN, 2.6)
	wire.albedo_color = Color(CYAN.r, CYAN.g, CYAN.b, 0.9)
	wire.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var core = MeshInstance3D.new()
	var sphere = SphereMesh.new()
	sphere.radius = 0.62
	sphere.height = 1.24
	sphere.radial_segments = 24
	sphere.rings = 14
	core.mesh = sphere
	var core_mat = material(Color("123842"), 1.2, 0.2, 0.4)
	core_mat.albedo_color = Color(0.07, 0.22, 0.26, 0.55)
	core_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	core.mesh.material = core_mat
	holo_globe.add_child(core)
	for i in range(3):
		var r = ring(holo_globe, 0.0, 0.60, 0.64, wire)
		r.rotation_degrees = Vector3(90 * i, 30 * i, 20 * i)
	ring(holo_globe, 0.0, 0.86, 0.90, material(GOLD, 1.6)).rotation_degrees = Vector3(78, 0, 0)
	# Un unique anneau doré incliné suffit comme accent ; pas de semis de cubes.

	holo_glow = OmniLight3D.new()
	holo_glow.position = Vector3(3.0, 2.0, -2.1)
	holo_glow.light_color = CYAN
	holo_glow.light_energy = 2.2
	holo_glow.omni_range = 8.0
	add_child(holo_glow)

# ----------------------------------------------------------------------- UI

func label_at(parent, text, at, size, font_size = 22, color = WHITE, display = false, font_override = null, wrap = false):
	var item = Label.new()
	# L'autowrap doit être posé AVANT la taille : sinon le label se dimensionne
	# d'abord au contenu (très large) et wrappe ensuite à cette largeur, ce qui
	# faisait déborder les textes longs hors des panneaux.
	if wrap:
		item.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		item.clip_text = true
	item.position = at
	item.custom_minimum_size = size
	item.size = size
	item.text = text
	var f = font_override
	if f == null: f = display_font if display else body_font
	item.add_theme_font_override("font", f)
	item.add_theme_font_size_override("font_size", font_size)
	item.add_theme_color_override("font_color", color)
	item.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(item)
	return item

func style(color, border, left_accent = 4):
	var s = StyleBoxFlat.new()
	s.bg_color = color
	s.border_color = border
	s.set_border_width_all(1)
	s.border_width_left = left_accent
	s.content_margin_left = 22
	s.content_margin_right = 20
	s.set_corner_radius_all(3)
	return s

func panel_at(parent, at, size, tint = Color(0.024, 0.052, 0.066, 0.975), border = Color("32565c")):
	var p = Panel.new()
	p.position = at
	p.size = size
	var s = style(tint, border, 1)
	s.set_corner_radius_all(4)
	p.add_theme_stylebox_override("panel", s)
	parent.add_child(p)
	return p

func button_at(parent, text, at, size, action, primary = false):
	var b = Button.new()
	b.text = text
	b.position = at
	b.size = size
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_font_override("font", body_font)
	b.add_theme_font_size_override("font_size", 24)
	b.add_theme_color_override("font_color", INK if primary else WHITE)
	b.add_theme_color_override("font_hover_color", INK if primary else GOLD)
	b.add_theme_color_override("font_focus_color", INK if primary else GOLD)
	b.add_theme_stylebox_override("normal", style(GOLD if primary else Color(0.03, 0.07, 0.085, 0.85), Color("5f7a78")))
	b.add_theme_stylebox_override("hover", style(Color("f7e072") if primary else Color(0.07, 0.15, 0.17, 0.95), GOLD))
	b.add_theme_stylebox_override("focus", style(Color("f7e072") if primary else Color(0.06, 0.14, 0.155, 0.97), GOLD))
	b.add_theme_stylebox_override("pressed", style(Color("ffe98a") if primary else Color(0.02, 0.08, 0.10, 0.98), CYAN))
	b.mouse_entered.connect(func(): b.grab_focus())
	b.focus_entered.connect(func(): sound("hover"))
	b.pressed.connect(func(): sound("confirm"); action.call())
	parent.add_child(b)
	return b

func build_ui():
	var canvas = CanvasLayer.new()
	add_child(canvas)
	root_ui = Control.new()
	root_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	canvas.add_child(root_ui)

	# Voile dégradé ancré à gauche : la colonne de texte est toujours sur du sombre,
	# le point d'intérêt 3D reste visible à droite. Aucune animation ici.
	var veil = ColorRect.new()
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var shader = Shader.new()
	shader.code = "shader_type canvas_item; void fragment(){ float a = mix(0.95, 0.0, smoothstep(0.0, 0.62, UV.x)); float top = mix(0.35, 0.0, smoothstep(0.0, 0.32, UV.y)); float bot = smoothstep(0.72, 1.0, UV.y) * 0.5; COLOR = vec4(0.01, 0.022, 0.03, clamp(a + top + bot, 0.0, 0.97)); }"
	var sm = ShaderMaterial.new(); sm.shader = shader; veil.material = sm
	root_ui.add_child(veil)

	label_at(root_ui, "CHAOSTIC / TOOL", Vector2(64, 40), Vector2(900, 35), 22, CYAN, true)
	label_at(root_ui, "POSTE D'OPÉRATEUR  ·  PRÉVISUALISATION", Vector2(64, 80), Vector2(1000, 28), 14, MUTED, true)
	title = label_at(root_ui, "", Vector2(64, 138), Vector2(1200, 130), 55, GOLD, true)
	subtitle = label_at(root_ui, "", Vector2(66, 236), Vector2(760, 60), 22, WHITE)
	page = Control.new(); page.position = Vector2(66, 300); page.size = Vector2(1500, 520); root_ui.add_child(page)
	back_button = button_at(root_ui, "←  RETOUR", Vector2(1300, 44), Vector2(235, 46), func(): back_action())
	status_label = label_at(root_ui, "F11  PLEIN ÉCRAN     ·     ÉCHAP  RETOUR     ·     FLÈCHES + ENTRÉE", Vector2(64, 850), Vector2(1300, 30), 15, MUTED, false, mono_font)

func back_action():
	if current_page == "fiche": show_page("arsenal")
	else: show_page("home")

func clear_page():
	for child in page.get_children(): page.remove_child(child); child.queue_free()

func show_page(which):
	var previous = current_page
	current_page = which
	clear_page()
	back_button.visible = which != "home"
	if which == "fiche": back_button.text = "←  ARSENAL"
	else: back_button.text = "←  ACCUEIL"
	if scene_tween: scene_tween.kill()
	if ui_tween: ui_tween.kill()
	if target_tween: target_tween.kill()
	focus_pulse = 1.0
	match which:
		"home":
			title.text = "VOTRE PROCHAINE\nOPÉRATION."
			title.add_theme_font_size_override("font_size", 46)
			subtitle.text = "Entrez dans votre poste de commandement."
			subtitle.position.y = 258
			build_home()
		"arsenal":
			title.text = "ARSENAL"
			title.add_theme_font_size_override("font_size", 56)
			subtitle.text = "Le catalogue réel de ChaosticTool. Choisissez un outil, ouvrez sa fiche."
			subtitle.position.y = 232
			build_arsenal()
		"fiche":
			title.add_theme_font_size_override("font_size", 46)
			subtitle.position.y = 232
			build_fiche()
		"settings":
			title.text = "IMAGE & SON"
			title.add_theme_font_size_override("font_size", 56)
			subtitle.text = "Réglez votre expérience. Les préférences sont conservées."
			subtitle.position.y = 232
			build_settings()

	var frame = FRAMES.get(which, FRAMES.home)
	if settings.motion and camera:
		page.modulate.a = 0
		page.position.x = 92
		ui_tween = create_tween().set_parallel(true)
		ui_tween.tween_property(page, "modulate:a", 1.0, 0.3)
		ui_tween.tween_property(page, "position:x", 66.0, 0.4).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		var dur = 0.7 if previous != which else 0.4
		scene_tween = create_tween()
		scene_tween.tween_property(camera, "position", frame.pos, dur).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
		target_tween = create_tween()
		target_tween.tween_property(self, "cam_target", frame.look, dur).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	elif camera:
		page.modulate.a = 1; page.position.x = 66
		camera.position = frame.pos; cam_target = frame.look
	var controls = page.find_children("*", "Button", true, false)
	if not controls.is_empty(): controls[0].grab_focus()

func build_home():
	button_at(page, "01   EXPLORER L'ARSENAL", Vector2(0, 24), Vector2(600, 76), func(): show_page("arsenal"), true)
	button_at(page, "02   IMAGE & SON", Vector2(0, 116), Vector2(600, 76), func(): show_page("settings"))
	button_at(page, "03   OUVRIR DESKTOP 0.8", Vector2(0, 208), Vector2(600, 76), open_desktop)
	button_at(page, "QUITTER", Vector2(0, 312), Vector2(290, 60), func(): get_tree().quit())
	label_at(page, "Prototype graphique : les opérations restent dans Desktop 0.8.\nAucun outil n'est lancé depuis cette prévisualisation.", Vector2(2, 398), Vector2(820, 64), 18, MUTED)

func build_arsenal():
	panel_at(page, Vector2(-14, -12), Vector2(624, 512))
	var search = LineEdit.new(); search.position = Vector2(8, 8); search.size = Vector2(584, 46)
	search.placeholder_text = "Rechercher un outil…"
	search.add_theme_font_override("font", body_font)
	search.add_theme_font_size_override("font_size", 21)
	search.add_theme_stylebox_override("normal", style(Color(0.03, 0.07, 0.09, 0.95), Color("3a5f64"), 1))
	search.add_theme_stylebox_override("focus", style(Color(0.05, 0.10, 0.12, 0.98), GOLD, 1))
	page.add_child(search)
	var list = ItemList.new(); list.position = Vector2(8, 66); list.size = Vector2(584, 380)
	list.add_theme_font_override("font", body_font); list.add_theme_font_size_override("font_size", 23)
	list.add_theme_constant_override("v_separation", 12)
	list.add_theme_color_override("font_color", WHITE)
	list.add_theme_color_override("font_selected_color", GOLD)
	list.add_theme_stylebox_override("panel", style(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0))
	list.add_theme_stylebox_override("selected", style(Color(0.09, 0.17, 0.19, 0.9), GOLD))
	list.add_theme_stylebox_override("selected_focus", style(Color(0.10, 0.19, 0.21, 0.95), GOLD))
	page.add_child(list)

	# Volet de synthèse à droite, sur panneau opaque : toujours lisible.
	panel_at(page, Vector2(636, -12), Vector2(636, 460))
	var detail = label_at(page, "", Vector2(660, 6), Vector2(600, 60), 34, GOLD, true)
	var meta = label_at(page, "", Vector2(662, 66), Vector2(590, 30), 18, CYAN, false, mono_font)
	var description = label_at(page, "", Vector2(662, 108), Vector2(588, 150), 22, WHITE, false, null, true)
	var profiles = label_at(page, "", Vector2(662, 268), Vector2(588, 90), 19, MUTED, false, null, true)
	var open_btn = button_at(page, "OUVRIR LA FICHE  →", Vector2(660, 372), Vector2(320, 58), func(): show_page("fiche"), true)

	var indices = []
	var populate = func(query):
		list.clear()
		indices.clear()
		for i in range(catalog.size()):
			var tool = catalog[i]
			var hay = (str(tool.name) + " " + str(tool.get("group", "")) + " " + str(tool.get("category", ""))).to_lower()
			if query.is_empty() or hay.contains(query.to_lower()):
				var row = list.add_item(str(tool.name))
				list.set_item_metadata(row, i)
				indices.append(i)
	var preview = func(index):
		var idx = list.get_item_metadata(index)
		selected_tool = idx
		var tool = catalog[idx]
		detail.text = str(tool.name).to_upper()
		meta.text = str(tool.get("group", "")).to_upper() + "   ·   " + str(tool.get("category", "")).to_upper()
		description.text = str(tool.get("desc", ""))
		profiles.text = "%d profil(s) natif(s)  ·  %d profil(s) Linux\nConsultation du catalogue — l'exécution reste dans Desktop." % [tool.get("presets", []).size(), tool.get("linux_presets", []).size()]
		open_btn.text = "OUVRIR LA FICHE " + str(tool.name).to_upper() + "  →"
		sound("hover")
	search.text_changed.connect(populate)
	list.item_selected.connect(preview)
	list.item_activated.connect(func(index): preview.call(index); show_page("fiche"))
	populate.call("")
	# Restaure la sélection courante (ex. Nmap) si présente.
	var start = indices.find(selected_tool)
	if start < 0: start = 0
	if list.item_count > 0:
		list.select(start)
		preview.call(start)

func build_fiche():
	var tool = catalog[selected_tool]
	title.text = str(tool.name).to_upper()
	subtitle.text = str(tool.get("group", "")) + "   ·   catégorie " + str(tool.get("category", ""))

	# Colonne gauche : description + profils, sur panneaux lisibles.
	panel_at(page, Vector2(-14, -12), Vector2(700, 300))
	label_at(page, "DESCRIPTION", Vector2(8, 6), Vector2(400, 26), 16, CYAN, false, mono_font)
	label_at(page, str(tool.get("desc", "")), Vector2(8, 40), Vector2(660, 120), 23, WHITE, false, null, true)
	var note = str(tool.get("note", ""))
	if not note.is_empty():
		label_at(page, "NOTE", Vector2(8, 168), Vector2(400, 24), 15, GOLD, false, mono_font)
		label_at(page, note, Vector2(8, 194), Vector2(660, 96), 17, MUTED, false, null, true)

	# Bandeau de comptes de profils.
	var natifs = tool.get("presets", []).size()
	var linux = tool.get("linux_presets", []).size()
	panel_at(page, Vector2(-14, 300), Vector2(700, 74))
	label_at(page, "%d PROFILS NATIFS" % natifs, Vector2(20, 316), Vector2(320, 44), 26, WHITE, true)
	label_at(page, "%d PROFILS LINUX" % linux, Vector2(360, 316), Vector2(320, 44), 26, CYAN, true)

	# Colonne droite : profils disponibles (labels seuls, consultation).
	panel_at(page, Vector2(712, -12), Vector2(560, 386))
	label_at(page, "PROFILS DISPONIBLES  ·  CONSULTATION", Vector2(732, 6), Vector2(520, 26), 15, CYAN, false, mono_font)
	var plist = ItemList.new(); plist.position = Vector2(732, 40); plist.size = Vector2(516, 322)
	plist.add_theme_font_override("font", body_font); plist.add_theme_font_size_override("font_size", 20)
	plist.add_theme_constant_override("v_separation", 9)
	plist.add_theme_color_override("font_color", WHITE)
	plist.add_theme_color_override("font_selected_color", GOLD)
	plist.add_theme_stylebox_override("panel", style(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0))
	plist.add_theme_stylebox_override("selected", style(Color(0.09, 0.17, 0.19, 0.9), GOLD))
	plist.add_theme_stylebox_override("selected_focus", style(Color(0.10, 0.19, 0.21, 0.95), GOLD))
	plist.focus_mode = Control.FOCUS_ALL
	for preset in tool.get("presets", []):
		plist.add_item("· " + str(preset.get("label", "profil")))
	if plist.item_count == 0:
		plist.add_item("Profils Linux uniquement — voir Desktop.")
	page.add_child(plist)

	# Actions : l'exécution reste dans Desktop (aucun outil lancé ici).
	button_at(page, "OUVRIR DANS DESKTOP 0.8", Vector2(-14, 392), Vector2(440, 60), open_desktop, true)
	label_at(page, "Exécution non raccordée à cette prévisualisation.", Vector2(440, 408), Vector2(500, 40), 17, MUTED, false, mono_font)

func toggle_at(text, key, y):
	var check = CheckButton.new(); check.text = text; check.position = Vector2(24, y); check.size = Vector2(660, 44)
	check.add_theme_font_override("font", body_font); check.add_theme_font_size_override("font_size", 23)
	check.add_theme_color_override("font_color", WHITE)
	check.button_pressed = bool(settings[key]); page.add_child(check)
	check.toggled.connect(func(value): settings[key] = value; apply_settings(); save_settings(); sound("confirm"))
	return check

func slider_at(text, key, y):
	label_at(page, text, Vector2(724, y), Vector2(520, 30), 22, WHITE)
	var slider = HSlider.new(); slider.position = Vector2(724, y + 36); slider.size = Vector2(470, 34)
	slider.min_value = 0; slider.max_value = 100; slider.step = 1; slider.value = float(settings[key]) * 100
	page.add_child(slider)
	var amount = label_at(page, str(int(slider.value)) + " %", Vector2(1206, y + 32), Vector2(120, 38), 22, CYAN, false, mono_font)
	slider.value_changed.connect(func(value): settings[key] = value / 100.0; amount.text = str(int(value)) + " %"; apply_audio(); save_settings())

func build_settings():
	panel_at(page, Vector2(-14, -12), Vector2(690, 500))
	panel_at(page, Vector2(700, -12), Vector2(572, 500))
	toggle_at("Plein écran sans bordure · F11", "fullscreen", 4)
	toggle_at("Ambiance et transitions animées", "motion", 78)
	toggle_at("Couper tous les sons", "mute", 152)
	label_at(page, "Cadence maximale", Vector2(24, 236), Vector2(450, 34), 22, WHITE)
	var fps = OptionButton.new(); fps.position = Vector2(24, 278); fps.size = Vector2(440, 46)
	fps.add_theme_font_override("font", body_font); fps.add_theme_font_size_override("font_size", 21)
	for rate in [30, 60, 120]: fps.add_item(str(rate) + " images/s", rate)
	fps.select([30, 60, 120].find(int(settings.fps)))
	fps.item_selected.connect(func(index): settings.fps = fps.get_item_id(index); apply_settings(); save_settings())
	page.add_child(fps)
	slider_at("Volume général", "master", 0)
	slider_at("Interface · survols et confirmations", "ui", 118)
	slider_at("Ambiance sonore", "ambience", 236)
	button_at(page, "TESTER LE SON", Vector2(724, 360), Vector2(470, 54), func(): sound("confirm"))
	label_at(page, "Réglages du prototype, séparés de Desktop.\nÉchap revient au menu ; F11 quitte le plein écran.", Vector2(24, 372), Vector2(640, 80), 19, MUTED)

func build_audio():
	for bus in ["Interface", "Ambience"]:
		AudioServer.add_bus(); AudioServer.set_bus_name(AudioServer.bus_count - 1, bus)
	for key in ["hover", "confirm", "back"]:
		var player = AudioStreamPlayer.new(); player.stream = load("res://assets/" + key + ".wav"); player.bus = "Interface"; add_child(player); players[key] = player
	ambience = AudioStreamPlayer.new(); ambience.stream = load("res://assets/ambience.wav").duplicate(); ambience.bus = "Ambience"
	ambience.stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
	ambience.stream.loop_end = int(ambience.stream.get_length() * ambience.stream.mix_rate)
	add_child(ambience)
	if qa_dir.is_empty(): ambience.play()

func sound(key):
	if qa_dir.is_empty() and not settings.mute and players.has(key): players[key].play()

func apply_audio():
	AudioServer.set_bus_volume_db(0, linear_to_db(max(0.0001, float(settings.master))))
	AudioServer.set_bus_mute(0, bool(settings.mute) or float(settings.master) == 0)
	for key in ["ui", "ambience"]:
		var bus = AudioServer.get_bus_index("Interface" if key == "ui" else "Ambience")
		AudioServer.set_bus_volume_db(bus, linear_to_db(max(0.0001, float(settings[key]))))
		AudioServer.set_bus_mute(bus, float(settings[key]) == 0)

func apply_settings():
	Engine.max_fps = int(settings.fps)
	apply_audio()
	if qa_dir.is_empty(): DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if settings.fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)

func save_settings():
	for key in settings: config.set_value("preferences", key, settings[key])
	config.save(settings_path)

func _process(delta):
	if focus_pulse > 0.0: focus_pulse = max(0.0, focus_pulse - delta * 1.4)
	if DisplayServer.window_is_focused() and settings.motion:
		tick += delta
		# Le globe tourne lentement — seule vraie animation au repos.
		if holo_globe:
			holo_globe.rotation.y = tick * 0.18
			holo_globe.rotation.x = sin(tick * 0.11) * 0.12
			# À l'ouverture d'une fiche, il se resserre brièvement (vivant à l'interaction).
			var s = 1.0 + focus_pulse * 0.12
			holo_globe.scale = Vector3(s, s, s)
		if holo_glow:
			holo_glow.light_energy = 2.0 + sin(tick * 0.5) * 0.15 + focus_pulse * 0.8
	if camera:
		# Léger flottement de caméra, très tenu, sans jamais balayer la scène.
		var drift = Vector3.ZERO
		if settings.motion:
			drift = Vector3(sin(tick * 0.16) * 0.05, cos(tick * 0.13) * 0.035, 0.0)
		camera.look_at(cam_target + drift)

func _unhandled_input(event):
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F11:
			settings.fullscreen = not settings.fullscreen; apply_settings(); save_settings(); get_viewport().set_input_as_handled()
		elif event.keycode == KEY_ESCAPE:
			if current_page != "home": sound("back"); back_action()
			else: settings.fullscreen = false; apply_settings(); save_settings()

func open_desktop():
	var exe = OS.get_environment("LOCALAPPDATA").path_join("Programs/ChaosticTool/ChaosticTool.exe")
	if FileAccess.file_exists(exe):
		OS.create_process(exe, [])
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MINIMIZED)
	else: status_label.text = "Desktop introuvable. Installez la release Desktop pour lancer les outils."

func snap(name):
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(qa_dir.path_join(name + ".png"))

func run_qa():
	await get_tree().create_timer(1.2).timeout
	await snap("accueil")
	show_page("arsenal")
	await get_tree().create_timer(1.1).timeout
	await snap("arsenal")
	# Sélectionne Nmap pour la fiche de démonstration si présent.
	for i in range(catalog.size()):
		if str(catalog[i].name) == "Nmap": selected_tool = i; break
	show_page("fiche")
	await get_tree().create_timer(1.1).timeout
	await snap("fiche")
	show_page("settings")
	await get_tree().create_timer(1.1).timeout
	await snap("parametres")
	settings.master = 0.27; settings.mute = true; settings.motion = false; settings.fps = 30
	apply_settings(); save_settings()
	var readback = ConfigFile.new(); readback.load(settings_path)
	var result = {"catalog": catalog.size(), "settings_persisted": readback.get_value("preferences", "master") == 0.27, "mute": AudioServer.is_bus_mute(0), "fps": Engine.max_fps, "renderer": RenderingServer.get_video_adapter_name(), "driver": RenderingServer.get_current_rendering_method()}
	players.confirm.play()
	await get_tree().create_timer(0.03).timeout
	result["audio_player_started"] = players.confirm.playing
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	await get_tree().create_timer(0.3).timeout
	result["fullscreen"] = DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var file = FileAccess.open(qa_dir.path_join("validation.json"), FileAccess.WRITE); file.store_string(JSON.stringify(result, "  ")); file.close()
	get_tree().quit()
