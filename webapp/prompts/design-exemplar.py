# design.py — API and care exemplar. Concept "Ink & Clay", on the Coffee Berry plan.
# Concept: ink-blue joinery against clay plaster, slate at the bar, boards in the dining room.
# Palette: clay "#d9cfc1", ink "#2c3442", oxidised copper accent. Floors: slate bar, smoked oak dining, pavers outside.
# Light: daylight from the glazing, copper domes over tables, LED coves in the back bar, track light on the art.
# Rooms on this plan: terrace y<8.06 | dining x 0-10.93, y 9-12.33 (glazed south facade, street door x 9.3-10.3)
# bar room x 0-4.61, y 12.33-22.8 | prep x 4.61-9.03, y 12.33-14.61 | WC x 9.03-10.93, y 12.33-14.61.

K = Kit(SCENE, textures_dir=TEXTURES, seed=SEED, style=STYLE)
CEIL = 3.35
INK, CLAY = "#2c3442", "#d9cfc1"

# ---- envelope ---------------------------------------------------------------------------------
K.architecture(wall=CLAY, ceiling="plaster_white", ground="paving", skirt_mat="charcoal", door_mat="oak_smoked",
               floors={"seating_indoor": "oak_smoked", "service_counter": "slate", "seating_outdoor": "paving_herringbone",
                       "preparation": "hex_tile:#c9c6bd", "wc_disabled": "square_tile:#cfc9bd"})
K.facade(material="brick_stone", plinth=INK, plinth_h=0.5, cornice=INK, pilasters=INK, band=INK, awning=INK)
K.sign("coffee berry", (5.0, 8.85), rot=180, z=3.05, size=0.42, mat="copper", name="fascia")      # read from the street

# ---- every enclosed room is finished ----------------------------------------------------------
K.finish_walls("seating_indoor", finish=CLAY, dado=INK, dado_h=1.05, dado_style="panel", rail="copper", crown="plaster_white", skirting=INK)
K.finish_walls("service_counter", finish=CLAY, dado="zellige:#2c3442", dado_h=1.25, rail="copper", crown="plaster_white")
K.finish_walls("preparation", finish="subway:#ece9e1", skirting="charcoal")
K.finish_walls("wc_disabled", finish="#e4dfd4", dado="zellige:#2c3442", dado_h=1.4, rail="copper")

# ---- ceiling + floor zoning -------------------------------------------------------------------
K.ceiling_beams(0.3, 9.3, 10.6, 12.1, CEIL, spacing=1.3, mat="oak_smoked", axis="y")
K.ceiling_raft(0.8, 14.6, 3.4, 19.4, CEIL, style="slats", drop=0.32, led=True)
K.floor_zone([[8.7, 9.1], [10.83, 9.1], [10.83, 10.5], [8.7, 10.5]], "marble_mosaic", name="door_mat")

# ---- service line where the plan draws it ------------------------------------------------------
K.back_bar((0.125, 21.4), (0.125, 14.0), depth=0.6, shelves=3, shelf_z=(1.5, 1.9, 2.3), body=INK, top="marble_white", splash="zellige:#2c3442")
K.espresso_station((0.43, 19.9), rot=90, on=0.92, grinders=2)
K.menu_screen((0.15, 16.75), rot=-90, w=1.45, h=0.82, z=2.75)
K.counter_run((2.375, 15.95), (2.375, 19.4), depth=0.65, top="marble_white", front="fluted:veneer:#2c3442", rail="copper", name="counter")
K.till((2.1, 16.3), rot=-90, on=0.95, name="till1")   # screen faces the barista, west of this counter
K.display_case((2.05, 15.3), rot=90, w=1.3, d=0.83, body=INK, top="marble_white", name="pastry")
K.pendant_linear((2.05, 17.7), CEIL, rot=90, drop=1.05)
K.shelving_wall((4.51, 15.15), (4.51, 16.75), depth=0.35, h=0.85, levels=2, name="retail_low")
K.condiment_station((4.285, 17.3), rot=90)
K.track_light((3.8, 14.8), (3.8, 19.2), CEIL - 0.3, heads=4, aim=(2.0, 17.0))

# ---- appliances from the plan's legend, as detailed models --------------------------------------
K.plan_equipment()

# ---- dining ---------------------------------------------------------------------------------------
K.banquette((0.125, 12.1), (0.125, 9.35), depth=0.6, seat_mat="velvet:#8a5a3c", panel=None, cushions="channel")
for i, y in enumerate((9.85, 10.7, 11.55)):
    K.table((1.1, y), shape="round", size=0.65, top="marble_white", chairs=0, name=f"two{i}")
    K.chair((1.75, y), rot=-90, name=f"two{i}_chair")
    K.pendant((1.1, y), CEIL, drop=1.05, name=f"pend_two{i}")
for i, x in enumerate((3.3, 5.3, 7.3)):
    K.table((x, 10.15), shape="rect", size=(1.2, 0.7), top="oak", chairs=4, name=f"win{i}")
    K.pendant((x, 10.15), CEIL, drop=1.0, name=f"pend_win{i}")
K.lounge_group((9.3, 11.4), chairs=2, table_top="marble_white", rug="linen:#8a7a66")
K.arch_mirror((10.815, 10.6), rot=90, z=0.4, w=0.9, h=2.2, frame="copper")
K.gallery_wall((4.5, 12.26), (2.8, 12.26), z=1.75, n=3, frame="oak_smoked")
K.fluted_panel((8.15, 12.26), (6.4, 12.26), z0=1.05, z1=2.6, mat="oak_smoked")
K.curtain((0.6, 9.12), (2.9, 9.12), z0=0.05, z1=3.15, colour="linen:#d8ccb4", open_frac=0.8)
K.wall_sconce((0.165, 10.3), rot=-90, z=1.75, name="sc1")
K.wall_sconce((0.165, 11.2), rot=-90, z=1.75, name="sc2")
K.plant((10.35, 9.6), h=1.3, name="plant_a")
K.hanging_plants((1.2, 15.0), (1.2, 19.0), CEIL - 0.32, n=3)
K.wall_shelf((4.12, 20.72), rot=137, z=1.5, w=0.8, name="shelf_chamfer")

# ---- terrace ---------------------------------------------------------------------------------------
for i, (x, y) in enumerate(((2.3, 5.8), (5.5, 5.8), (2.3, 2.6), (5.5, 2.6), (8.3, 4.2))):
    K.table((x, y), shape="round", size=0.8, top="marble_white", chairs=4, name=f"terr{i}")
    K.umbrella((x, y), size=2.9, h=2.6, colour=INK, name=f"umb{i}")
K.olive_tree((0.7, 0.8), h=2.8, name="olive_w")
K.olive_tree((10.2, 7.2), h=2.8, name="olive_e")
K.planter_hedge((1.4, 0.3), (9.4, 0.3), w=0.42, h=0.5, name="hedge_s")
K.planter_hedge((0.3, 1.5), (0.3, 7.4), w=0.42, h=0.5, name="hedge_w")
K.string_lights((0.4, 7.9), (10.5, 7.9), 2.95, n=18)

# ---- light, cameras, tour --------------------------------------------------------------------------
K.lights(mood="day")
K.camera((9.6, 9.75), look_at=(2.5, 11.4), label="Arriving at the street door", look_z=1.25)
K.camera((3.6, 14.2), look_at=(0.8, 18.8), label="Bar and service line")
K.camera((5.1, 12.85), look_at=(8.6, 14.0), label="Prep kitchen", look_z=0.95, fov=80)
K.camera((5.3, 11.9), look_at=(0.6, 10.2), label="Dining room", look_z=1.1)
K.camera((9.6, 0.9), look_at=(3.6, 9.0), label="Terrace and facade", look_z=2.0)
K.stops = [(9.6, 10.0, 130, "Street door"), (5.2, 11.7, 180, "Dining room"), (3.5, 16.5, 100, "Service line"), (5.6, 4.0, 90, "Terrace")]
K.finish()
print("DESIGN_OK")
