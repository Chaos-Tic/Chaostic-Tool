extends Node3D

# ChaosticTool — prévisualisation, thème sobre.
# Un vrai moteur 3D, mais une direction posée : matières mates, lumière douce de
# studio, une seule teinte d'accent acier, typographie en casse normale. Pas de
# néons, pas d'hologramme lumineux, pas d'effets qui balayent. La fenêtre reste
# toujours fenêtrée. L'interface s'anime avec retenue, surtout à l'interaction.

const INK    = Color("14171a")   # fond / texte sur clair
const SURF    = Color("1c2024")  # panneaux
const SURF2   = Color("23282d")  # boutons au repos
const LINE    = Color("39424a")  # bordures
const TEXT    = Color("e7e9eb")
const MUTED   = Color("969ca3")
const ACCENT  = Color("9fb2bd")   # acier doux, unique accent

var camera: Camera3D
var cam_target := Vector3(2.4, 1.7, -2.0)
var focal: Node3D
var spin: Node3D
var page: Control
var root_ui: Control
var title: Label
var subtitle: Label
var back_button: Button
var scene_tween: Tween
var target_tween: Tween
var ui_tween: Tween
var display_font = preload("res://assets/Exo2.ttf")
var body_font = preload("res://assets/Exo2.ttf")
var config = ConfigFile.new()
var settings = {"master":0.45,"ui":0.5,"ambience":0.18,"mute":false,"motion":true,"fps":60}
var players = {}
var ambience: AudioStreamPlayer
var tick = 0.0
var current_page = "home"
var catalog = []
var qa_dir = ""
var settings_path = "user://settings.cfg"
var status_label: Label
var selected_tool := 0

# Cadrage caméra par section : position + cible du regard. L'objet focal reste à
# droite pour dégager la colonne de texte, à gauche, sur fond sombre lisible.
const FRAMES = {
	"home":     {"pos": Vector3(-5.2, 3.1, 8.6), "look": Vector3(2.6, 1.7, -2.2)},
	"arsenal":  {"pos": Vector3(-3.3, 2.85, 7.4), "look": Vector3(2.9, 1.65, -2.4)},
	"fiche":    {"pos": Vector3(-1.3, 2.6, 6.3), "look": Vector3(3.0, 1.7, -2.6)},
	"settings": {"pos": Vector3(-6.0, 3.3, 8.9), "look": Vector3(1.8, 1.6, -2.0)},
}

func _ready():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--qa-dir="): qa_dir = arg.trim_prefix("--qa-dir=")
	if not qa_dir.is_empty(): settings_path = qa_dir.path_join("settings.cfg")
	config.load(settings_path)
	for key in settings: settings[key] = config.get_value("preferences", key, settings[key])
	catalog = JSON.parse_string(FileAccess.get_file_as_string("res://catalog.json"))
	build_audio()
	build_world()
	build_ui()
	apply_settings()
	show_page("home")
	if not qa_dir.is_empty(): run_qa.call_deferred()

# ------------------------------------------------------------------ matériaux

func material(color: Color, rough = 0.6, metal = 0.25, emission = 0.0):
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
	mesh.radial_segments = 56
	node.mesh = mesh
	node.material_override = mat
	node.position = pos
	parent.add_child(node)
	return node

func ring(parent: Node3D, inner: float, outer: float, mat: Material):
	var node = MeshInstance3D.new()
	var torus = TorusMesh.new()
	torus.inner_radius = inner
	torus.outer_radius = outer
	torus.rings = 48
	torus.ring_segments = 12
	node.mesh = torus
	node.material_override = mat
	parent.add_child(node)
	return node

# --------------------------------------------------------------------- monde

func build_world():
	var env_node = WorldEnvironment.new()
	var env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("15181c")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("3b434a")
	env.ambient_light_energy = 0.8
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 1.0
	env.fog_enabled = true
	env.fog_light_color = Color("1a1f24")
	env.fog_density = 0.012
	env.fog_aerial_perspective = 0.3
	env_node.environment = env
	add_child(env_node)

	# Lumière douce de studio : une clé chaude-neutre, un remplissage froid léger.
	var key_light = DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-48, -40, 0)
	key_light.light_color = Color("d5dade")
	key_light.light_energy = 1.05
	key_light.shadow_enabled = true
	key_light.shadow_blur = 1.5
	add_child(key_light)
	var fill = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-18, 128, 0)
	fill.light_color = Color("6d777d")
	fill.light_energy = 0.4
	add_child(fill)

	build_room()
	build_focal()

	camera = Camera3D.new()
	camera.fov = 50
	camera.position = FRAMES.home.pos
	cam_target = FRAMES.home.look
	add_child(camera)
	camera.look_at(cam_target)
	camera.current = true

func build_room():
	# Sol mat, sans grille lumineuse : un léger assombrissement vers les bords.
	var floor_plane = MeshInstance3D.new()
	var pm = PlaneMesh.new()
	pm.size = Vector2(48, 48)
	floor_plane.mesh = pm
	var floor_mat = ShaderMaterial.new()
	var floor_shader = Shader.new()
	floor_shader.code = """
shader_type spatial;
uniform vec3 base_color = vec3(0.075, 0.085, 0.095);
void fragment() {
	float dist = length(UV - vec2(0.5));
	float fade = smoothstep(0.55, 0.12, dist);
	ALBEDO = base_color * (0.55 + 0.45 * fade);
	ROUGHNESS = 0.7;
	METALLIC = 0.1;
}
"""
	floor_mat.shader = floor_shader
	floor_plane.material_override = floor_mat
	add_child(floor_plane)

	var wall = material(Color("1a1e22"), 0.75, 0.1)
	var wall_dark = material(Color("14181c"), 0.8, 0.1)
	var ledge = material(Color("242a30"), 0.55, 0.3)

	# Fond architectural calme : un mur mat, une niche en léger retrait derrière
	# l'objet, une tablette horizontale. Aucun écran de données, aucun néon.
	box(self, Vector3(1.5, 4.0, -13.6), Vector3(30, 9.0, 0.6), wall)
	box(self, Vector3(3.0, 3.6, -13.2), Vector3(9.5, 6.2, 0.2), wall_dark)          # niche
	box(self, Vector3(3.0, 6.85, -13.1), Vector3(9.9, 0.14, 0.32), ledge)           # linteau
	box(self, Vector3(3.0, 0.55, -13.1), Vector3(9.9, 0.14, 0.32), ledge)           # seuil
	box(self, Vector3(1.5, 2.1, -12.4), Vector3(26, 0.16, 0.7), ledge)              # tablette basse

	for side in [-1, 1]:
		var x = side * 12.6
		box(self, Vector3(x, 4.0, -6.0), Vector3(0.6, 9.0, 16), wall, side * 6.0)

	box(self, Vector3(1.5, 8.5, -6.0), Vector3(30, 0.5, 16), wall)

func build_focal():
	# Objet focal sobre : un socle mat et une sculpture mate qui tourne lentement,
	# posée sous un projecteur doux. Présence par la lumière et la matière, pas par
	# l'émission. Deux fins anneaux d'acier croisent une sphère mate.
	focal = Node3D.new()
	focal.position = Vector3(3.0, 0, -2.2)
	add_child(focal)

	var plinth_mat = material(Color("20262b"), 0.5, 0.35)
	var plinth_top = material(Color("2a3137"), 0.45, 0.45)
	cyl(focal, Vector3(0, 0.12, 0), 0.24, 1.5, 1.7, material(Color("161a1e"), 0.6, 0.2))
	cyl(focal, Vector3(0, 0.5, 0), 0.6, 1.25, 1.4, plinth_mat)
	cyl(focal, Vector3(0, 0.82, 0), 0.06, 1.2, 1.22, plinth_top)

	spin = Node3D.new()
	spin.position = Vector3(0, 1.85, 0)
	focal.add_child(spin)

	var steel = material(Color("aeb9c0"), 0.35, 0.75)
	var steel_dim = material(Color("77828a"), 0.4, 0.65)
	var core_mat = material(Color("3a434a"), 0.5, 0.4)

	var core = MeshInstance3D.new()
	var sphere = SphereMesh.new()
	sphere.radius = 0.62
	sphere.height = 1.24
	sphere.radial_segments = 40
	sphere.rings = 22
	core.mesh = sphere
	core.material_override = core_mat
	spin.add_child(core)

	ring(spin, 0.86, 0.90, steel).rotation_degrees = Vector3(78, 0, 0)
	ring(spin, 0.98, 1.01, steel_dim).rotation_degrees = Vector3(20, 40, 10)
	# Un fin socle-accent acier sur le plateau, seule touche de teinte.
	ring(focal, 1.12, 1.16, material(ACCENT, 0.4, 0.6)).position.y = 0.86

	# Projecteur doux au-dessus, pour détacher la sculpture du fond.
	var spot = SpotLight3D.new()
	spot.position = Vector3(3.0, 5.4, -1.6)
	spot.rotation_degrees = Vector3(-90, 0, 0)
	spot.light_color = Color("e4e8ea")
	spot.light_energy = 3.2
	spot.spot_range = 9.0
	spot.spot_angle = 26.0
	spot.spot_attenuation = 1.4
	spot.shadow_enabled = true
	add_child(spot)

# ----------------------------------------------------------------------- UI

func label_at(parent, text, at, size, font_size = 22, color = TEXT, display = false, font_override = null, wrap = false):
	var item = Label.new()
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

func style(bg, border, left_accent = 1):
	var s = StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(1)
	s.border_width_left = left_accent
	s.content_margin_left = 22
	s.content_margin_right = 20
	s.set_corner_radius_all(4)
	return s

func panel_at(parent, at, size):
	var p = Panel.new()
	p.position = at
	p.size = size
	var s = style(Color(SURF.r, SURF.g, SURF.b, 0.975), LINE, 1)
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
	b.add_theme_font_size_override("font_size", 23)
	b.add_theme_color_override("font_color", INK if primary else TEXT)
	b.add_theme_color_override("font_hover_color", INK if primary else TEXT)
	b.add_theme_color_override("font_focus_color", INK if primary else TEXT)
	if primary:
		b.add_theme_stylebox_override("normal", style(ACCENT, ACCENT, 1))
		b.add_theme_stylebox_override("hover", style(Color("b3c3cc"), Color("b3c3cc"), 1))
		b.add_theme_stylebox_override("focus", style(Color("b3c3cc"), Color("cdd8de"), 1))
		b.add_theme_stylebox_override("pressed", style(Color("8aa0ac"), ACCENT, 1))
	else:
		b.add_theme_stylebox_override("normal", style(Color(SURF2.r, SURF2.g, SURF2.b, 0.9), LINE, 1))
		b.add_theme_stylebox_override("hover", style(Color("2b3238"), ACCENT, 3))
		b.add_theme_stylebox_override("focus", style(Color("2b3238"), ACCENT, 3))
		b.add_theme_stylebox_override("pressed", style(Color("20262b"), ACCENT, 3))
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

	# Voile ancré à gauche : la colonne de texte reste sur du sombre. Statique.
	var veil = ColorRect.new()
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var shader = Shader.new()
	shader.code = "shader_type canvas_item; void fragment(){ float a = mix(0.9, 0.0, smoothstep(0.0, 0.6, UV.x)); float bot = smoothstep(0.78, 1.0, UV.y) * 0.35; COLOR = vec4(0.055, 0.062, 0.07, clamp(a + bot, 0.0, 0.92)); }"
	var sm = ShaderMaterial.new(); sm.shader = shader; veil.material = sm
	root_ui.add_child(veil)

	label_at(root_ui, "ChaosticTool", Vector2(64, 42), Vector2(900, 40), 26, TEXT, true)
	label_at(root_ui, "Prévisualisation", Vector2(66, 84), Vector2(1000, 26), 15, MUTED)
	title = label_at(root_ui, "", Vector2(64, 140), Vector2(1200, 120), 42, TEXT, true)
	subtitle = label_at(root_ui, "", Vector2(66, 232), Vector2(760, 60), 20, MUTED)
	page = Control.new(); page.position = Vector2(66, 300); page.size = Vector2(1500, 520); root_ui.add_child(page)
	back_button = button_at(root_ui, "←  Retour", Vector2(1310, 44), Vector2(225, 46), func(): back_action())
	status_label = label_at(root_ui, "Échap  retour       ·       Flèches + Entrée", Vector2(64, 852), Vector2(1300, 28), 15, MUTED)

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
	back_button.text = "←  Arsenal" if which == "fiche" else "←  Accueil"
	if scene_tween: scene_tween.kill()
	if ui_tween: ui_tween.kill()
	if target_tween: target_tween.kill()
	match which:
		"home":
			title.text = "Bienvenue."
			subtitle.text = "Choisissez une section pour commencer."
			subtitle.position.y = 244
			build_home()
		"arsenal":
			title.text = "Arsenal"
			subtitle.text = "Le catalogue réel de ChaosticTool. Choisissez un outil, ouvrez sa fiche."
			subtitle.position.y = 232
			build_arsenal()
		"fiche":
			subtitle.position.y = 232
			build_fiche()
		"settings":
			title.text = "Image & son"
			subtitle.text = "Réglez votre expérience. Les préférences sont conservées."
			subtitle.position.y = 232
			build_settings()

	var frame = FRAMES.get(which, FRAMES.home)
	if settings.motion and camera:
		page.modulate.a = 0
		page.position.x = 88
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
	button_at(page, "Explorer l'arsenal", Vector2(0, 20), Vector2(560, 70), func(): show_page("arsenal"))
	button_at(page, "Image & son", Vector2(0, 104), Vector2(560, 70), func(): show_page("settings"))
	button_at(page, "Ouvrir Desktop 0.8", Vector2(0, 188), Vector2(560, 70), open_desktop)
	button_at(page, "Quitter", Vector2(0, 288), Vector2(270, 58), func(): get_tree().quit())
	label_at(page, "Prévisualisation graphique : les opérations restent dans Desktop 0.8.\nAucun outil n'est lancé depuis cette fenêtre.", Vector2(2, 372), Vector2(820, 64), 17, MUTED)

func build_arsenal():
	panel_at(page, Vector2(-14, -12), Vector2(624, 512))
	var search = LineEdit.new(); search.position = Vector2(8, 8); search.size = Vector2(584, 46)
	search.placeholder_text = "Rechercher un outil…"
	search.add_theme_font_override("font", body_font)
	search.add_theme_font_size_override("font_size", 21)
	search.add_theme_color_override("font_color", TEXT)
	search.add_theme_stylebox_override("normal", style(Color("181c20"), LINE, 1))
	search.add_theme_stylebox_override("focus", style(Color("1d2226"), ACCENT, 1))
	page.add_child(search)
	var list = ItemList.new(); list.position = Vector2(8, 66); list.size = Vector2(584, 380)
	list.add_theme_font_override("font", body_font); list.add_theme_font_size_override("font_size", 23)
	list.add_theme_constant_override("v_separation", 12)
	list.add_theme_color_override("font_color", TEXT)
	list.add_theme_color_override("font_selected_color", TEXT)
	list.add_theme_stylebox_override("panel", style(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0))
	list.add_theme_stylebox_override("selected", style(Color("2b3238"), ACCENT, 3))
	list.add_theme_stylebox_override("selected_focus", style(Color("2b3238"), ACCENT, 3))
	page.add_child(list)

	panel_at(page, Vector2(636, -12), Vector2(636, 460))
	var detail = label_at(page, "", Vector2(660, 8), Vector2(600, 54), 32, TEXT, true)
	var meta = label_at(page, "", Vector2(662, 66), Vector2(590, 28), 17, ACCENT)
	var description = label_at(page, "", Vector2(662, 106), Vector2(588, 150), 22, TEXT, false, null, true)
	var profiles = label_at(page, "", Vector2(662, 268), Vector2(588, 90), 18, MUTED, false, null, true)
	var open_btn = button_at(page, "Ouvrir la fiche  →", Vector2(660, 372), Vector2(320, 56), func(): show_page("fiche"), true)

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
		detail.text = str(tool.name)
		meta.text = str(tool.get("group", "")) + "   ·   " + str(tool.get("category", ""))
		description.text = str(tool.get("desc", ""))
		profiles.text = "%d profil(s) natif(s)  ·  %d profil(s) Linux\nConsultation du catalogue — l'exécution reste dans Desktop." % [tool.get("presets", []).size(), tool.get("linux_presets", []).size()]
		open_btn.text = "Ouvrir la fiche " + str(tool.name) + "  →"
		sound("hover")
	search.text_changed.connect(populate)
	list.item_selected.connect(preview)
	list.item_activated.connect(func(index): preview.call(index); show_page("fiche"))
	populate.call("")
	var start = indices.find(selected_tool)
	if start < 0: start = 0
	if list.item_count > 0:
		list.select(start)
		preview.call(start)

func build_fiche():
	var tool = catalog[selected_tool]
	title.text = str(tool.name)
	subtitle.text = str(tool.get("group", "")) + "   ·   catégorie " + str(tool.get("category", ""))

	panel_at(page, Vector2(-14, -12), Vector2(700, 300))
	label_at(page, "Description", Vector2(8, 8), Vector2(400, 26), 16, ACCENT)
	label_at(page, str(tool.get("desc", "")), Vector2(8, 42), Vector2(660, 110), 22, TEXT, false, null, true)
	var note = str(tool.get("note", ""))
	if not note.is_empty():
		label_at(page, "Note", Vector2(8, 168), Vector2(400, 24), 15, MUTED)
		label_at(page, note, Vector2(8, 196), Vector2(660, 92), 17, MUTED, false, null, true)

	var natifs = tool.get("presets", []).size()
	var linux = tool.get("linux_presets", []).size()
	panel_at(page, Vector2(-14, 300), Vector2(700, 74))
	label_at(page, "%d profils natifs" % natifs, Vector2(20, 316), Vector2(320, 44), 24, TEXT, true)
	label_at(page, "%d profils Linux" % linux, Vector2(360, 316), Vector2(320, 44), 24, ACCENT, true)

	panel_at(page, Vector2(712, -12), Vector2(560, 386))
	label_at(page, "Profils disponibles — consultation", Vector2(732, 8), Vector2(520, 26), 15, ACCENT)
	var plist = ItemList.new(); plist.position = Vector2(732, 42); plist.size = Vector2(516, 320)
	plist.add_theme_font_override("font", body_font); plist.add_theme_font_size_override("font_size", 20)
	plist.add_theme_constant_override("v_separation", 9)
	plist.add_theme_color_override("font_color", TEXT)
	plist.add_theme_color_override("font_selected_color", TEXT)
	plist.add_theme_stylebox_override("panel", style(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0))
	plist.add_theme_stylebox_override("selected", style(Color("2b3238"), ACCENT, 3))
	plist.add_theme_stylebox_override("selected_focus", style(Color("2b3238"), ACCENT, 3))
	plist.focus_mode = Control.FOCUS_ALL
	for preset in tool.get("presets", []):
		plist.add_item("·  " + str(preset.get("label", "profil")))
	if plist.item_count == 0:
		plist.add_item("Profils Linux uniquement — voir Desktop.")
	page.add_child(plist)

	button_at(page, "Ouvrir dans Desktop 0.8", Vector2(-14, 392), Vector2(420, 58), open_desktop, true)
	label_at(page, "Exécution non raccordée à cette prévisualisation.", Vector2(424, 408), Vector2(520, 40), 16, MUTED)

func toggle_at(text, key, y):
	var check = CheckButton.new(); check.text = text; check.position = Vector2(24, y); check.size = Vector2(640, 44)
	check.add_theme_font_override("font", body_font); check.add_theme_font_size_override("font_size", 22)
	check.add_theme_color_override("font_color", TEXT)
	check.button_pressed = bool(settings[key]); page.add_child(check)
	check.toggled.connect(func(value): settings[key] = value; apply_settings(); save_settings(); sound("confirm"))
	return check

func slider_at(text, key, y):
	label_at(page, text, Vector2(724, y), Vector2(520, 30), 22, TEXT)
	var slider = HSlider.new(); slider.position = Vector2(724, y + 36); slider.size = Vector2(470, 34)
	slider.min_value = 0; slider.max_value = 100; slider.step = 1; slider.value = float(settings[key]) * 100
	page.add_child(slider)
	var amount = label_at(page, str(int(slider.value)) + " %", Vector2(1206, y + 32), Vector2(120, 38), 21, ACCENT)
	slider.value_changed.connect(func(value): settings[key] = value / 100.0; amount.text = str(int(value)) + " %"; apply_audio(); save_settings())

func build_settings():
	panel_at(page, Vector2(-14, -12), Vector2(690, 500))
	panel_at(page, Vector2(700, -12), Vector2(572, 500))
	toggle_at("Ambiance et transitions animées", "motion", 16)
	toggle_at("Couper tous les sons", "mute", 96)
	label_at(page, "Cadence maximale", Vector2(24, 188), Vector2(450, 34), 22, TEXT)
	var fps = OptionButton.new(); fps.position = Vector2(24, 230); fps.size = Vector2(440, 46)
	fps.add_theme_font_override("font", body_font); fps.add_theme_font_size_override("font_size", 21)
	for rate in [30, 60, 120]: fps.add_item(str(rate) + " images/s", rate)
	fps.select([30, 60, 120].find(int(settings.fps)))
	fps.item_selected.connect(func(index): settings.fps = fps.get_item_id(index); apply_settings(); save_settings())
	page.add_child(fps)
	label_at(page, "La fenêtre reste fenêtrée, redimensionnable.", Vector2(24, 300), Vector2(640, 40), 17, MUTED)
	slider_at("Volume général", "master", 0)
	slider_at("Interface · survols et confirmations", "ui", 118)
	slider_at("Ambiance sonore", "ambience", 236)
	button_at(page, "Tester le son", Vector2(724, 360), Vector2(470, 54), func(): sound("confirm"))
	label_at(page, "Réglages du prototype, séparés de Desktop.\nÉchap revient au menu.", Vector2(24, 372), Vector2(640, 80), 18, MUTED)

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
	# Toujours fenêtré : jamais de plein écran.
	if qa_dir.is_empty():
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)

func save_settings():
	for key in settings: config.set_value("preferences", key, settings[key])
	config.save(settings_path)

func _process(delta):
	if DisplayServer.window_is_focused() and settings.motion:
		tick += delta
		if spin:
			spin.rotation.y = tick * 0.14
			spin.rotation.x = sin(tick * 0.09) * 0.08
	if camera:
		var drift = Vector3.ZERO
		if settings.motion:
			drift = Vector3(sin(tick * 0.15) * 0.04, cos(tick * 0.12) * 0.03, 0.0)
		camera.look_at(cam_target + drift)

func _unhandled_input(event):
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE and current_page != "home":
			sound("back"); back_action()

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
	var result = {"catalog": catalog.size(), "settings_persisted": readback.get_value("preferences", "master") == 0.27, "mute": AudioServer.is_bus_mute(0), "fps": Engine.max_fps, "windowed": DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED, "renderer": RenderingServer.get_video_adapter_name(), "driver": RenderingServer.get_current_rendering_method()}
	players.confirm.play()
	await get_tree().create_timer(0.03).timeout
	result["audio_player_started"] = players.confirm.playing
	var file = FileAccess.open(qa_dir.path_join("validation.json"), FileAccess.WRITE); file.store_string(JSON.stringify(result, "  ")); file.close()
	get_tree().quit()
