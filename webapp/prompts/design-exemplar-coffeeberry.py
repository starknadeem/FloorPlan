# Concept "Coffee Berry Standard": the client's own shop language, built to their documents (clientsDocs/3.CB Leo-Documents:
# "Τεχνική Περιγραφή" = technical description, "ΥΛΙΚΑ" = materials schedule) and the electrical/lighting drawing HM01.
# Paint (§5.01): walls Vivechrome 30YY 58/082 warm beige #d7c6ae; main ceiling Vivechrome 96YR 09/033 dark warm grey #5d534d;
#          back-of-house RAL 9010 #f1ece1. Shopfront frames RAL 7021 black-grey (§5.03).
# Tiles (§2.03-2.08): Soulant grey 60x120 on the whole shop + seating + WC floor (long side parallel to the shopfront);
#          Ariman grey 30x60 prep floor and prep walls to 1.80 m; COEM Sassiepietre Grigio 90x90 on the service counter's
#          top and front AND the wall above the back counter; recessed counter kick in Sassiepietre Grigio SCURO.
# Joinery (§4.01-4.10): Egger H1307 Brown Warmia Walnut "cb_walnut" for every bar cabinet, door, shelf, the coffee/capsule
#          boutiques, bookshelf, condiment and order-here units, and the seating bench back (73 cm board, LED behind);
#          black Gola handles, black plinths; warm LED strip under every shelf.
# Light (ΥΛΙΚΑ 10.1 + HM01): black surface GU10 spots on a ~1.1 m grid, LED cove all round 35 cm below the ceiling (§4.02),
#          ONLY 3 pendants — over the seating bench. Terrace: IP67 LED on the planters, spike spots in the planters.
# Signage: the real logo (tree + wordmark) via K.logo_sign — never the plain "coffee berry" text.
# Seating, counters and equipment follow the signed-off plan exactly (plan_furniture / plan_equipment).

K = Kit(SCENE, textures_dir=TEXTURES, seed=SEED, style=STYLE)
CEIL = 3.35
CREAM, BLACK, WALNUT, STONE, STONE_DARK = "#d7c6ae", "#1b1b1b", "cb_walnut", "cb_bar_tile", "cb_bar_tile_dark"   # CREAM = Vivechrome 30YY 58/082
CEIL_DARK, RAL9010 = "#5d534d", "#f1ece1"                                        # Vivechrome 96YR 09/033, RAL 9010

# ---- envelope ----
K.architecture(wall=CREAM, ceiling={"default": CEIL_DARK, "preparation": RAL9010, "kitchen": RAL9010, "storage": RAL9010,
                                    "staff": RAL9010, "wc": RAL9010, "wc_disabled": RAL9010}, ground="paving", skirt_mat="charcoal", frame_mat="ral7021", door_mat=BLACK,
               downlight_step=1.1, downlight_style="surface",
               floors={"seating_indoor": "cb_floor", "service_counter": "cb_floor", "entrance": "cb_floor",
                       "seating_outdoor": "paving", "preparation": "cb_prep_floor", "kitchen": "cb_prep_floor",
                       "wc_disabled": "cb_floor", "wc": "cb_floor"})
K.ceiling_cove(drop=0.35, mat=CEIL_DARK)                                         # §4.02 perimeter LED cove
K.facade(material=CREAM, plinth="charcoal", plinth_h=0.35, cornice=BLACK, band=BLACK)
K.logo_sign((5.4, 9.825), rot=180, z=3.55, width=1.6, panel=CREAM, name="fascia_street")
K.logo_sign((3.33, 23.50), rot=-46.5, z=3.15, width=1.2, panel=CREAM, name="fascia_mall")

# ---- walls ----
K.finish_walls("seating_indoor", finish=CREAM, skirting=BLACK)
K.finish_walls("service_counter", finish=CREAM, dado=STONE, dado_h=1.5, skirting=BLACK)          # §2.04 Sassiepietre above the back counter
K.finish_walls("preparation", finish=RAL9010, dado="cb_prep_floor", dado_h=1.8, skirting="charcoal")   # Ariman 30x60 to 1.80 m
K.finish_walls("wc_disabled", finish="cb_floor")

# (no floor zoning: §2.03 lays Soulant over the whole sales floor, barista side included)

# ---- service line where the plan draws it ----
K.back_bar((0.125, 23.8), (0.125, 19.6), depth=0.6, shelves=2, shelf_z=(1.65, 2.05), body=WALNUT, top=STONE, splash=STONE,
           plinth=BLACK, gola=True, shelf_edge=WALNUT, name="backbar_a")
K.back_bar((0.125, 19.6), (0.125, 14.3), depth=0.6, shelves=0, shelf_z=(1.3,), body=WALNUT, top=STONE, splash=STONE,
           plinth=BLACK, gola=True, name="backbar_b")
K.espresso_station((0.425, 22.45), rot=90, on=0.92, grinders=0)    # legend 9: La Cimbali M100 3-group
K._has_grinders = False                                             # legend 10/11/11a/12 grinders go where the plan draws them
K.counter_run((2.45, 17.25), (2.45, 23.0), depth=0.7, top=STONE, front="panel:" + STONE, top_thick=0.06, plinth=STONE_DARK,
              led_kick=False, name="counter")                                    # §2.04 + §3.03: tiled top 60 mm, recessed dark kick
K.display_case((2.05, 16.6), rot=90, w=1.3, d=0.83, body=STONE, top=STONE, name="grabngo")              # legend 1
K.display_case((2.1, 19.75), rot=90, w=1.06, d=0.58, on=0.95, h_base=0.05, glass_h=0.42, body=BLACK, top=STONE, name="cooling")  # legend 3
K.till((2.1, 17.6), rot=-90, on=0.95, name="till")                                                     # legend 2
K.menu_screen((0.165, 18.2), rot=-90, w=1.45, h=0.82, z=2.05)                                        # legend 22: monitor 65"
# walnut panel with the coffee-bean dispenser tubes (brand signature on the back wall)
K.box("bean_panel", (0.03, 1.0, 1.0), (0.155, 16.2, 1.95), 0, K.M(WALNUT))
for i in range(4):
    K.cyl(f"bean_tube{i}", 0.045, 0.62, (0.24, 15.85 + i * 0.23, 1.6), K.M("display_glass"), 18)
    K.cyl(f"bean_fill{i}", 0.04, 0.5, (0.24, 15.85 + i * 0.23, 1.62), K.M("beans"), 14)
    K.cyl(f"bean_cap{i}", 0.05, 0.06, (0.24, 15.85 + i * 0.23, 2.22), K.M("black"), 18)
# client cups + syrups styled on the back bar
for i in range(5):
    K.place("cup", (0.3, 19.0 + i * 0.1), rot=90, z=0.92, name=f"cup_stack{i}")
for i in range(4):
    K.place("syrup", (0.35, 15.0 + i * 0.1), rot=90, z=0.92, name=f"syrup{i}")
K.logo_sign((0.125, 21.7), rot=-90, z=2.6, width=1.0, name="logo_backbar")         # real logo over the back bar
K.kiosk((4.33, 20.0), rot=-90, panel=WALNUT, trim=BLACK)                           # §4.03 "Order here" unit
K.shelving_wall((4.385, 16.1), (4.385, 17.9), depth=0.30, h=1.95, levels=5, carcass=WALNUT, shelf=WALNUT, shelf_led=True, name="retail")  # §4.05 coffee boutique
K.condiment_station((4.215, 15.2), rot=-90, body=WALNUT, top=WALNUT)              # §4.04
K.condiment_station((8.6, 10.2), rot=180, body=WALNUT, top=WALNUT, name="condiments_facade")
K.shelving_wall((1.97, 14.25), (0.62, 14.25), depth=0.30, h=1.95, levels=5, carcass=WALNUT, shelf=WALNUT, shelf_led=True, name="bookshelf")  # §4.07

# ---- every appliance in the legend, then every table / chair / stool / banquette in the plan ----
K.plan_equipment(skip=("carrier bar 2",), wc_finish="cb_floor", wc_dado="cb_floor", vanity="#1b1b1b", kitchen_finish="cb_prep_floor")
K.plan_furniture(seat_mat="linen:#d8cbb4", bench_back=WALNUT, planter_led=True)   # §4.09 bench, 10.1.15 planter LED

# ---- pendants: HM01 draws exactly three, over the seating bench (none over the bar or the loose tables) ----
for i, y in enumerate((11.05, 12.1, 13.0)):
    K.pendant((1.21, y), CEIL, drop=1.3, variant="dome_black", name=f"banq_pend{i}")

# ---- terrace: umbrellas over the plan's four clusters, planters on the edge ----
for i, c in enumerate(((2.14, 6.45), (6.01, 6.45), (2.14, 2.25), (6.01, 2.25))):
    K.umbrella(c, size=3.4, h=2.55, colour=CREAM, name=f"umbrella{i}")
K.planter_hedge((0.3, 0.2), (2.0, 0.2), w=0.35, h=0.5, planter="concrete", led=True, name="planter_w")
K.planter_hedge((8.4, 0.2), (10.6, 0.2), w=0.35, h=0.5, planter="concrete", led=True, name="planter_e")
K.planter_hedge((10.6, 0.6), (10.6, 3.4), w=0.35, h=0.5, planter="concrete", led=True, name="planter_r")

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
