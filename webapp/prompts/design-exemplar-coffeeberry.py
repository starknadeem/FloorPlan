# Concept "Coffee Berry Standard": the client's own shop language, reproduced from their built stores and material schedule.
# Palette: warm cream walls #efe4cf, light sonoma-oak joinery "cb_oak", black-marble counter fronts + splash "cb_marble_black",
#          matte black #1b1b1b doors, frames, columns; grey Soulant 60x120 floor, Sassiepietre Grigio behind the bar.
# Zoning: Soulant grey throughout the shop and WC, Ariman grey in prep, Sassiepietre barista lane, paving outside.
# Light: Rockfon white ceiling with recessed downlights, black dome pendants over the bar and every table, warm 3000 K.
# Seating, counters and equipment follow the signed-off plan exactly (plan_furniture / plan_equipment).

K = Kit(SCENE, textures_dir=TEXTURES, seed=SEED, style=STYLE)
CEIL = 3.35
CREAM, BLACK, OAK, MARBLE = "#efe4cf", "#1b1b1b", "cb_oak", "cb_marble_black"

# ---- envelope ----
K.architecture(wall=CREAM, ceiling="rockfon", ground="paving", skirt_mat="charcoal", frame_mat="black_steel", door_mat=BLACK,
               floors={"seating_indoor": "cb_floor", "service_counter": "cb_floor", "entrance": "cb_floor",
                       "seating_outdoor": "paving", "preparation": "cb_prep_floor", "kitchen": "cb_prep_floor",
                       "wc_disabled": "cb_floor", "wc": "cb_floor"})
K.facade(material=CREAM, plinth="charcoal", plinth_h=0.35, cornice=BLACK, band=BLACK)
K.sign("coffee berry", (5.4, 9.825), rot=180, z=3.45, size=0.42, mat="black", name="fascia_street")
K.sign("coffee berry", (3.33, 23.50), rot=-46.5, z=3.1, size=0.3, mat="black", name="fascia_mall")

# ---- walls ----
K.finish_walls("seating_indoor", finish=CREAM, skirting=BLACK)
K.finish_walls("service_counter", finish=CREAM, dado=MARBLE, dado_h=1.5, skirting=BLACK)
K.finish_walls("preparation", finish="plaster_white", dado="tile_white", dado_h=1.8, skirting="charcoal")
K.finish_walls("wc_disabled", finish="cb_floor")

# ---- floor zoning: Sassiepietre barista lane ----
K.floor_zone([[0.125, 14.3], [1.7, 14.3], [1.7, 23.8], [0.125, 23.8]], "cb_bar_tile", name="barista_lane")

# ---- service line where the plan draws it ----
K.back_bar((0.125, 23.8), (0.125, 19.6), depth=0.6, shelves=2, shelf_z=(1.65, 2.05), body=OAK, top=OAK, splash=MARBLE, name="backbar_a")
K.back_bar((0.125, 19.6), (0.125, 14.3), depth=0.6, shelves=0, shelf_z=(1.3,), body=OAK, top=OAK, splash=MARBLE, name="backbar_b")
K.espresso_station((0.425, 22.45), rot=90, on=0.92, grinders=0)    # legend 9: La Cimbali M100 3-group
K._has_grinders = False                                             # legend 10/11/11a/12 grinders go where the plan draws them
K.counter_run((2.45, 17.25), (2.45, 23.0), depth=0.7, top=OAK, front="panel:" + MARBLE, name="counter")
K.display_case((2.05, 16.6), rot=90, w=1.3, d=0.83, body=MARBLE, top=OAK, name="grabngo")              # legend 1
K.display_case((2.1, 19.75), rot=90, w=1.06, d=0.58, on=0.95, h_base=0.05, glass_h=0.42, body=OAK, top=OAK, name="cooling")  # legend 3
K.till((2.1, 17.6), rot=-90, on=0.95, name="till")                                                     # legend 2
K.menu_screen((0.165, 18.2), rot=-90, w=1.45, h=0.82, z=2.05)                                        # legend 22: monitor 65"
# oak panel with the coffee-bean dispenser tubes (brand signature on the back wall)
K.box("bean_panel", (0.03, 1.0, 1.0), (0.155, 16.2, 1.95), 0, K.M(OAK))
for i in range(4):
    K.cyl(f"bean_tube{i}", 0.045, 0.62, (0.24, 15.85 + i * 0.23, 1.6), K.M("display_glass"), 18)
    K.cyl(f"bean_fill{i}", 0.04, 0.5, (0.24, 15.85 + i * 0.23, 1.62), K.M("beans"), 14)
    K.cyl(f"bean_cap{i}", 0.05, 0.06, (0.24, 15.85 + i * 0.23, 2.22), K.M("black"), 18)
for i, y in enumerate((18.3, 19.6, 20.9, 22.1)):
    K.pendant((2.1, y), CEIL, drop=1.15, variant="dome_black", name=f"bar_pend{i}")
# client cups + syrups styled on the back bar
for i in range(5):
    K.place("cup", (0.3, 19.0 + i * 0.1), rot=90, z=0.92, name=f"cup_stack{i}")
for i in range(4):
    K.place("syrup", (0.35, 15.0 + i * 0.1), rot=90, z=0.92, name=f"syrup{i}")
K.kiosk((4.33, 20.0), rot=-90)                                                     # order kiosk faces the queue
K.shelving_wall((4.385, 16.1), (4.385, 17.9), depth=0.35, h=2.2, levels=5, name="retail")  # mall-side display
K.condiment_station((4.215, 15.2), rot=-90)
K.condiment_station((8.6, 10.2), rot=180, name="condiments_facade")
K.shelving_wall((1.97, 14.25), (0.62, 14.25), depth=0.32, h=1.2, levels=3, name="bookshelf")

# ---- every appliance in the legend, then every table / chair / stool / banquette in the plan ----
K.plan_equipment(skip=("carrier bar 2",), wc_finish="cb_floor", wc_dado="cb_floor", vanity="#1b1b1b", kitchen_finish="tile_white")
K.plan_furniture(seat_mat="linen:#d8cbb4")

# ---- lighting over the plan's tables ----
for i, x in enumerate((3.02, 4.54, 6.01, 7.18, 8.7)):
    K.pendant((x, 11.03), CEIL, drop=1.3, variant="dome_black", name=f"dine_pend{i}")
for i, y in enumerate((11.05, 12.1, 13.0)):
    K.pendant((1.21, y), CEIL, drop=1.3, variant="dome_black", name=f"banq_pend{i}")

# ---- terrace: umbrellas over the plan's four clusters, planters on the edge ----
for i, c in enumerate(((2.14, 6.45), (6.01, 6.45), (2.14, 2.25), (6.01, 2.25))):
    K.umbrella(c, size=3.4, h=2.55, colour=CREAM, name=f"umbrella{i}")
K.planter_hedge((0.3, 0.2), (2.0, 0.2), w=0.35, h=0.5, planter="concrete", name="planter_w")
K.planter_hedge((8.4, 0.2), (10.6, 0.2), w=0.35, h=0.5, planter="concrete", name="planter_e")
K.planter_hedge((10.6, 0.6), (10.6, 3.4), w=0.35, h=0.5, planter="concrete", name="planter_r")

# ---- light, cameras, tour ----
K.lights(mood="day")
K.camera((9.75, 11.15), look_at=(1.0, 12.3), label="Arriving at the street door", look_z=1.3)
K.camera((7.45, 12.35), look_at=(0.8, 11.0), label="Dining room and banquette", look_z=1.2)
K.camera((3.4, 22.2), look_at=(1.0, 15.5), label="Bar from the mall entrance", look_z=1.3)
K.camera((3.3, 14.6), look_at=(1.2, 22.0), label="Service line", look_z=1.3)
K.camera((5.25, 1.2), look_at=(5.4, 9.9), label="Terrace and facade", look_z=2.4, fov=75)
K.stops = [(9.75, 11.2, 160, "Street door"), (7.4, 12.3, 190, "Dining room"), (3.4, 22.1, 230, "Mall entrance"),
           (3.3, 14.8, 100, "Service line"), (5.25, 1.3, 90, "Terrace")]
K.finish()
print("DESIGN_OK")
