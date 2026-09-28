extends Node3D

const GOLD = Color("e5ee36")
const CYAN = Color("69e1dd")
const WHITE = Color("e4ede8")
const MUTED = Color("98b0b4")
var camera: Camera3D
var sculpture: Node3D
var light: OmniLight3D
var page: Control
var root_ui: Control
var title: Label
var subtitle: Label
var back_button: Button
var scene_tween: Tween
var ui_tween: Tween
var display_font = preload("res://assets/Orbitron.ttf")
var body_font = preload("res://assets/Exo2.ttf")
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

func material(color: Color, emission = 0.0):
	var m = StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.4
	m.metallic = 0.55
	if emission > 0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = emission
	return m

func box(parent: Node3D, pos: Vector3, size: Vector3, mat: Material):
	var node = MeshInstance3D.new()
	var mesh = BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.material_override = mat
	node.position = pos
	parent.add_child(node)
	return node

func build_world():
	var env_node = WorldEnvironment.new()
	var env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("071115")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("75969b")
	env.ambient_light_energy = 0.45
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.fog_enabled = true
	env.fog_light_color = Color("18353a")
	env.fog_density = 0.016
	env_node.environment = env
	add_child(env_node)
	var key_light = DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-45,-25,0)
	key_light.light_color = Color("89c8ce")
	key_light.light_energy = 1.3
	key_light.shadow_enabled = true
	add_child(key_light)
	light = OmniLight3D.new()
	light.position = Vector3(3,4,3)
	light.light_color = CYAN
	light.light_energy = 3.0
	light.omni_range = 14
	add_child(light)
	var dark = material(Color("15252e"))
	var metal = material(Color("23333a"))
	var neon = material(CYAN,2.0)
	var yellow = material(GOLD,1.4)
	box(self,Vector3(0,-0.3,0),Vector3(60,0.4,60),material(Color("121c22")))
	for i in range(-8,9):
		box(self,Vector3(i*3,-0.075,0),Vector3(0.018,0.012,45),material(Color("24494b"),0.5))
		box(self,Vector3(0,-0.075,i*3),Vector3(45,0.012,0.018),material(Color("24494b"),0.5))
	# A physical corridor with lit server architecture, not a flat background.
	for side in [-1,1]:
		for i in range(7):
			var x = side * (7.5 + (i%2)*0.6)
			var z = -float(i)*3.4
			box(self,Vector3(x,3,z),Vector3(1.4,6,1.6),dark)
			box(self,Vector3(x-side*0.72,3,z),Vector3(0.03,5.4,0.9),metal)
			for j in range(5):
				box(self,Vector3(x-side*0.75,0.9+j,z+0.05),Vector3(0.06,0.06,1.0),neon)
			box(self,Vector3(x,6.0,z),Vector3(1.6,0.12,1.8),yellow if i%3==0 else neon)
		box(self,Vector3(side*6.0,0.03,-10),Vector3(0.12,0.08,28),yellow)
	# Structural ribs and a distant bulkhead give the space a ceiling and depth.
	for i in range(6):
		box(self,Vector3(0,7.6,-i*4),Vector3(18,0.30,0.35),metal)
		box(self,Vector3(0,7.42,-i*4),Vector3(8,0.04,0.08),neon)
	box(self,Vector3(0,4,-25),Vector3(19,8,0.5),dark)
	for i in range(-3,4):
		box(self,Vector3(i*2.4,4,-24.7),Vector3(0.08,6,0.06),neon)
	# Central hardware sculpture: layered pedestal and illuminated core.
	box(self,Vector3(2,0.18,-1),Vector3(4,0.4,4),metal)
	box(self,Vector3(2,0.42,-1),Vector3(3.7,0.08,3.7),neon)
	box(self,Vector3(2,0.65,-1),Vector3(3.4,0.4,3.4),dark)
	sculpture = Node3D.new()
	sculpture.position = Vector3(2,3.0,-1)
	add_child(sculpture)
	var core = box(sculpture,Vector3.ZERO,Vector3(1.65,2.7,1.65),material(Color("152d36")))
	core.rotation_degrees = Vector3(0,35,0)
	for i in range(4):
		var angle = i*PI/2
		box(sculpture,Vector3(cos(angle)*1.3,0,sin(angle)*1.3),Vector3(0.06,3.2,0.06),yellow)
	for height in [-1.65,1.65]:
		var ring = MeshInstance3D.new()
		var torus = TorusMesh.new()
		torus.inner_radius = 1.65
		torus.outer_radius = 1.70
		torus.rings = 32
		torus.ring_segments = 8
		ring.mesh = torus
		ring.material_override = neon
		ring.position.y = height
		sculpture.add_child(ring)
	for i in range(12):
		box(sculpture,Vector3(0,-1.1+i*0.2,0.87),Vector3(1.2,0.025,0.02),neon)
	camera = Camera3D.new()
	camera.position = Vector3(10,5.5,13)
	camera.fov = 55
	add_child(camera)
	camera.look_at(Vector3(0,2,-3))
	camera.current = true

func label_at(parent, text, at, size, font_size = 22, color = WHITE, display = false):
	var item = Label.new()
	item.text = text
	item.position = at
	item.size = size
	item.add_theme_font_override("font",display_font if display else body_font)
	item.add_theme_font_size_override("font_size",font_size)
	item.add_theme_color_override("font_color",color)
	item.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(item)
	return item

func style(color, border):
	var s = StyleBoxFlat.new()
	s.bg_color = color
	s.border_color = border
	s.set_border_width_all(1)
	s.border_width_left = 4
	s.content_margin_left = 22
	s.content_margin_right = 20
	return s

func button_at(parent, text, at, size, action, primary = false):
	var b = Button.new()
	b.text = text
	b.position = at
	b.size = size
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_font_override("font",body_font)
	b.add_theme_font_size_override("font_size",25)
	b.add_theme_color_override("font_color",Color("0d161c") if primary else WHITE)
	b.add_theme_color_override("font_hover_color",GOLD)
	b.add_theme_color_override("font_focus_color",GOLD)
	b.add_theme_stylebox_override("normal",style(GOLD if primary else Color(0.025,0.065,0.08,0.80),Color("607170")))
	b.add_theme_stylebox_override("hover",style(Color(0.08,0.16,0.18,0.94),GOLD))
	b.add_theme_stylebox_override("focus",style(Color(0.07,0.15,0.16,0.97),GOLD))
	b.add_theme_stylebox_override("pressed",style(Color(0.02,0.08,0.10,0.98),CYAN))
	b.mouse_entered.connect(func(): b.grab_focus())
	b.focus_entered.connect(func(): sound("hover"))
	b.pressed.connect(func(): sound("confirm");action.call())
	parent.add_child(b)
	return b

func build_ui():
	var canvas = CanvasLayer.new()
	add_child(canvas)
	root_ui = Control.new()
	root_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	canvas.add_child(root_ui)
	var veil = ColorRect.new()
	veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var shader = Shader.new()
	shader.code = "shader_type canvas_item; void fragment(){float a=mix(0.93,0.08,smoothstep(0.02,0.9,UV.x));float v=smoothstep(0.30,0.76,length(UV-vec2(0.5)));COLOR=vec4(0.012,0.025,0.035,min(0.97,a+v*0.38));}"
	var sm = ShaderMaterial.new();sm.shader=shader;veil.material=sm
	root_ui.add_child(veil)
	label_at(root_ui,"CHAOSTIC / TOOL",Vector2(64,38),Vector2(900,35),23,CYAN,true)
	label_at(root_ui,"GAME INTERFACE  /  PRÉVISUALISATION",Vector2(64,79),Vector2(1000,28),15,MUTED,true)
	title = label_at(root_ui,"",Vector2(64,139),Vector2(1200,85),55,GOLD,true)
	subtitle = label_at(root_ui,"",Vector2(68,229),Vector2(1300,50),23,WHITE)
	page = Control.new();page.position=Vector2(68,300);page.size=Vector2(1460,510);root_ui.add_child(page)
	back_button = button_at(root_ui,"←  RETOUR",Vector2(1300,44),Vector2(235,46),func():show_page("home"))
	status_label = label_at(root_ui,"F11  PLEIN ÉCRAN     /     ÉCHAP  RETOUR     /     FLÈCHES + ENTRÉE",Vector2(64,848),Vector2(1300,30),16,MUTED)

func clear_page():
	for child in page.get_children(): page.remove_child(child);child.queue_free()

func show_page(which):
	current_page=which
	clear_page()
	back_button.visible=which!="home"
	if scene_tween:scene_tween.kill()
	if ui_tween:ui_tween.kill()
	var destination = Vector3(10,5.5,13)
	match which:
		"home":
			title.text="VOTRE PROCHAINE\nOPÉRATION."
			title.add_theme_font_size_override("font_size",46)
			subtitle.text="Entrez dans votre espace de commandement."
			subtitle.position.y=251
			button_at(page,"01   EXPLORER L’ARSENAL",Vector2(0,28),Vector2(620,78),func():show_page("arsenal"),true)
			button_at(page,"02   IMAGE & SON",Vector2(0,123),Vector2(620,78),func():show_page("settings"))
			button_at(page,"03   OUVRIR DESKTOP 0.8",Vector2(0,218),Vector2(620,78),open_desktop)
			button_at(page,"QUITTER",Vector2(0,325),Vector2(300,62),func():get_tree().quit())
			label_at(page,"Prototype graphique : les opérations restent dans Desktop.\nAucun outil n’est lancé depuis cette prévisualisation.",Vector2(0,413),Vector2(850,62),19,MUTED)
		"arsenal":
			title.text="ARSENAL"
			title.add_theme_font_size_override("font_size",55)
			subtitle.text="Le catalogue réel de ChaosticTool. Choisissez une fiche."
			subtitle.position.y=229
			destination=Vector3(5,4,9)
			build_arsenal()
		"settings":
			title.text="IMAGE & SON"
			title.add_theme_font_size_override("font_size",55)
			subtitle.text="Réglez votre expérience. Les préférences sont conservées."
			subtitle.position.y=229
			destination=Vector3(12,3,7)
			build_settings()
	if settings.motion:
		page.modulate.a=0
		page.position.x=95
		ui_tween=create_tween().set_parallel(true)
		ui_tween.tween_property(page,"modulate:a",1.0,0.32)
		ui_tween.tween_property(page,"position:x",68.0,0.38).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		scene_tween=create_tween()
		scene_tween.tween_property(camera,"position",destination,0.85).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	else:
		page.modulate.a=1;page.position.x=68;camera.position=destination
	var controls=page.find_children("*","Button",true,false)
	if not controls.is_empty(): controls[0].grab_focus()

func build_arsenal():
	var search=LineEdit.new();search.position=Vector2.ZERO;search.size=Vector2(600,48)
	search.placeholder_text="Rechercher un outil…";search.add_theme_font_size_override("font_size",22);page.add_child(search)
	var list=ItemList.new();list.position=Vector2(0,68);list.size=Vector2(600,410)
	list.add_theme_font_override("font",body_font);list.add_theme_font_size_override("font_size",24)
	list.add_theme_constant_override("v_separation",14)
	list.add_theme_stylebox_override("panel",style(Color(0.02,0.05,0.07,0.92),Color("43666b")))
	page.add_child(list)
	var detail=label_at(page,"",Vector2(650,8),Vector2(720,70),32,GOLD,true)
	var description=label_at(page,"",Vector2(650,98),Vector2(650,210),23,WHITE)
	description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var profiles=label_at(page,"",Vector2(650,316),Vector2(690,100),19,CYAN)
	profiles.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	label_at(page,"Consultation du catalogue · exécution non raccordée",Vector2(650,443),Vector2(700,40),18,MUTED)
	var populate=func(query):
		list.clear()
		for i in range(catalog.size()):
			var tool=catalog[i]
			if query.is_empty() or (str(tool.name)+" "+str(tool.get("group",""))).to_lower().contains(query.to_lower()):
				var row=list.add_item(str(tool.name));list.set_item_metadata(row,i)
	var select=func(index):
		var tool=catalog[list.get_item_metadata(index)]
		detail.text=str(tool.name).to_upper()
		description.text=str(tool.get("group",""))+"\n\n"+str(tool.get("desc",""))
		profiles.text=str(tool.get("presets",[]).size())+" profil(s) natif(s) · "+str(tool.get("linux_presets",[]).size())+" profil(s) Linux\n"+str(tool.get("note",""))
		sound("hover")
	search.text_changed.connect(populate)
	list.item_selected.connect(select)
	populate.call("")
	if list.item_count>0:list.select(0);select.call(0)

func toggle_at(text,key,y):
	var check=CheckButton.new();check.text=text;check.position=Vector2(0,y);check.size=Vector2(690,44)
	check.add_theme_font_override("font",body_font);check.add_theme_font_size_override("font_size",23)
	check.button_pressed=bool(settings[key]);page.add_child(check)
	check.toggled.connect(func(value):settings[key]=value;apply_settings();save_settings();sound("confirm"))
	return check

func slider_at(text,key,y):
	label_at(page,text,Vector2(720,y),Vector2(530,30),23,WHITE)
	var slider=HSlider.new();slider.position=Vector2(720,y+37);slider.size=Vector2(480,36)
	slider.min_value=0;slider.max_value=100;slider.step=1;slider.value=float(settings[key])*100
	page.add_child(slider)
	var amount=label_at(page,str(int(slider.value))+" %",Vector2(1220,y+32),Vector2(130,38),22,CYAN)
	slider.value_changed.connect(func(value):settings[key]=value/100.0;amount.text=str(int(value))+" %";apply_audio();save_settings())

func build_settings():
	var backdrop=Panel.new();backdrop.position=Vector2(-20,-12);backdrop.size=Vector2(1420,500)
	backdrop.add_theme_stylebox_override("panel",style(Color(0.015,0.035,0.05,0.90),Color("426366")))
	page.add_child(backdrop)
	toggle_at("Plein écran sans bordure · F11","fullscreen",0)
	toggle_at("Ambiance et transitions animées","motion",75)
	toggle_at("Couper tous les sons","mute",150)
	label_at(page,"Cadence maximale",Vector2(0,233),Vector2(450,35),23,WHITE)
	var fps=OptionButton.new();fps.position=Vector2(0,278);fps.size=Vector2(450,48)
	for rate in [30,60,120]:fps.add_item(str(rate)+" images/s",rate)
	fps.select([30,60,120].find(int(settings.fps)))
	fps.item_selected.connect(func(index):settings.fps=fps.get_item_id(index);apply_settings();save_settings())
	page.add_child(fps)
	slider_at("Volume général","master",0)
	slider_at("Interface · survols et confirmations","ui",120)
	slider_at("Ambiance sonore","ambience",240)
	button_at(page,"TESTER LE SON",Vector2(720,365),Vector2(480,55),func():sound("confirm"))
	label_at(page,"Réglages du prototype, séparés de Desktop.\nÉchap revient au menu ; F11 quitte le plein écran.",Vector2(0,389),Vector2(650,80),20,MUTED)

func build_audio():
	for bus in ["Interface","Ambience"]:
		AudioServer.add_bus();AudioServer.set_bus_name(AudioServer.bus_count-1,bus)
	for key in ["hover","confirm","back"]:
		var player=AudioStreamPlayer.new();player.stream=load("res://assets/"+key+".wav");player.bus="Interface";add_child(player);players[key]=player
	ambience=AudioStreamPlayer.new();ambience.stream=load("res://assets/ambience.wav").duplicate();ambience.bus="Ambience"
	ambience.stream.loop_mode=AudioStreamWAV.LOOP_FORWARD
	ambience.stream.loop_end=int(ambience.stream.get_length()*ambience.stream.mix_rate)
	add_child(ambience)
	if qa_dir.is_empty():ambience.play()

func sound(key):
	if qa_dir.is_empty() and not settings.mute:players[key].play()

func apply_audio():
	AudioServer.set_bus_volume_db(0,linear_to_db(max(0.0001,float(settings.master))))
	AudioServer.set_bus_mute(0,bool(settings.mute) or float(settings.master)==0)
	for key in ["ui","ambience"]:
		var bus=AudioServer.get_bus_index("Interface" if key=="ui" else "Ambience")
		AudioServer.set_bus_volume_db(bus,linear_to_db(max(0.0001,float(settings[key]))))
		AudioServer.set_bus_mute(bus,float(settings[key])==0)

func apply_settings():
	Engine.max_fps=int(settings.fps)
	apply_audio()
	if qa_dir.is_empty():DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if settings.fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)

func save_settings():
	for key in settings:config.set_value("preferences",key,settings[key])
	config.save(settings_path)

func _process(delta):
	if DisplayServer.window_is_focused() and settings.motion:
		tick+=delta
		sculpture.rotation.y=sin(tick*0.13)*0.16
		light.light_energy=2.8+sin(tick*0.4)*0.18
	if camera:camera.look_at(Vector3(0,2,-3))

func _unhandled_input(event):
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_F11:
			settings.fullscreen=not settings.fullscreen;apply_settings();save_settings();get_viewport().set_input_as_handled()
		elif event.keycode==KEY_ESCAPE:
			if current_page!="home":sound("back");show_page("home")
			else:settings.fullscreen=false;apply_settings();save_settings()

func open_desktop():
	var exe=OS.get_environment("LOCALAPPDATA").path_join("Programs/ChaosticTool/ChaosticTool.exe")
	if FileAccess.file_exists(exe):
		OS.create_process(exe,[])
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_MINIMIZED)
	else:status_label.text="Desktop introuvable. Installez la release Desktop pour lancer les outils."

func snap(name):
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(qa_dir.path_join(name+".png"))

func run_qa():
	await get_tree().create_timer(1.2).timeout
	await snap("accueil")
	show_page("arsenal")
	await get_tree().create_timer(1.1).timeout
	await snap("arsenal")
	show_page("settings")
	await get_tree().create_timer(1.1).timeout
	await snap("parametres")
	settings.master=0.27;settings.mute=true;settings.motion=false;settings.fps=30
	apply_settings();save_settings()
	var readback=ConfigFile.new();readback.load(settings_path)
	var result={"catalog":catalog.size(),"settings_persisted":readback.get_value("preferences","master")==0.27,"mute":AudioServer.is_bus_mute(0),"fps":Engine.max_fps,"renderer":RenderingServer.get_video_adapter_name(),"driver":RenderingServer.get_current_rendering_method()}
	players.confirm.play()
	await get_tree().create_timer(0.03).timeout
	result["audio_player_started"]=players.confirm.playing
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	await get_tree().create_timer(0.3).timeout
	result["fullscreen"]=DisplayServer.window_get_mode()==DisplayServer.WINDOW_MODE_FULLSCREEN
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var file=FileAccess.open(qa_dir.path_join("validation.json"),FileAccess.WRITE);file.store_string(JSON.stringify(result,"  "));file.close()
	get_tree().quit()
