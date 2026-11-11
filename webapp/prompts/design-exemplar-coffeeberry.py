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
# As built (Leonberg opening photos, images2/): the back wall over the bar is the brand's walnut CUBBY WALL (K.brand_wall):
#          walnut-backed cubbies 1.45-2.90 m with LED under every shelf, rose-copper/dark pouches, white ceramics, ivy, a lantern,
#          the halo-lit logo on a flush light panel in its own bay, menu TVs in open walnut bays; the stone bar has a shadow
#          reveal under the top and a COPPER kick band with a warm LED glow on the floor; glass cake domes on the bar top;
#          "HOME COLLECTION" lettering over the boutique shelving; flush ROUND recessed downlights in the dark ceiling.
# Light (ΥΛΙΚΑ 10.1 + HM01, as built): flush round recessed downlights on a ~1.1 m grid, LED cove all round 35 cm below the ceiling (§4.02),
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
               downlight_step=1.1, downlight_style="recessed",
               floors={"seating_indoor": "cb_floor", "service_counter": "cb_floor", "entrance": "cb_floor",
                       "seating_outdoor": "paving", "preparation": "cb_prep_floor", "kitchen": "cb_prep_floor",
                       "wc_disabled": "cb_floor", "wc": "cb_floor"})
K.ceiling_cove(drop=0.35, mat=CEIL_DARK)                                         # §4.02 perimeter LED cove
# A03 elevations: plain shopfronts, no cornice; the street front rises to a parapet carrying the 3.60 x 1.10 sign board
K.facade(material=CREAM, plinth="charcoal", plinth_h=0.35, cornice=None, parapet=5.6)
K.logo_sign((5.4, 9.825), rot=180, z=4.55, width=2.10, panel=CREAM, panel_size=(3.60, 1.10), name="fascia_street")   # 210 x 90 illuminated
K.logo_sign((3.33, 23.50), rot=-46.5, z=2.95, width=1.16, name="fascia_mall")                                       # 116 x 50 on the bulkhead

# ---- walls ----
K.finish_walls("seating_indoor", finish=CREAM, skirting=BLACK)
K.finish_walls("service_counter", finish=CREAM, dado=STONE, dado_h=1.5, skirting=BLACK)          # §2.04 Sassiepietre above the back counter
K.finish_walls("preparation", finish=RAL9010, dado="cb_prep_floor", dado_h=1.8, skirting="charcoal")   # Ariman 30x60 to 1.80 m
K.finish_walls("wc_disabled", finish="cb_floor")

# (no floor zoning: §2.03 lays Soulant over the whole sales floor, barista side included)

# ---- service line where the plan draws it ----
K.back_bar((0.125, 23.8), (0.125, 19.6), depth=0.6, shelves=0, shelf_z=(1.45,), body=WALNUT, top=STONE, splash=STONE,
           plinth=BLACK, gola=True, shelf_edge=WALNUT, name="backbar_a")
K.back_bar((0.125, 19.6), (0.125, 14.3), depth=0.6, shelves=0, shelf_z=(1.45,), body=WALNUT, top=STONE, splash=STONE,
           plinth=BLACK, gola=True, name="backbar_b")
# the brand's walnut cubby wall over the whole back bar (stone splash up to 1.45 m): logo bay centred on the A14 logo position,
# open walnut bays where the menu TV and the bean-tube panel hang; bays are (from, to, kind) in metres along a→b
K.brand_wall((0.125, 23.8), (0.125, 14.3), z0=1.45, z1=2.9, depth=0.28, rows=3, cell=0.62, logo_width=0.96,
             bays=((1.55, 2.65, "logo"), (4.85, 6.35, "open"), (7.1, 8.1, "open")), frame=WALNUT, name="cbwall")
K.espresso_station((0.425, 22.45), rot=90, on=0.92, grinders=0)    # legend 9: La Cimbali M100 3-group
K._has_grinders = False                                             # legend 10/11/11a/12 grinders go where the plan draws them
K.counter_run((2.45, 17.25), (2.45, 23.0), depth=0.7, top=STONE, front="panel:" + STONE, top_thick=0.06, plinth=STONE_DARK,
              led_kick=True, kick_trim="copper", reveal=0.12, name="counter")   # §2.04 + §3.03 tiled top 60 mm; as built: reveal + copper kick glow
K.cake_dome((2.2, 20.6), on=0.95, variant="carrot_cake", name="dome_a")        # glass cake domes on the bar top (opening photos)
K.cake_dome((2.2, 21.0), on=0.95, variant="choc_cake", name="dome_b")
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
K.kiosk((4.33, 20.0), rot=-90, panel=WALNUT, trim=BLACK)                           # §4.03 "Order here" unit
K.shelving_wall((4.385, 16.1), (4.385, 17.9), depth=0.30, h=1.95, levels=5, carcass=WALNUT, shelf=WALNUT, shelf_led=True, name="retail")  # §4.05 coffee boutique
K.sign("HOME COLLECTION", (4.385, 17.0), rot=90, z=2.2, size=0.1, mat="black", name="home_collection")      # lettering over the boutique
K.condiment_station((4.215, 15.2), rot=-90, body=WALNUT, top=WALNUT)              # §4.04
K.condiment_station((8.6, 10.2), rot=180, body=WALNUT, top=WALNUT, name="condiments_facade")
K.shelving_wall((1.97, 14.25), (0.62, 14.25), depth=0.30, h=1.95, levels=5, carcass=WALNUT, shelf=WALNUT, shelf_led=True, name="bookshelf")  # §4.07

# ---- every appliance in the legend, then every table / chair / stool / banquette in the plan ----
K.plan_equipment(skip=("carrier bar 2",), wc_finish="cb_floor", wc_dado="cb_floor", vanity="#1b1b1b", kitchen_finish="cb_prep_floor")
K.plan_furniture(seat_mat="linen:#d8cbb4", bench_back=WALNUT, planter_led=True)   # §4.09 bench, 10.1.15 planter LED

# ---- pendants: HM01 draws exactly three, over the seating bench (none over the bar or the loose tables) ----
for i, y in enumerate((11.05, 12.1, 13.0)):
    K.pendant((1.21, y), CEIL, drop=1.3, variant="dome_black", name=f"banq_pend{i}")
K.logo_sign((0.125, 12.1), rot=-90, z=2.39, width=1.16, name="logo_bench")          # HM01: 116 x 50 over the bench, h=2.14-2.64

# ---- terrace: A04 draws four square 4x4 m umbrellas (frame RAL 7039, NYFAN fabric), planters on the edge ----
for i, c in enumerate(((2.14, 6.45), (6.01, 6.45), (2.14, 2.25), (6.01, 2.25))):
    K.umbrella(c, size=3.96, h=2.5, colour=CREAM, shape="square", frame="#6c6960", name=f"umbrella{i}")
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
