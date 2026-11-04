# design.py — Coffee Berry Leo-Center (plan A01) · designer build on top of cafe_kit
#
# The runner injects: SCENE (parsed CafeScene dict), TEXTURES (textures dir), Kit (cafe_kit.Kit).
# Plan frame: x east, y north (up the page), metres. Rooms on this plan:
#   terrace   x 0.0–10.9, y 0.0–9.0   (street side, open to sky)
#   dining    x 0.0–11.0, y 10.15–13.3 (glazed facade at y=10.15, street door at x 9.4–10.3)
#   bar room  x 0.0–4.55, y 13.3–24.0 (west wall x=0; mall entrance on the chamfer at the top)
#   prep      x 4.65–8.9, y 13.3–15.6  (door at x 4.65–5.45 on y=13.32)
#   wc        x 9.0–11.0, y 13.3–15.6  (door at x 9.45–10.35 on y=13.32)
# Concept: warm walnut joinery, honed terrazzo tops with LED kicks, cream plaster, brushed brass,
# black steel shelving, oat bouclé seating; dark ceiling with downlights; branded terrace.

K = Kit(SCENE, textures_dir=TEXTURES)
CEIL = 3.35

# ---- shell: walls/doors/glazing from the plan, floors per zone, dark ceilings with downlights
K.architecture(
    wall="plaster",
    floors={"seating_indoor": "oak", "service_counter": "stone", "seating_outdoor": "stone",
            "preparation": "concrete", "wc_disabled": "concrete"},
)

# ---- DESIGN SCHEME ------------------------------------------------------------------------
# Concept: "warm workshop" — dark ceiling with a walnut slat raft over the bar, walnut cladding and
# a sage colour block in the dining room, lime-plaster quote wall at the end of the order corridor,
# checker tile at the bar, oak boards in the dining room, layered 2700K light (pendants, track,
# sconces, LED coves), styled shelves with coffee bags, books and plants.
K.floor_zone([[0, 13.32], [4.55, 13.32], [4.55, 21.5], [2.05, 23.95], [0, 23.95]], "tile_check")   # bar floor
K.ceiling_raft(0.8, 14.5, 3.3, 21.5, CEIL, style="slats", drop=0.4, led=True)                      # over the bar
K.track_light((3.6, 14.8), (3.6, 21.2), CEIL - 0.45, heads=6, aim=(1.6, 18.0))                     # grazing the counter
K.quote_wall((4.48, 21.43), (1.98, 23.88), ["Crafted with soul", "roasted with care", "served with heart"],
             z_top=2.3, size=0.2, side=-1, name="quote")   # chamfer wall face (t=0.2)                                           # chamfer wall by the mall door
K.wall_panel((0.125, 13.245), (0.125, 10.25), 0.0, 2.3, "walnut_slat", side=1, name="dining_cladding")   # behind the dining 2-tops
K.accent_wall((10.87, 10.25), (10.87, 13.245), "sage", side=1, name="sage_block")   # east wall face (t=0.2)                    # east feature wall
K.wall_panel((9.3, 13.245), (5.6, 13.245), 2.2, 2.9, "walnut", side=1, name="banquette_back")   # above the banquette panel        # above the banquette

# ---- bar room: back bar on the west wall, service counter in front of it ------------------
# back bar body grows east (left of travel when walking south along x=0)
K.back_bar((0.125, 21.0), (0.125, 14.3), depth=0.6, shelves=3, cups=True, led=True)   # west wall face (t=0.25)
K.menu_screen((0.125, 18.9), rot=-90, w=1.45, h=0.82, z=2.75)          # 65" menu over the back bar
# service counter: body grows west (barista side), customers stand east of x≈2.0
K.counter_run((1.95, 16.9), (1.95, 21.0), depth=0.7, h=0.95, top="terrazzo", front="walnut_slat")
K.espresso_station((1.6, 19.9), rot=90, on=0.95, machine_w=1.0, grinders=2)   # faces the customer side
K.till((1.72, 17.4), rot=90, on=0.95)
# pastry + grab-and-go displays continue the counter line toward the dining room
K.display_case((1.6, 16.1), rot=90, w=1.3, d=0.75, name="pastry")
K.display_case((1.6, 14.9), rot=90, w=1.1, d=0.75, name="grabgo")
# order corridor east wall: two self-order kiosks, then the retail wall (wall at x=4.55)
K.kiosk((4.475, 14.3), rot=90, name="kiosk1")
K.kiosk((4.475, 15.1), rot=90, name="kiosk2")
K.shelving_wall((4.475, 15.9), (4.475, 20.4), depth=0.35, h=2.4, levels=5, products=True)   # east wall face (t=0.15)
K.sign("coffee berry", (4.475, 18.15), rot=90, z=2.75, size=0.26, mat="bronze", name="retail_sign")
# pick-up end: condiment station, high table with stools, neon over it
K.condiment_station((3.6, 22.3), rot=0)
K.high_table((2.6, 22.6), rot=0, w=1.4, d=0.5, stools=3)
K.neon_sign("coffee first", (4.475, 21.2), rot=90, z=2.3, size=0.26)
K.letter_board((4.475, 15.4), rot=90, z=1.95, w=0.8, h=0.55)
K.wall_shelf((4.475, 21.0), rot=90, z=1.45, w=1.0, name="shelf_bar")
K.hanging_plants((1.0, 15.0), (1.0, 21.0), CEIL, n=4)
K.wall_sconce((0.125, 22.6), rot=-90, z=1.8, name="sconce_bar")

# ---- dining room: banquette on the north partition, 2-tops in front, 4-tops along the glazing
K.banquette((9.3, 13.245), (5.6, 13.245), depth=0.6, seat_mat="boucle")   # north partition face (t=0.15)    # body grows south into the room
for i, x in enumerate((6.1, 7.4, 8.7)):
    K.table((x, 12.45), shape="round", size=0.7, chairs=0, name=f"two_top{i}")
    K.chair((x, 11.75), rot=180, name=f"two_top{i}_chair")              # facing the banquette
    K.pendant((x, 12.45), CEIL, drop=1.05, style="brass", name=f"pend_two{i}")
for i, x in enumerate((1.4, 3.3, 5.2, 7.1, 8.9)):
    K.table((x, 11.35), shape="rect", size=(1.2, 0.7), chairs=4, name=f"window{i}")
    K.pendant((x, 11.35), CEIL, drop=1.0, style="opal", name=f"pend_win{i}")
K.art((10.87, 11.2), rot=90, z=1.65, w=0.8, h=0.55, name="art1")
K.mirror((10.87, 12.4), rot=90, z=1.5, w=1.0, h=1.5, name="mirror_dining")
K.wall_sconce((10.87, 10.6), rot=90, z=1.8, name="sconce_d1")
K.wall_sconce((10.87, 13.0), rot=90, z=1.8, name="sconce_d2")
K.wall_shelf((10.2, 13.245), rot=180, z=1.5, w=1.0, name="shelf_dining")
K.rug((7.4, 12.2), w=4.0, d=1.4, name="rug_dining")
K.plant((0.45, 12.8), h=1.3, name="plant_dining")
K.sign("coffee berry", (5.5, 10.05), rot=0, z=2.85, size=0.4, mat="walnut", name="fascia")   # outer facade face  # over the glazing, read from the street

# ---- terrace: branded umbrellas, 4-tops, olive trees, planters along the street edge ----------
for i, (x, y) in enumerate(((2.6, 4.6), (8.3, 4.6))):
    K.umbrella((x, y), size=3.4, h=2.6, name=f"umb{i}")
for i, (x, y) in enumerate(((1.6, 3.4), (3.7, 5.8), (7.3, 3.4), (9.3, 5.8), (5.5, 7.6))):
    K.table((x, y), shape="round", size=0.8, chairs=4, top="walnut", seat_mat="boucle_sage", name=f"terr{i}")
K.olive_tree((0.7, 0.8), h=2.7, name="olive_w")
K.olive_tree((10.2, 0.8), h=2.7, name="olive_e")
K.planter_hedge((1.6, 0.3), (9.4, 0.3), w=0.4, h=0.45)                     # street edge
K.planter_hedge((0.3, 1.2), (0.3, 8.4), w=0.4, h=0.45, name="hedge_w")
K.planter_hedge((10.6, 1.2), (10.6, 8.4), w=0.4, h=0.45, name="hedge_e")
K.string_lights((0.8, 9.5), (10.1, 9.5), 2.9, n=16)                         # along the facade
K.string_lights((0.8, 1.0), (10.1, 1.0), 2.9, n=16, name="festoon2")

# ---- back of house: prep worktop, stainless run ------------------------------------------
K.counter_run((8.875, 15.5), (8.875, 13.45), depth=0.65, h=0.9, top="steel", front="steel", led_kick=False, name="prep_run")

# ---- lighting + cameras ---------------------------------------------------------------------
K.lights(sun_elev=34, sun_az=150, sun_power=2.6)
K.camera((9.3, 11.0), look_at=(2.0, 16.0), label="Arriving from the street door", look_z=1.5)
K.camera((3.7, 15.2), look_at=(0.8, 19.6), label="Order corridor and bar")
K.camera((2.9, 12.0), look_at=(8.6, 12.9), label="Dining room and banquette")
K.camera((5.5, 6.2), look_at=(5.5, 11.5), label="Terrace toward the facade", look_z=2.0)
K.stops = [(9.6, 10.9, 120, "Street door"), (3.5, 15.3, 125, "Order corridor"), (3.3, 19.0, 160, "Bar"),
           (2.9, 12.0, 20, "Dining room"), (5.5, 6.5, 90, "Terrace")]
K.finish()
print(f"DESIGN_OK objects={len(bpy.data.objects)} cameras={len(K.cameras)}")
