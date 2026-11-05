"""
author_models.py — builds the detailed commercial café library and registers it in assets/manifest.json.

    blender --background --python blender/author_models.py -- [--only substring]

Every model: base at z=0, centred in XY, FRONT faces -Y, true size in metres (commercial proportions).
"""
import json
import math
import os
import sys

import bpy  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardsurface as hs  # noqa: E402
from hardsurface import Model, pbr, plain  # noqa: E402

MODELS = os.path.join(HERE, "assets", "models")
MANIFEST = os.path.join(HERE, "assets", "manifest.json")
ALL = ["industrial", "scandinavian", "japandi", "bistro", "mediterranean", "deco", "midcentury", "biophilic", "brutalist", "retro", "modern", "cozy"]


def mats():
    pbr("steel", "brushed_steel", tint="#c9cbce", metal=1.0, tiles_per_m=4.0, normal=0.08, rough_only=True)
    plain("steel_dark", "#55585c", 0.35, 1.0)
    plain("chrome", "#e6e7e9", 0.06, 1.0)
    plain("black", "#121213", 0.45)
    plain("black_gloss", "#0b0b0c", 0.12, coat=0.5)
    plain("black_metal", "#17181a", 0.38, 0.85)
    plain("rubber", "#0d0d0d", 0.85)
    plain("plastic_grey", "#3a3c3f", 0.55)
    plain("plastic_white", "#eceae5", 0.42)
    plain("gasket", "#1c1c1d", 0.8)
    plain("glass", "#e9f3f2", 0.03, glass=True)
    plain("glass_dark", "#39424a", 0.05, glass=True)
    plain("glass_amber", "#b36a25", 0.05, glass=True)
    plain("interior_white", "#e8e8e6", 0.5)
    plain("led", "#000000", emit="#fff3df", emit_power=3.2)
    plain("led_red", "#000000", emit="#ff4a2e", emit_power=5.0)
    plain("led_green", "#000000", emit="#57e08a", emit_power=5.0)
    plain("screen", "#05080b", 0.15, emit="#3f6d8f", emit_power=1.3)
    plain("screen_warm", "#090705", 0.15, emit="#c98f4f", emit_power=1.1)
    plain("iron", "#16161a", 0.7, 0.4)
    plain("brass", "#c49a56", 0.26, 1.0)
    plain("copper", "#b76e45", 0.25, 1.0)
    plain("walnut_h", "#4a2a18", 0.38, coat=0.3)
    plain("beans", "#3a2212", 0.55)
    plain("ceramic", "#f3f1ea", 0.22, coat=0.5)
    pbr("oak_f", "oak_light", tint="#b9915f", normal=0.4)
    pbr("oak_dark_f", "oak_light", tint="#6e4c33", normal=0.4)
    pbr("walnut_f", "veneer_a", tint="#5a3a26", normal=0.4)
    pbr("black_f", "veneer_c", tint="#1e1b19", normal=0.4)
    pbr("leather_b", "leather_brown", normal=0.7)
    pbr("leather_w", "leather_white", normal=0.7)
    pbr("velvet_g", "velvet", tint="#46624f", normal=0.7, rough_only=True, sheen=1.0)
    pbr("velvet_t", "velvet", tint="#a2553a", normal=0.7, rough_only=True, sheen=1.0)
    pbr("velvet_i", "velvet", tint="#2b3a55", normal=0.7, rough_only=True, sheen=1.0)
    pbr("boucle_c", "boucle_teddy", tint="#e9e2d3", normal=1.0)
    pbr("linen_o", "linen", tint="#d4c7ad", normal=0.8)
    plain("cane", "#c8a877", 0.7)
    plain("rattan", "#b58f5d", 0.75)
    plain("opal", "#fff6e8", 0.35, emit="#ffdfb5", emit_power=4.5)
    plain("bulb", "#ffffff", 0.3, emit="#ffd9a6", emit_power=25.0)


# ------------------------------------------------------------------ small reusable parts
def foot(b, x, y, h=0.1, r=0.018):
    b.cyl(r * 1.25, h * 0.25, (x, y, 0), "rubber", seg=16)
    b.cyl(r, h * 0.8, (x, y, h * 0.2), "steel_dark", seg=16)


def knob(b, at, r=0.02, depth=0.024, mat="black_metal"):
    """Front-facing control knob (axis -Y) with a pointer line."""
    x, y, z = at
    b.lathe([(0, 0), (r * 0.92, 0), (r, depth * 0.1), (r * 0.94, depth * 0.85), (r * 0.8, depth), (0, depth)], (x, y, z), mat, seg=24, rot=(90, 0, 0))
    b.box((r * 0.14, 0.002, r * 0.9), (x, y - depth - 0.001, z + r * 0.42), "chrome", bevel=0)


def bar_handle_v(b, x, y, z0, z1, off=0.045, r=0.011, mat="chrome"):
    b.tube([(x, y, z0), (x, y - off, z0 + 0.012), (x, y - off, z1 - 0.012), (x, y, z1)], r, mat, seg=12, samples=5)


def bar_handle_h(b, x0, x1, y, z, off=0.045, r=0.011, mat="chrome"):
    b.tube([(x0, y, z), (x0 + 0.012, y - off, z), (x1 - 0.012, y - off, z), (x1, y, z)], r, mat, seg=12, samples=5)


def vent(b, w, x, y, z, n=10, h=0.012, gap=0.02):
    for i in range(n):
        b.box((w, 0.006, h), (x, y, z + i * gap), "black_metal", bevel=0)


def bottle(b, x, y, z, kind=0):
    if kind == 0:   # glass bottle
        b.lathe([(0, 0), (0.03, 0.0), (0.032, 0.012), (0.032, 0.13), (0.015, 0.17), (0.013, 0.215), (0.014, 0.225), (0, 0.225)], (x, y, z), "glass_amber", seg=10)
    elif kind == 1:  # can
        b.lathe([(0, 0), (0.026, 0.0), (0.03, 0.012), (0.03, 0.105), (0.026, 0.118), (0, 0.118)], (x, y, z), "can_a", seg=12)
    else:            # juice
        b.lathe([(0, 0), (0.031, 0.0), (0.033, 0.01), (0.033, 0.12), (0.018, 0.16), (0.018, 0.18), (0, 0.18)], (x, y, z), "juice", seg=10)
        b.cyl(0.02, 0.015, (x, y, z + 0.178), "plastic_white", seg=10)


plain_ready = False


# ------------------------------------------------------------------ refrigeration
def fridge_display(name="fridge_display", doors=1):
    plain("can_a", "#a53a2c", 0.3, 0.6)
    plain("juice", "#d98a26", 0.25, coat=0.4)
    W, D, H = (0.62 * doors + 0.02, 0.66, 1.98)
    b = Model(name)
    base = 0.11
    # carcass: sides, top, back, floor (a real hollow cabinet you can see into)
    for sx in (-1, 1):
        b.box((0.035, D, H - base), (sx * (W / 2 - 0.0175), 0, base + (H - base) / 2), "black_metal", bevel=0.004)
    b.box((W, D, 0.03), (0, 0, H - 0.015), "black_metal", bevel=0.004)
    b.box((W - 0.07, 0.02, H - base - 0.2), (0, D / 2 - 0.02, base + (H - base - 0.2) / 2 + 0.02), "interior_white", bevel=0)
    b.box((W - 0.07, D - 0.05, 0.02), (0, 0.01, base + 0.02), "interior_white", bevel=0)
    # lit header with brand panel
    b.box((W - 0.01, 0.05, 0.17), (0, -D / 2 + 0.03, H - 0.115), "black_metal", bevel=0.006)
    b.box((W - 0.09, 0.006, 0.12), (0, -D / 2 + 0.003, H - 0.115), "led", bevel=0)
    # plinth with vent louvres + feet
    b.box((W, D - 0.04, 0.09), (0, 0.02, base - 0.03), "black_metal", bevel=0.003)
    for i in range(int((W - 0.1) / 0.022)):
        b.box((0.012, 0.006, 0.06), (-W / 2 + 0.06 + i * 0.022, -D / 2 + 0.018, base - 0.03), "black", bevel=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), h=0.04)
    # interior shelves with wire rods and stock
    shelf_zs = [base + 0.06 + i * 0.36 for i in range(5)]
    dw = (W - 0.07) / doors
    for s, z in enumerate(shelf_zs):
        for i in range(int((W - 0.1) / 0.03)):
            b.box((0.004, D - 0.12, 0.004), (-W / 2 + 0.05 + i * 0.03, 0.01, z), "chrome", bevel=0)
        b.box((W - 0.07, 0.008, 0.03), (0, -D / 2 + 0.08, z + 0.01), "steel_dark", bevel=0)
        if s < 4:
            for row in range(2):
                n = int((W - 0.12) / 0.078)
                for i in range(n):
                    kind = (s + (i // 3)) % 3
                    bottle(b, -W / 2 + 0.075 + i * 0.078, -D / 2 + 0.15 + row * 0.13, z + 0.004, kind)
    # LED columns inside
    for sx in (-1, 1):
        b.box((0.008, 0.008, H - base - 0.26), (sx * (W / 2 - 0.042), -D / 2 + 0.08, base + (H - base - 0.26) / 2 + 0.03), "led", bevel=0)
    # glass door(s): full frame, gasket, pane, vertical bar handle
    for k in range(doors):
        cx = -W / 2 + 0.035 + dw * (k + 0.5)
        dz0, dz1 = base + 0.015, H - 0.2
        zc = (dz0 + dz1) / 2
        hh = dz1 - dz0
        for sx in (-1, 1):
            b.box((0.04, 0.045, hh), (cx + sx * (dw / 2 - 0.022), -D / 2 + 0.018, zc), "black_metal", bevel=0.004)
        for z in (dz0 + 0.02, dz1 - 0.02):
            b.box((dw - 0.005, 0.045, 0.04), (cx, -D / 2 + 0.018, z), "black_metal", bevel=0.004)
        b.box((dw - 0.07, 0.008, hh - 0.07), (cx, -D / 2 + 0.018, zc), "glass", bevel=0)
        b.box((dw - 0.03, 0.006, 0.006), (cx, -D / 2 + 0.043, dz1 - 0.042), "gasket", bevel=0)
        hx = cx + (dw / 2 - 0.022) * (1 if k % 2 == 0 else -1)
        bar_handle_v(b, hx, -D / 2 - 0.004, zc - 0.32, zc + 0.32, off=0.04, r=0.009)
    return b


def fridge_upright(name="fridge_upright", doors=2):
    W, D, H = (0.7 * doors, 0.82, 2.02)
    b = Model(name)
    base = 0.14
    b.box((W, D, H - base), (0, 0, base + (H - base) / 2), "steel", bevel=0.006)
    b.box((W - 0.01, D - 0.02, 0.1), (0, 0.01, base - 0.05), "steel_dark", bevel=0.002)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.07), sy * (D / 2 - 0.08), h=0.1)
    dw = W / doors
    top = H - 0.2
    for k in range(doors):
        cx = -W / 2 + dw * (k + 0.5)
        zc = (base + 0.03 + top) / 2
        hh = top - base - 0.03
        b.box((dw - 0.018, 0.05, hh), (cx, -D / 2 - 0.022, zc), "steel", bevel=0.007, seg=3)
        b.box((dw - 0.006, 0.012, hh + 0.012), (cx, -D / 2 + 0.003, zc), "gasket", bevel=0)
        side = 1 if k % 2 == 0 else -1
        bar_handle_v(b, cx + side * (dw / 2 - 0.06), -D / 2 - 0.047, zc - 0.34, zc + 0.34, off=0.05, r=0.012)
        for z in (base + 0.14, top - 0.1):   # hinges
            b.box((0.05, 0.028, 0.065), (cx - side * (dw / 2 - 0.018), -D / 2 - 0.02, z), "steel_dark", bevel=0.004)
    # top control fascia with digital thermostat and louvres
    b.box((W - 0.012, 0.012, 0.17), (0, -D / 2 - 0.001, H - 0.095), "steel_dark", bevel=0.002)
    b.box((0.11, 0.006, 0.055), (-W / 2 + 0.14, -D / 2 - 0.008, H - 0.095), "black_gloss", bevel=0)
    b.box((0.062, 0.002, 0.024), (-W / 2 + 0.14, -D / 2 - 0.012, H - 0.095), "led_red", bevel=0)
    for i in range(3):
        b.cyl(0.006, 0.006, (-W / 2 + 0.24 + i * 0.024, -D / 2 - 0.006, H - 0.095), "plastic_grey", rot=(90, 0, 0), seg=12)
    for i in range(6):
        b.box((W - 0.5, 0.006, 0.01), (0.14, -D / 2 - 0.008, H - 0.155 + i * 0.022), "black", bevel=0)
    return b


def fridge_undercounter(name="fridge_undercounter", doors=2, W=None):
    W = W or 0.62 * doors
    D, H = 0.68, 0.86
    b = Model(name)
    base = 0.1
    b.box((W, D, H - base - 0.012), (0, 0, base + (H - base - 0.012) / 2), "steel", bevel=0.004)
    b.box((W, D + 0.01, 0.012), (0, -0.005, H - 0.006), "steel", bevel=0.002)
    b.box((W - 0.02, D - 0.04, 0.08), (0, 0.02, base - 0.03), "steel_dark", bevel=0.001)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), h=0.075, r=0.016)
    panel = 0.09
    dw = (W - 0.015) / doors
    for k in range(doors):
        cx = -W / 2 + 0.0075 + dw * (k + 0.5)
        hh = H - base - panel - 0.03
        zc = base + 0.012 + hh / 2
        b.box((dw - 0.012, 0.035, hh), (cx, -D / 2 - 0.016, zc), "steel", bevel=0.006, seg=3)
        b.box((dw - 0.004, 0.01, hh + 0.01), (cx, -D / 2 + 0.002, zc), "gasket", bevel=0)
        bar_handle_h(b, cx - dw / 2 + 0.07, cx + dw / 2 - 0.07, -D / 2 - 0.033, zc + hh / 2 - 0.05, off=0.035, r=0.009)
    b.box((W - 0.03, 0.006, panel - 0.02), (0, -D / 2 - 0.003, H - 0.012 - panel / 2), "steel_dark", bevel=0.001)
    b.box((0.08, 0.004, 0.032), (W / 2 - 0.1, -D / 2 - 0.007, H - 0.012 - panel / 2), "black_gloss", bevel=0)
    b.box((0.05, 0.002, 0.018), (W / 2 - 0.1, -D / 2 - 0.0095, H - 0.012 - panel / 2), "led_green", bevel=0)
    for i in range(int((W - 0.4) / 0.02)):
        b.box((0.009, 0.004, 0.038), (-W / 2 + 0.05 + i * 0.02, -D / 2 - 0.007, H - 0.012 - panel / 2), "black", bevel=0)
    return b


def freezer_chest(name="freezer_chest"):
    W, D, H = 1.0, 0.68, 0.88
    b = Model(name)
    b.box((W, D, H - 0.09), (0, 0, 0.09 + (H - 0.09) / 2), "plastic_white", bevel=0.018, seg=3)
    b.box((W + 0.012, D + 0.012, 0.035), (0, 0, H - 0.015), "steel_dark", bevel=0.006)
    # curved sliding glass lids
    for k, (x0, w) in enumerate(((-0.24, 0.5), (0.24, 0.5))):
        b.box((w, D - 0.055, 0.008), (x0, 0, H + 0.008 + k * 0.012), "glass", bevel=0)
        b.box((0.035, D - 0.05, 0.016), (x0 + (w / 2 - 0.018) * (1 if k == 0 else -1), 0, H + 0.012 + k * 0.012), "black_metal", bevel=0.002)
    for i in range(14):
        b.box((0.035, 0.005, 0.07), (-W / 2 + 0.1 + i * 0.058, -D / 2 - 0.002, 0.18), "plastic_grey", bevel=0)
    b.box((0.09, 0.004, 0.036), (W / 2 - 0.12, -D / 2 - 0.002, 0.3), "black_gloss", bevel=0)
    b.box((0.05, 0.002, 0.018), (W / 2 - 0.12, -D / 2 - 0.0045, 0.3), "led_red", bevel=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl(0.03, 0.05, (sx * (W / 2 - 0.08), sy * (D / 2 - 0.08), 0.0), "rubber", seg=16)
            b.cyl(0.018, 0.05, (sx * (W / 2 - 0.08), sy * (D / 2 - 0.08), 0.045), "steel_dark", seg=12)
    return b


# ------------------------------------------------------------------ cooking
def range_stove(name="stove_range"):
    W, D, H = 0.9, 0.76, 0.92
    b = Model(name)
    leg = 0.15
    b.box((W, D, H - leg - 0.03), (0, 0, leg + (H - leg - 0.03) / 2), "steel", bevel=0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.06), sy * (D / 2 - 0.07), h=leg, r=0.024)
    # hob tray with raised rim, burners and cast-iron grates
    b.box((W, D, 0.03), (0, 0, H - 0.015), "steel", bevel=0.005)
    b.box((W - 0.05, D - 0.14, 0.006), (0, 0.03, H + 0.001), "black_metal", bevel=0)
    for ix, x in enumerate((-0.215, 0.215)):
        for iy, y in enumerate((-0.135, 0.195)):
            r = 0.05 if (ix + iy) % 2 == 0 else 0.038
            b.lathe([(0, 0.01), (r * 1.55, 0.002), (r * 1.3, 0.016), (r, 0.022), (r * 0.98, 0.034), (0, 0.04)], (x, y, H), "iron", seg=24)
            for k in range(10):   # gas ports
                a = 2 * math.pi * k / 10
                b.cyl(0.0022, 0.002, (x + math.cos(a) * r * 1.02, y + math.sin(a) * r * 1.02, H + 0.024), "black", rot=(90, 0, math.degrees(a) + 90), seg=6)
            b.box((0.36, 0.016, 0.016), (x, y, H + 0.052), "iron", bevel=0.003)
            b.box((0.016, 0.3, 0.016), (x, y, H + 0.052), "iron", bevel=0.003)
            for s in (-1, 1):
                b.box((0.36, 0.016, 0.03), (x, y + s * 0.15, H + 0.03), "iron", bevel=0.003)
                b.box((0.016, 0.3, 0.03), (x + s * 0.18, y, H + 0.03), "iron", bevel=0.003)
    # sloped knob rail
    b.box((W - 0.006, 0.055, 0.1), (0, -D / 2 - 0.018, H - 0.075), "steel", bevel=0.006)
    for i in range(4):
        knob(b, (-0.3 + i * 0.2, -D / 2 - 0.046, H - 0.075), r=0.024, depth=0.03)
    # oven door: inset dark window, tube handle, hinge base
    door_h = 0.48
    z = leg + 0.05 + door_h / 2
    b.box((W - 0.05, 0.04, door_h), (0, -D / 2 - 0.016, z), "steel", bevel=0.007, seg=3)
    b.box((W - 0.26, 0.006, door_h - 0.22), (0, -D / 2 - 0.037, z - 0.03), "glass_dark", bevel=0.002)
    bar_handle_h(b, -W / 2 + 0.09, W / 2 - 0.09, -D / 2 - 0.036, z + door_h / 2 - 0.055, off=0.05, r=0.012)
    b.box((W - 0.05, 0.014, 0.05), (0, -D / 2 - 0.004, leg + 0.03), "steel_dark", bevel=0.002)
    # upstand with overshelf
    b.box((W, 0.03, 0.14), (0, D / 2 - 0.015, H + 0.07), "steel", bevel=0.004)
    return b


def oven_combi(name="oven_combi"):
    W, D, H = 0.86, 0.82, 1.62
    b = Model(name)
    stand = 0.72
    # stand with tray runners
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.042, 0.042, stand - 0.04), (sx * (W / 2 - 0.04), sy * (D / 2 - 0.06), (stand - 0.04) / 2 + 0.04), "steel", bevel=0.004)
            b.cyl(0.03, 0.04, (sx * (W / 2 - 0.04), sy * (D / 2 - 0.06), 0), "rubber", seg=16)
    for z in (0.2, 0.42):
        b.box((W - 0.05, D - 0.1, 0.025), (0, 0, z), "steel", bevel=0.003)
    for i in range(5):
        for sx in (-1, 1):
            b.box((0.012, D - 0.14, 0.008), (sx * (W / 2 - 0.08), 0, stand - 0.06 - i * 0.05), "chrome", bevel=0)
    b.box((W, D - 0.04, 0.03), (0, 0.02, stand - 0.015), "steel", bevel=0.004)
    # oven body
    zb = stand
    hb = H - stand
    b.box((W, D - 0.06, hb), (0, 0.03, zb + hb / 2), "steel", bevel=0.01, seg=3)
    # control tower on the right, door on the left
    tw = 0.2
    dw = W - tw - 0.02
    dx = -W / 2 + 0.01 + dw / 2
    zc = zb + hb / 2 + 0.01
    dh = hb - 0.1
    b.box((dw, 0.05, dh), (dx, -D / 2 + 0.02, zc), "black_metal", bevel=0.012, seg=3)
    b.box((dw - 0.1, 0.008, dh - 0.12), (dx, -D / 2 - 0.006, zc), "glass_dark", bevel=0.003)
    for i in range(5):   # racks visible through the dark glass
        b.box((dw - 0.2, 0.004, 0.006), (dx, -D / 2 + 0.003, zb + 0.16 + i * 0.13), "chrome", bevel=0)
    bar_handle_v(b, dx + dw / 2 - 0.035, -D / 2 - 0.004, zc - 0.28, zc + 0.28, off=0.055, r=0.014)
    tx = W / 2 - tw / 2 - 0.006
    b.box((tw - 0.02, 0.012, dh), (tx, -D / 2 + 0.002, zc), "black_gloss", bevel=0.004)
    b.box((tw - 0.06, 0.004, 0.2), (tx, -D / 2 - 0.006, zc + 0.16), "screen", bevel=0.001)
    b.lathe([(0, 0), (0.042, 0), (0.046, 0.008), (0.043, 0.026), (0.034, 0.033), (0, 0.033)], (tx, -D / 2 - 0.004, zc - 0.1), "chrome", seg=32, rot=(90, 0, 0))
    b.lathe([(0, 0), (0.05, 0), (0.052, 0.003), (0, 0.003)], (tx, -D / 2 - 0.004, zc - 0.1), "steel_dark", seg=32, rot=(90, 0, 0))
    for i in range(3):
        b.cyl(0.012, 0.005, (tx - 0.04 + i * 0.04, -D / 2 - 0.004, zc - 0.24), "plastic_grey", rot=(90, 0, 0), seg=16)
    # flue and top vent
    b.cyl(0.05, 0.08, (W / 2 - 0.16, D / 2 - 0.2, H), "steel", seg=24)
    b.lathe([(0.05, 0), (0.06, 0.02), (0.06, 0.028), (0, 0.04)], (W / 2 - 0.16, D / 2 - 0.2, H + 0.08), "steel_dark", seg=24)
    vent(b, 0.3, -0.15, D / 2 - 0.3, H + 0.002, n=1, h=0.004)
    return b


def oven_speed(name="oven_speed"):
    """Countertop high-speed oven (Merrychef class)."""
    W, D, H = 0.48, 0.66, 0.58
    b = Model(name)
    b.box((W, D, H - 0.04), (0, 0, 0.04 + (H - 0.04) / 2), "steel", bevel=0.016, seg=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl(0.018, 0.04, (sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), 0), "rubber", seg=14)
    # door: drops down, large handle
    dh = 0.27
    zd = 0.09 + dh / 2
    b.box((W - 0.03, 0.03, dh), (0, -D / 2 - 0.01, zd), "black_metal", bevel=0.01, seg=3)
    b.box((W - 0.11, 0.004, dh - 0.11), (0, -D / 2 - 0.026, zd - 0.02), "glass_dark", bevel=0.002)
    bar_handle_h(b, -W / 2 + 0.06, W / 2 - 0.06, -D / 2 - 0.024, zd + dh / 2 - 0.035, off=0.045, r=0.012)
    # easy-touch panel + vents
    zp = 0.09 + dh + 0.09
    b.box((W - 0.03, 0.012, 0.13), (0, -D / 2 - 0.002, zp), "black_gloss", bevel=0.005)
    b.box((W - 0.2, 0.003, 0.085), (0, -D / 2 - 0.009, zp), "screen", bevel=0)
    for i in range(3):
        b.cyl(0.011, 0.004, (W / 2 - 0.07, -D / 2 - 0.008, zp - 0.04 + i * 0.04), "chrome", rot=(90, 0, 0), seg=14)
    for i in range(16):
        b.box((0.012, 0.28, 0.003), (-W / 2 + 0.06 + i * 0.024, 0.05, H + 0.001), "black_metal", bevel=0)
    b.box((W - 0.05, 0.03, 0.022), (0, -D / 2 + 0.012, 0.055), "steel_dark", bevel=0.003)
    return b


def microwave(name="microwave"):
    W, D, H = 0.52, 0.42, 0.33
    b = Model(name)
    b.box((W, D, H - 0.02), (0, 0, 0.02 + (H - 0.02) / 2), "steel", bevel=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl(0.012, 0.02, (sx * (W / 2 - 0.04), sy * (D / 2 - 0.04), 0), "rubber", seg=12)
    dw = W - 0.14
    b.box((dw, 0.022, H - 0.06), (-W / 2 + dw / 2 + 0.012, -D / 2 - 0.008, H / 2 + 0.01), "black_metal", bevel=0.006)
    b.box((dw - 0.08, 0.004, H - 0.14), (-W / 2 + dw / 2 + 0.012, -D / 2 - 0.02, H / 2 + 0.01), "glass_dark", bevel=0.001)
    bar_handle_v(b, -W / 2 + dw - 0.014, -D / 2 - 0.018, 0.09, H - 0.07, off=0.03, r=0.008)
    px = W / 2 - 0.058
    b.box((0.09, 0.008, H - 0.06), (px, -D / 2 - 0.002, H / 2 + 0.01), "black_gloss", bevel=0.003)
    b.box((0.066, 0.002, 0.026), (px, -D / 2 - 0.007, H - 0.065), "led_green", bevel=0)
    for r_ in range(4):
        for c in range(3):
            b.box((0.016, 0.003, 0.012), (px - 0.022 + c * 0.022, -D / 2 - 0.007, 0.21 - r_ * 0.022), "plastic_grey", bevel=0.001)
    knob(b, (px, -D / 2 - 0.006, 0.08), r=0.018, depth=0.018)
    return b


def toaster(name="toaster"):
    W, D, H = 0.32, 0.21, 0.22
    b = Model(name)
    b.box((W, D, H - 0.012), (0, 0, 0.012 + (H - 0.012) / 2), "chrome", bevel=0.03, seg=5)
    b.box((W + 0.006, D + 0.006, 0.02), (0, 0, 0.018), "black", bevel=0.006)
    for i in range(2):
        b.box((W - 0.07, 0.03, 0.004), (0, -0.04 + i * 0.08, H + 0.0005), "black", bevel=0)
    b.box((0.022, 0.012, 0.09), (W / 2 + 0.003, 0, 0.13), "black", bevel=0)
    b.box((0.028, 0.03, 0.012), (W / 2 + 0.02, 0, 0.15), "black_gloss", bevel=0.003)
    knob(b, (W / 2 - 0.06, -D / 2 - 0.0, 0.06), r=0.013, depth=0.012)
    return b


def dishwasher(name="dishwasher"):
    W, D, H = 0.6, 0.65, 0.85
    b = Model(name)
    b.box((W, D, H - 0.08), (0, 0, 0.08 + (H - 0.08) / 2), "steel", bevel=0.004)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), h=0.08, r=0.016)
    b.box((W - 0.012, 0.014, 0.075), (0, -D / 2 + 0.0, 0.09), "steel_dark", bevel=0.002)
    # door + recessed bar handle + control strip
    b.box((W - 0.014, 0.035, 0.6), (0, -D / 2 - 0.016, 0.44), "steel", bevel=0.007, seg=3)
    bar_handle_h(b, -W / 2 + 0.05, W / 2 - 0.05, -D / 2 - 0.03, 0.67, off=0.045, r=0.011)
    b.box((W - 0.014, 0.012, 0.09), (0, -D / 2 - 0.004, H - 0.058), "black_gloss", bevel=0.004)
    b.box((0.13, 0.003, 0.03), (-W / 2 + 0.11, -D / 2 - 0.011, H - 0.058), "led_green", bevel=0)
    for i in range(5):
        b.cyl(0.012, 0.004, (0.02 + i * 0.05, -D / 2 - 0.01, H - 0.058), "chrome", rot=(90, 0, 0), seg=16)
    return b


def sink_unit(name="sink_unit", W=1.0, bowls=1):
    """Stainless bench sink with a REAL recessed bowl, drain, gooseneck mixer and undershelf."""
    D, H = 0.65, 0.9
    b = Model(name)
    t = 0.04
    bw, bd, bh = 0.46 * (W / 1.0 if bowls == 1 else 0.5), 0.4, 0.24
    cxs = [0.0] if bowls == 1 else [-W / 4, W / 4]
    # top plate built around the opening(s)
    left = -W / 2
    xs = []
    for c in cxs:
        xs += [c - bw / 2, c + bw / 2]
    edges = [left] + xs + [W / 2]
    for i in range(0, len(edges), 2):
        x0, x1 = edges[i], edges[i + 1]
        if x1 - x0 > 1e-3:
            b.box((x1 - x0, D, t), ((x0 + x1) / 2, 0, H - t / 2), "steel", bevel=0.002)
    for c in cxs:
        by = -0.01
        b.box((bw, (D - bd) / 2 + by, t), (c, -D / 2 + ((D - bd) / 2 + by) / 2, H - t / 2), "steel", bevel=0.002)
        b.box((bw, (D - bd) / 2 - by, t), (c, D / 2 - ((D - bd) / 2 - by) / 2, H - t / 2), "steel", bevel=0.002)
        # bowl walls and base
        for sx in (-1, 1):
            b.box((0.004, bd, bh), (c + sx * (bw / 2 - 0.002), by, H - bh / 2), "steel", bevel=0)
        for sy in (-1, 1):
            b.box((bw, 0.004, bh), (c, by + sy * (bd / 2 - 0.002), H - bh / 2), "steel", bevel=0)
        b.box((bw, bd, 0.004), (c, by, H - bh), "steel", bevel=0)
        b.lathe([(0, 0), (0.04, 0), (0.042, 0.004), (0.02, 0.004), (0, 0.002)], (c, by, H - bh + 0.002), "chrome", seg=24)
        b.cyl(0.024, 0.2, (c, by, H - bh - 0.2), "chrome", seg=14)
    # upstand and mixer tap
    b.box((W, 0.02, 0.15), (0, D / 2 - 0.01, H + 0.075), "steel", bevel=0.003)
    for c in cxs:
        ty = D / 2 - 0.07
        b.lathe([(0.03, 0), (0.028, 0.01), (0.016, 0.018), (0.016, 0.1), (0, 0.1)], (c, ty, H), "chrome", seg=20)
        b.tube([(c, ty, H + 0.08), (c, ty, H + 0.28), (c, ty - 0.06, H + 0.37), (c, ty - 0.17, H + 0.34), (c, ty - 0.19, H + 0.26)], 0.011, "chrome", seg=12, samples=6)
        b.lathe([(0.013, 0), (0.016, 0.01), (0.016, 0.03), (0, 0.03)], (c, ty - 0.19, H + 0.24), "chrome", seg=16)
        b.tube([(c + 0.016, ty, H + 0.06), (c + 0.1, ty, H + 0.075)], 0.006, "chrome", seg=8, samples=1)
    # front apron, legs, undershelf
    b.box((W, 0.02, 0.12), (0, -D / 2 + 0.01, H - t - 0.06), "steel", bevel=0.002)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.box((0.04, 0.04, H - t - 0.03), (sx * (W / 2 - 0.04), sy * (D / 2 - 0.05), (H - t - 0.03) / 2 + 0.03), "steel", bevel=0.004)
            b.cyl(0.026, 0.03, (sx * (W / 2 - 0.04), sy * (D / 2 - 0.05), 0), "rubber", seg=14)
    b.box((W - 0.03, D - 0.05, 0.02), (0, 0, 0.26), "steel", bevel=0.002)
    return b


def basin(name="basin"):
    W, D = 0.45, 0.4
    b = Model(name)
    H = 0.86
    b.lathe([(0, H - 0.14), (0.15, H - 0.14), (0.195, H - 0.05), (0.205, H), (0.225, H), (0.225, H - 0.02), (0.21, H - 0.11), (0.14, H - 0.18), (0.05, H - 0.2), (0.03, H - 0.26), (0, H - 0.26)], (0, 0, 0), "ceramic", seg=40)
    b.lathe([(0, 0), (0.115, 0), (0.115, 0.012), (0.075, 0.05), (0.06, 0.35), (0.075, H - 0.28), (0.09, H - 0.24), (0, H - 0.24)], (0, 0.03, 0), "ceramic", seg=32)
    b.lathe([(0, 0), (0.022, 0), (0.016, 0.01), (0.012, 0.015), (0, 0.015)], (0, 0, H - 0.14), "chrome", seg=16)
    b.tube([(0, 0.17, H), (0, 0.17, H + 0.14), (0, 0.11, H + 0.2), (0, 0.05, H + 0.17)], 0.009, "chrome", seg=10, samples=5)
    b.cyl(0.024, 0.04, (0, 0.17, H), "chrome", seg=16)
    return b


def toilet(name="toilet"):
    b = Model(name)
    # pedestal and bowl as a lofted surface
    def bowl(u, v):
        a = 2 * math.pi * u
        h = 0.40 * v
        rx = 0.1 + 0.085 * v ** 2.2
        ry = 0.13 + 0.13 * v ** 2.2
        return (rx * math.cos(a), -0.05 + (ry * math.sin(a)) - 0.03 * v, h)
    b.surface(bowl, 36, 10, "ceramic", wrap_u=True)
    def rim(u, v):
        a = 2 * math.pi * u
        return ((0.185 + 0.006 * math.sin(v * 3.14)) * math.cos(a), -0.08 + (0.26 + 0.006 * math.sin(v * 3.14)) * math.sin(a), 0.40 + 0.03 * v)
    b.surface(rim, 36, 5, "plastic_white", wrap_u=True)
    def lid(u, v):
        a = 2 * math.pi * u
        k = math.sqrt(max(0.0, 1 - v * v))
        return (0.178 * k * math.cos(a), -0.08 + 0.252 * k * math.sin(a), 0.43 + 0.03 * v)
    b.surface(lid, 36, 8, "plastic_white", wrap_u=True)
    b.box((0.38, 0.17, 0.36), (0, 0.235, 0.56), "ceramic", bevel=0.022, seg=3)
    b.box((0.2, 0.2, 0.2), (0, 0.17, 0.3), "ceramic", bevel=0.03, seg=3)
    b.box((0.4, 0.18, 0.025), (0, 0.235, 0.75), "ceramic", bevel=0.01)
    b.cyl(0.03, 0.006, (0, 0.235, 0.762), "chrome", seg=20)
    return b


def ice_maker(name="ice_maker"):
    W, D, H = 0.62, 0.72, 1.3
    b = Model(name)
    b.box((W, D, H - 0.12), (0, 0, 0.12 + (H - 0.12) / 2), "steel", bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot(b, sx * (W / 2 - 0.06), sy * (D / 2 - 0.06), h=0.12, r=0.02)
    # lower storage bin door (sloped up-swing), handle
    zb = 0.42
    b.box((W - 0.05, 0.04, 0.5), (0, -D / 2 - 0.012, zb), "steel", bevel=0.009, seg=3)
    bar_handle_h(b, -W / 2 + 0.09, W / 2 - 0.09, -D / 2 - 0.03, zb + 0.18, off=0.04, r=0.011)
    # head unit: louvres + brand plate + status LEDs
    for i in range(9):
        b.box((W - 0.1, 0.008, 0.016), (0, -D / 2 - 0.003, 0.84 + i * 0.03), "black_metal", bevel=0)
    b.box((0.16, 0.005, 0.04), (0, -D / 2 - 0.003, H - 0.075), "chrome", bevel=0.001)
    for i, m in enumerate(("led_green", "led_red")):
        b.cyl(0.006, 0.003, (W / 2 - 0.1 + i * 0.03, -D / 2 - 0.002, H - 0.075), m, rot=(90, 0, 0), seg=10)
    return b


# ------------------------------------------------------------------ coffee bar
def espresso(name, body="steel", accent="black_gloss", groups=2):
    W = 0.34 + 0.27 * groups
    D, H = 0.58, 0.54
    b = Model(name)
    # lower chassis with visible steel feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.lathe([(0.024, 0), (0.018, 0.012), (0.014, 0.05), (0, 0.05)], (sx * (W / 2 - 0.05), sy * (D / 2 - 0.08), 0), "chrome", seg=16)
    # base with deep drip tray + slotted grate
    b.box((W, D, 0.075), (0, 0.0, 0.085), body, bevel=0.012, seg=3)
    b.box((W - 0.1, 0.2, 0.012), (0, -D / 2 + 0.11, 0.126), "black_metal", bevel=0.001)
    for i in range(int((W - 0.14) / 0.016)):
        b.box((0.007, 0.17, 0.003), (-W / 2 + 0.07 + i * 0.016, -D / 2 + 0.11, 0.133), "chrome", bevel=0)
    # back tower and upper head (real C-shape with open cup bay)
    b.box((W, 0.3, 0.27), (0, D / 2 - 0.15, 0.255), body, bevel=0.012, seg=3)
    b.box((W, D - 0.06, 0.12), (0, 0.03, H - 0.08), body, bevel=0.018, seg=4)
    b.box((W - 0.06, 0.006, 0.19), (0, D / 2 - 0.303, 0.23), accent, bevel=0.001)
    # cup-warmer: solid plate with fine slots
    b.box((W - 0.05, D - 0.14, 0.006), (0, 0.04, H - 0.018), "steel_dark", bevel=0.001)
    for i in range(int((W - 0.14) / 0.04)):
        b.box((0.005, D - 0.2, 0.002), (-W / 2 + 0.07 + i * 0.04, 0.04, H - 0.0145), "black", bevel=0)
    for sx in (-1, 1):
        for y in (-0.2, 0.26):
            b.cyl(0.006, 0.06, (sx * (W / 2 - 0.02), y, H - 0.02), "chrome", seg=10)
        b.tube([(sx * (W / 2 - 0.02), -0.2, H + 0.04), (sx * (W / 2 - 0.02), 0.26, H + 0.04)], 0.006, "chrome", seg=8, samples=1)
    b.tube([(-W / 2 + 0.02, 0.26, H + 0.04), (W / 2 - 0.02, 0.26, H + 0.04)], 0.006, "chrome", seg=8, samples=1)
    b.tube([(-W / 2 + 0.02, -0.2, H + 0.04), (W / 2 - 0.02, -0.2, H + 0.04)], 0.006, "chrome", seg=8, samples=1)
    # front fascia with screen/pressure gauges and brand plate
    fz = H - 0.08
    b.box((W - 0.04, 0.006, 0.08), (0, -D / 2 + 0.028, fz), accent, bevel=0.002)
    for sx in (-1, 1):
        x = sx * (W / 2 - 0.09)
        b.lathe([(0, 0), (0.03, 0), (0.032, 0.006), (0.027, 0.012), (0, 0.009)], (x, -D / 2 + 0.025, fz), "chrome", seg=24, rot=(90, 0, 0))
        b.cyl(0.024, 0.001, (x, -D / 2 + 0.012, fz), "plastic_white", rot=(90, 0, 0), seg=20)
        b.box((0.002, 0.001, 0.018), (x + 0.003, -D / 2 + 0.01, fz + 0.005), "led_red", bevel=0, rot=(0, 20, 0))
    b.box((0.13, 0.003, 0.03), (0, -D / 2 + 0.024, fz + 0.012), "brass", bevel=0.001)
    # group heads, portafilters with turned timber handles, brew buttons
    start = -(groups - 1) * 0.135
    for i in range(groups):
        x = start + i * 0.27
        gz = H - 0.14
        b.lathe([(0, 0), (0.05, 0), (0.05, 0.012), (0.056, 0.018), (0.056, 0.06), (0.05, 0.075), (0, 0.075)], (x, -D / 2 + 0.11, gz - 0.075), "chrome", seg=32)
        pz = gz - 0.105
        b.lathe([(0, 0), (0.044, 0), (0.05, 0.012), (0.052, 0.034), (0.058, 0.04), (0, 0.04)], (x, -D / 2 + 0.11, pz), "chrome", seg=32)
        b.cyl(0.011, 0.024, (x - 0.018, -D / 2 + 0.11, pz - 0.022), "chrome", seg=10)
        b.cyl(0.011, 0.024, (x + 0.018, -D / 2 + 0.11, pz - 0.022), "chrome", seg=10)
        hy = -D / 2 + 0.06
        b.lathe([(0.012, 0), (0.016, 0.014), (0.019, 0.05), (0.021, 0.09), (0.02, 0.115), (0.013, 0.125), (0, 0.128)], (x, hy, pz + 0.02), "walnut_h", seg=16, rot=(90, 0, 0))
        b.cyl(0.011, 0.02, (x, hy + 0.012, pz + 0.02), "chrome", rot=(90, 0, 0), seg=12)
        for k in range(4):
            b.cyl(0.0085, 0.006, (x - 0.042 + k * 0.028, -D / 2 + 0.025, fz - 0.024), "chrome", rot=(90, 0, 0), seg=12)
    # steam wands (bent, articulated) and knobs
    for sx in (-1, 1):
        x = sx * (W / 2 - 0.055)
        b.tube([(x, -D / 2 + 0.1, H - 0.14), (x, -D / 2 + 0.06, H - 0.18), (x + sx * 0.04, -D / 2 + 0.04, H - 0.3), (x + sx * 0.05, -D / 2 + 0.035, H - 0.36)], 0.0055, "chrome", seg=10, samples=6)
        b.lathe([(0.008, 0), (0.012, 0.008), (0.012, 0.02), (0, 0.022)], (x + sx * 0.05, -D / 2 + 0.035, H - 0.38), "chrome", seg=12)
        b.lathe([(0, 0), (0.028, 0), (0.03, 0.012), (0.024, 0.036), (0, 0.04)], (x + sx * 0.0, -D / 2 + 0.02, H - 0.11) if False else (sx * (W / 2 + 0.0), 0.02, H - 0.11), "walnut_h", seg=20, rot=(0, sx * 90, 0))
    # hot water tap
    b.tube([(0, -D / 2 + 0.11, H - 0.14), (0, -D / 2 + 0.075, H - 0.17), (0, -D / 2 + 0.075, H - 0.24)], 0.008, "chrome", seg=10, samples=4) if groups != 2 else b.tube([(0, -D / 2 + 0.11, H - 0.15), (0, -D / 2 + 0.075, H - 0.18), (0, -D / 2 + 0.075, H - 0.25)], 0.008, "chrome", seg=10, samples=4)
    return b


def grinder(name="grinder", body="black_metal"):
    W, D, H = 0.2, 0.28, 0.62
    b = Model(name)
    b.box((W + 0.02, D + 0.02, 0.02), (0, 0, 0.01), "chrome", bevel=0.004)
    b.box((W, D, 0.3), (0, 0.02, 0.17), body, bevel=0.018, seg=3)
    # burr housing, dosing spout + portafilter fork, touch display
    b.lathe([(0, 0), (0.07, 0), (0.08, 0.01), (0.08, 0.05), (0.065, 0.06), (0, 0.06)], (0, 0.02, 0.32), "chrome", seg=32)
    b.box((W - 0.02, 0.06, 0.05), (0, -D / 2 + 0.02, 0.255), body, bevel=0.012)
    b.cyl(0.02, 0.05, (0, -D / 2 + 0.0, 0.2), "chrome", seg=16, r2=0.028)
    for sx in (-1, 1):
        b.box((0.01, 0.075, 0.016), (sx * 0.038, -D / 2 - 0.03, 0.125), "chrome", bevel=0.002)
    b.box((0.09, 0.09, 0.012), (0, -D / 2 + 0.018, 0.026), "black", bevel=0.002)
    # glass hopper with beans and a lid (lathed)
    z = 0.38
    b.lathe([(0, 0), (0.045, 0), (0.095, 0.11), (0.1, 0.2), (0, 0.2)], (0, 0.02, z), "glass_dark", seg=32)
    b.lathe([(0, 0.02), (0.05, 0.02), (0.085, 0.1), (0, 0.125)], (0, 0.02, z), "beans", seg=24)
    b.lathe([(0.108, 0), (0.108, 0.018), (0.09, 0.03), (0.012, 0.036), (0.012, 0.05), (0, 0.052)], (0, 0.02, z + 0.2), "black_gloss", seg=32)
    return b


def blender_bar(name="blender_bar"):
    b = Model(name)
    b.box((0.19, 0.2, 0.15), (0, 0, 0.08), "black_metal", bevel=0.022, seg=3)
    b.box((0.2, 0.21, 0.012), (0, 0, 0.012), "rubber", bevel=0.003)
    for i in range(3):
        b.box((0.03, 0.004, 0.012), (-0.045 + i * 0.045, -0.101, 0.11), "chrome", bevel=0.001)
    knob(b, (0, -0.1, 0.06), r=0.022, depth=0.02, mat="chrome")
    b.lathe([(0.07, 0), (0.078, 0.02), (0.095, 0.24), (0.1, 0.3), (0, 0.3)], (0, 0, 0.155), "glass", seg=32)
    b.lathe([(0, 0), (0.06, 0.0), (0.082, 0.14), (0, 0.14)], (0, 0, 0.17), "juice2", seg=24)
    b.lathe([(0.105, 0), (0.105, 0.02), (0.09, 0.03), (0.035, 0.03), (0.035, 0.05), (0, 0.05)], (0, 0, 0.45), "black", seg=32)
    b.tube([(0.09, 0, 0.43), (0.15, 0, 0.42), (0.15, 0, 0.25), (0.08, 0, 0.2)], 0.012, "black", seg=10, samples=5)
    return b


def water_boiler(name="boiler"):
    W, D, H = 0.3, 0.36, 0.48
    b = Model(name)
    b.box((W, D, H - 0.03), (0, 0, 0.03 + (H - 0.03) / 2), "steel", bevel=0.012, seg=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b.cyl(0.014, 0.03, (sx * (W / 2 - 0.04), sy * (D / 2 - 0.05), 0), "rubber", seg=12)
    b.box((W - 0.05, 0.006, 0.09), (0, -D / 2 - 0.002, H - 0.09), "black_gloss", bevel=0.002)
    b.box((0.09, 0.002, 0.03), (0, -D / 2 - 0.006, H - 0.08), "led_red", bevel=0)
    b.lathe([(0, 0), (0.04, 0), (0.042, 0.006), (0.036, 0.012), (0, 0.009)], (-0.08, -D / 2 - 0.0, 0.22), "chrome", seg=24, rot=(90, 0, 0))
    b.tube([(0, -D / 2 - 0.0, 0.15), (0, -D / 2 - 0.05, 0.14), (0, -D / 2 - 0.05, 0.1)], 0.01, "chrome", seg=10, samples=4)
    b.box((0.025, 0.05, 0.05), (0, -D / 2 - 0.05, 0.18), "black", bevel=0.005)
    b.box((W - 0.05, 0.1, 0.012), (0, -D / 2 - 0.03, 0.04), "chrome", bevel=0.002)
    return b


def pos_terminal(name="pos"):
    plain("pos_ui", "#0c0e10", 0.18, emit="#27323a", emit_power=0.7)
    b = Model(name)
    b.lathe([(0, 0), (0.07, 0), (0.075, 0.004), (0.045, 0.012), (0.016, 0.018), (0, 0.018)], (0, 0, 0), "black_metal", seg=32)
    b.tube([(0, 0, 0.012), (0, 0.015, 0.07), (0, 0.012, 0.11)], 0.01, "black_metal", seg=10, samples=5)
    b.box((0.26, 0.012, 0.18), (0, 0.0, 0.18), "black_gloss", bevel=0.006, seg=3, rot=(-20, 0, 0))
    b.box((0.235, 0.002, 0.155), (0, -0.0075, 0.1815), "pos_ui", bevel=0, rot=(-20, 0, 0))
    b.box((0.07, 0.12, 0.024), (0.19, -0.02, 0.015), "black_metal", bevel=0.007, rot=(8, 0, 0))
    b.box((0.05, 0.002, 0.038), (0.19, -0.03, 0.03), "pos_ui", bevel=0, rot=(98, 0, 0))
    return b


def hood(name="hood"):
    W, D = 1.2, 0.85
    b = Model(name)
    b.box((W, D, 0.14), (0, 0, 0.07), "steel", bevel=0.005)
    def h(u, v):
        return ((W / 2 - 0.3 * v) * (2 * u - 1), (D / 2 - 0.16 * v) * 1.0, 0.14 + 0.2 * v)
    for s in (-1, 1):
        b.surface(lambda u, v: ((W / 2 - 0.34 * v) * (2 * u - 1), s * (D / 2 - 0.2 * v), 0.14 + 0.22 * v), 2, 2, "steel")
        b.surface(lambda u, v: (s * (W / 2 - 0.34 * v), (D / 2 - 0.2 * v) * (2 * u - 1), 0.14 + 0.22 * v), 2, 2, "steel")
    b.box((0.36, 0.26, 0.3), (0, 0, 0.5), "steel", bevel=0.004)
    for i in range(5):
        b.box((0.19, 0.012, 0.09), (-0.45 + i * 0.225, -D / 2 + 0.005, 0.07), "black_metal", bevel=0.001)
    return b


def waste_bin(name="waste_bin"):
    b = Model(name)
    b.lathe([(0, 0), (0.15, 0), (0.17, 0.02), (0.18, 0.6), (0.17, 0.6), (0.165, 0.62), (0.05, 0.68), (0, 0.685)], (0, 0, 0), "steel", seg=36)
    b.lathe([(0.05, 0), (0.055, 0.01), (0.022, 0.02), (0, 0.02)], (0, 0, 0.68), "black", seg=20)
    return b


def extinguisher(name="extinguisher"):
    plain("red_gloss", "#b01b16", 0.22, coat=0.6)
    b = Model(name)
    b.lathe([(0, 0), (0.07, 0), (0.08, 0.02), (0.08, 0.4), (0.055, 0.47), (0.02, 0.5), (0, 0.5)], (0, 0, 0), "red_gloss", seg=32)
    b.box((0.06, 0.02, 0.04), (0, 0, 0.52), "chrome", bevel=0.004)
    b.tube([(0, 0.0, 0.53), (0.05, -0.07, 0.48), (0.09, -0.09, 0.3), (0.1, -0.09, 0.2)], 0.008, "black", seg=8, samples=5)
    return b


# ------------------------------------------------------------------ seating
def chair_bentwood(name, frame="walnut_h", seat="cane"):
    """Thonet-style No.14: steam-bent back hoop + inner hoop, round seat, tapered legs, stretcher ring."""
    b = Model(name)
    sz = 0.46
    r = 0.21
    b.lathe([(0, sz - 0.012), (r - 0.005, sz - 0.012), (r, sz), (r - 0.004, sz + 0.016), (r - 0.022, sz + 0.016), (r - 0.022, sz + 0.012), (0, sz + 0.012)], (0, 0, 0), frame, seg=40)
    b.lathe([(0, sz + 0.012), (r - 0.022, sz + 0.012), (r - 0.022, sz + 0.0135), (0, sz + 0.016)], (0, 0, 0), seat, seg=40)
    for sx in (-1, 1):
        b.tube([(sx * 0.165, 0.14, sz), (sx * 0.2, 0.26, 0.0)], 0.014, frame, seg=10, samples=1)
        b.tube([(sx * 0.15, -0.14, sz), (sx * 0.19, -0.22, 0.0)], 0.015, frame, seg=10, samples=1)
    b.tube([(math.cos(i / 24 * 6.283) * 0.19, math.sin(i / 24 * 6.283) * 0.19, 0.27) for i in range(24)], 0.009, frame, seg=8, samples=1, closed=True)
    # outer steam-bent back hoop running down to the rear legs
    b.tube([(-0.185, 0.2, 0.46), (-0.19, 0.27, 0.72), (-0.13, 0.31, 0.88), (0, 0.325, 0.915), (0.13, 0.31, 0.88), (0.19, 0.27, 0.72), (0.185, 0.2, 0.46)], 0.012, frame, seg=10, samples=8)
    b.tube([(-0.12, 0.19, 0.47), (-0.13, 0.26, 0.66), (-0.08, 0.295, 0.78), (0, 0.305, 0.805), (0.08, 0.295, 0.78), (0.13, 0.26, 0.66), (0.12, 0.19, 0.47)], 0.009, frame, seg=8, samples=8)
    return b


def chair_shell(name, shell="oak_f", legs="black_metal"):
    """Moulded plywood shell on 4 splayed legs."""
    b = Model(name)
    def s(u, v):
        x = (u - 0.5) * (0.44 - 0.06 * v + 0.05 * math.sin(v * math.pi))
        t = v
        if t < 0.5:     # seat pan, front to back
            y = -0.22 + t * 0.84
            z = 0.455 - 0.035 * math.sin(t * 2 * math.pi * 0.5) + 0.03 * (2 * abs(u - 0.5)) ** 2
        else:           # sweep up the back
            a = (t - 0.5) * 2
            y = 0.2 + 0.09 * a ** 0.7
            z = 0.42 + 0.4 * a
        return (x, y, z + 0.03 * (2 * abs(u - 0.5)) ** 2)
    b.surface(s, 18, 26, shell, thick=0.011)
    for sx, sy, tx, ty in ((-1, -1, -0.2, -0.26), (1, -1, 0.2, -0.26), (-1, 1, -0.2, 0.3), (1, 1, 0.2, 0.3)):
        b.tube([(sx * 0.1, sy * 0.1, 0.392), (tx, ty, 0.0)], 0.0115, legs, seg=10, samples=1)
    b.box((0.24, 0.24, 0.012), (0, 0.0, 0.392), legs, bevel=0.003)
    return b


def chair_metal(name, paint):
    """Tolix-style pressed metal chair."""
    m = f"paint_{paint.strip('#')}"
    plain(m, paint, 0.32, 0.65, coat=0.3)
    b = Model(name)
    w = 0.36
    b.box((w, w, 0.012), (0, 0, 0.45), m, bevel=0.004)
    for sx in (-1, 1):
        b.box((0.012, w, 0.04), (sx * (w / 2 - 0.004), 0, 0.432), m, bevel=0.002)
    b.box((w, 0.012, 0.04), (0, -w / 2 + 0.004, 0.432), m, bevel=0.002)
    for sx, sy, tx, ty in ((-1, -1, -0.235, -0.235), (1, -1, 0.235, -0.235), (-1, 1, -0.215, 0.26), (1, 1, 0.215, 0.26)):
        b.box((0.035, 0.012, 0.45), ((sx * 0.17 + tx) / 2, (sy * 0.17 + ty) / 2, 0.222), m, bevel=0.003, rot=(math.degrees(math.atan2(ty - sy * 0.17, 0.44)) * 1.0, -math.degrees(math.atan2(tx - sx * 0.17, 0.44)), 0))
    for d in ((-1, -1, 1, -1), (-1, 1, 1, 1), (-1, -1, -1, 1), (1, -1, 1, 1)):
        b.tube([(d[0] * 0.205, d[1] * 0.205, 0.2), (d[2] * 0.205, d[3] * 0.205, 0.2)], 0.0055, m, seg=8, samples=1)
    for sx in (-1, 1):
        b.tube([(sx * 0.16, 0.17, 0.45), (sx * 0.16, 0.215, 0.66), (sx * 0.14, 0.24, 0.84)], 0.009, m, seg=10, samples=5)
    def back(u, v):
        return ((u - 0.5) * (0.33 - 0.05 * v), 0.225 + 0.02 * v + 0.022 * (2 * u - 1) ** 2, 0.62 + 0.24 * v)
    b.surface(back, 12, 5, m, thick=0.006)
    return b


def chair_tub(name, fabric="velvet_g", legs="brass"):
    """Upholstered tub chair: curved wrap-around back, plump seat, slim tapered legs."""
    b = Model(name)
    def wall(u, v):
        a = math.radians(-30 + u * 240)
        back = max(0.0, math.sin(a))                        # 0 at the arm ends, 1 at the centre of the back
        top = 0.56 + 0.22 * (back * back * (3 - 2 * back))  # smooth step from arm height to back height
        r = 0.285 + 0.015 * math.sin(v * math.pi)
        return (r * math.cos(a), r * math.sin(a) + 0.02, 0.34 + (top - 0.34) * v)
    b.surface(wall, 48, 8, fabric)
    def wall_in(u, v):
        a = math.radians(-30 + (1 - u) * 240)
        back = max(0.0, math.sin(a))
        top = 0.56 + 0.22 * (back * back * (3 - 2 * back))
        return (0.225 * math.cos(a), 0.225 * math.sin(a) + 0.02, 0.34 + (top - 0.34) * v)
    b.surface(wall_in, 48, 8, fabric)
    def wall_top(u, v):
        a = math.radians(-30 + u * 240)
        back = max(0.0, math.sin(a))
        top = 0.56 + 0.22 * (back * back * (3 - 2 * back))
        r = 0.285 - 0.06 * v
        return (r * math.cos(a), r * math.sin(a) + 0.02, top + 0.028 * math.sin(v * math.pi))
    b.surface(wall_top, 48, 5, fabric)
    for u_ in (0.0, 1.0):   # rounded arm ends
        a0 = math.radians(-30 + u_ * 240)
        c0 = (0.255 * math.cos(a0), 0.255 * math.sin(a0) + 0.02)
        b.cyl(0.03, 0.22, (c0[0], c0[1], 0.34), fabric, seg=16, bevel=0.012)
    b.lathe([(0, 0.34), (0.235, 0.34), (0.262, 0.37), (0.262, 0.43), (0.235, 0.462), (0.12, 0.476), (0, 0.48)], (0, 0.015, 0), fabric, seg=48)
    b.lathe([(0, 0), (0.25, 0), (0.262, 0.012), (0.25, 0.03), (0, 0.03)], (0, 0.015, 0.315), "black", seg=40)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        b.lathe([(0.008, 0), (0.013, 0.02), (0.02, 0.32), (0, 0.32)], (sx * 0.17, 0.015 + sy * 0.17, 0), legs, seg=14)
    return b


def stool_leather(name, frame="black_metal", seat="leather_b", ring="brass", h=0.76):
    b = Model(name)
    r = 0.175
    b.lathe([(0, h - 0.05), (r - 0.01, h - 0.05), (r, h - 0.035), (r, h - 0.012), (r - 0.03, h), (0.05, h + 0.006), (0, h + 0.006)], (0, 0, 0), seat, seg=44)
    b.lathe([(0, h - 0.07), (r - 0.025, h - 0.07), (r - 0.012, h - 0.05), (0, h - 0.05)], (0, 0, 0), frame, seg=32)
    n = 4
    for i in range(n):
        a = math.radians(45 + 90 * i)
        b.tube([(math.cos(a) * 0.12, math.sin(a) * 0.12, h - 0.06), (math.cos(a) * 0.22, math.sin(a) * 0.22, 0.012)], 0.0115, frame, seg=10, samples=1)
        b.cyl(0.014, 0.012, (math.cos(a) * 0.22, math.sin(a) * 0.22, 0), "rubber", seg=10)
    zr = h * 0.36
    rr = 0.12 + (0.22 - 0.12) * (h - 0.06 - zr) / (h - 0.072)
    b.tube([(math.cos(i / 32 * 6.283) * rr, math.sin(i / 32 * 6.283) * rr, zr) for i in range(32)], 0.009, ring, seg=8, samples=1, closed=True)
    return b


def stool_wood(name, wood="oak_f", h=0.75):
    """Backless timber stool with saddle seat and H stretchers."""
    b = Model(name)
    def seat(u, v):
        a = 2 * math.pi * u
        r = 0.175 * v
        z = h + 0.022 * (1 - v ** 4) * 0 + 0.02 * v ** 3 - 0.014 * (1 - v) * 0
        return (r * math.cos(a), r * math.sin(a), z)
    b.lathe([(0, h - 0.03), (0.165, h - 0.03), (0.178, h - 0.012), (0.176, h + 0.006), (0.15, h + 0.01), (0.07, h - 0.002), (0, h - 0.004)], (0, 0, 0), wood, seg=44)
    pts = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p = (sx * 0.19, sy * 0.19, 0.0)
        b.lathe([(0.012, 0), (0.016, (h - 0.03) * 0.45), (0.021, (h - 0.03) * 0.9), (0.02, h - 0.03), (0, h - 0.03)], p, wood, seg=14, rot=(sy * -7, sx * -7, 0)) if False else b.tube([(sx * 0.11, sy * 0.11, h - 0.03), (sx * 0.195, sy * 0.195, 0)], 0.0165, wood, seg=12, samples=1)
        pts.append((sx * 0.158, sy * 0.158, 0.28))
    b.tube([pts[0], pts[1]], 0.009, wood, seg=8, samples=1)
    b.tube([pts[2], pts[3]], 0.009, wood, seg=8, samples=1)
    b.tube([((pts[0][0] + pts[1][0]) / 2, pts[0][1], 0.28), ((pts[2][0] + pts[3][0]) / 2, pts[2][1], 0.28)], 0.009, wood, seg=8, samples=1)
    return b


# ------------------------------------------------------------------ pendants (shade only; the kit adds cord + rose + lamp)
def pendant_dome(name, shell="black_metal", inner="plastic_white", W=0.42):
    plain("shade_in", "#fff0d8", 0.4, emit="#ffe2b8", emit_power=1.2)
    b = Model(name)
    R = W / 2
    hh = R * 0.72
    prof = [(0.018 + (R - 0.018) * math.sin(t / 12 * math.pi / 2), hh * math.cos(t / 12 * math.pi / 2)) for t in range(13)]
    b.lathe(prof, (0, 0, 0), shell, seg=48)
    b.lathe([(r * 0.985, z - 0.004) for r, z in reversed(prof)] + [(0, hh - 0.006)], (0, 0, 0), "shade_in", seg=48)
    b.lathe([(0.02, hh - 0.01), (0.024, hh - 0.01), (0.024, hh + 0.05), (0.014, hh + 0.06), (0, hh + 0.06)], (0, 0, 0), "brass", seg=20)
    b.lathe([(0, hh * 0.28), (0.03, hh * 0.32), (0.04, hh * 0.46), (0.028, hh * 0.62), (0.016, hh * 0.7), (0.016, hh * 0.92)], (0, 0, 0), "bulb", seg=20)
    return b


def pendant_globe(name, R=0.15, fit="brass"):
    b = Model(name)
    prof = [(R * math.sin(i / 16 * math.pi), R - R * math.cos(i / 16 * math.pi)) for i in range(17)]
    prof[0] = (0, 0)
    prof[-1] = (0, 2 * R)
    b.lathe(prof, (0, 0, 0), "opal", seg=40)
    b.lathe([(0.035, 2 * R - 0.008), (0.042, 2 * R + 0.012), (0.03, 2 * R + 0.04), (0.012, 2 * R + 0.05), (0.012, 2 * R + 0.07)], (0, 0, 0), fit, seg=24)
    return b


def pendant_rattan(name, W=0.56, H=0.36):
    b = Model(name)
    R = W / 2
    ribs = 36
    for i in range(ribs):
        a = 2 * math.pi * i / ribs
        ca, sa = math.cos(a), math.sin(a)
        b.tube([(ca * (0.03 + (R - 0.03) * (t / 6) ** 0.7), sa * (0.03 + (R - 0.03) * (t / 6) ** 0.7), H * (1 - t / 6) ** 1.25) for t in range(7)], 0.0028, "rattan", seg=5, samples=2)
    for k in range(1, 7):
        t = k / 6.3
        z = H * (1 - t) ** 1.25
        r = 0.03 + (R - 0.03) * t ** 0.7
        b.tube([(math.cos(j / 40 * 6.283) * r, math.sin(j / 40 * 6.283) * r, z) for j in range(40)], 0.0024, "rattan", seg=5, samples=1, closed=True)
    b.tube([(math.cos(j / 56 * 6.283) * R, math.sin(j / 56 * 6.283) * R, 0.0) for j in range(56)], 0.006, "rattan", seg=8, samples=1, closed=True)
    b.lathe([(0, H * 0.25), (0.04, H * 0.28), (0.055, H * 0.42), (0.04, H * 0.58), (0.018, H * 0.65), (0.018, H)], (0, 0, 0), "bulb", seg=20)
    return b


def pendant_fluted(name, W=0.34, H=0.26):
    """Ribbed glass dome."""
    plain("glass_rib", "#fbf0dc", 0.25, emit="#ffdeb0", emit_power=3.0)
    b = Model(name)
    n, nv = 96, 16
    R = W / 2
    def s(u, v):
        a = 2 * math.pi * u
        k = (1 - v) ** 0.55
        r = (0.03 + (R - 0.03) * (1 - (v ** 2))) * (1 + 0.022 * math.cos(a * 24))
        return (r * math.cos(a), r * math.sin(a), H * v)
    b.surface(s, n, nv, "glass_rib", wrap_u=True)
    b.lathe([(0.035, H - 0.005), (0.04, H + 0.02), (0.014, H + 0.05), (0.014, H + 0.07)], (0, 0, 0), "brass", seg=20)
    return b


def pendant_linear(name, L=1.3, finish="black_metal"):
    """Linear bar pendant for over counters and shared tables."""
    b = Model(name)
    b.box((L, 0.06, 0.05), (0, 0, 0.025), finish, bevel=0.006, seg=3)
    b.box((L - 0.02, 0.046, 0.003), (0, 0, 0.0005), "led", bevel=0)
    return b


# ------------------------------------------------------------------ registry
def catalogue():
    t = lambda *a: list(a)  # noqa: E731
    plain("juice2", "#c6532f", 0.3, coat=0.3)
    return [
        ("fridge", "display_1door", "fridge/display_1door.glb", lambda n: fridge_display(n, 1), ALL),
        ("fridge", "display_2door", "fridge/display_2door.glb", lambda n: fridge_display(n, 2), ALL),
        ("fridge_tall", "upright_2door", "fridge/upright_2door.glb", lambda n: fridge_upright(n, 2), ALL),
        ("fridge_tall", "upright_1door", "fridge/upright_1door.glb", lambda n: fridge_upright(n, 1), ALL),
        ("undercounter", "uc_2door", "fridge/uc_2door.glb", lambda n: fridge_undercounter(n, 2), ALL),
        ("undercounter", "uc_1door", "fridge/uc_1door.glb", lambda n: fridge_undercounter(n, 1), ALL),
        ("freezer", "chest", "fridge/chest.glb", freezer_chest, ALL),
        ("stove", "range", "kitchen/range.glb", range_stove, ALL),
        ("oven", "combi", "kitchen/combi.glb", oven_combi, ALL),
        ("oven_counter", "speed", "kitchen/speed_oven.glb", oven_speed, ALL),
        ("microwave", "commercial", "kitchen/microwave.glb", microwave, ALL),
        ("toaster", "chrome", "kitchen/toaster.glb", toaster, ALL),
        ("dishwasher", "undercounter", "kitchen/dishwasher.glb", dishwasher, ALL),
        ("sink", "bench_1", "kitchen/sink_1.glb", lambda n: sink_unit(n, 1.0, 1), ALL),
        ("sink", "bench_2", "kitchen/sink_2.glb", lambda n: sink_unit(n, 1.5, 2), ALL),
        ("basin", "pedestal", "wc/basin.glb", basin, ALL),
        ("toilet", "wall", "wc/toilet.glb", toilet, ALL),
        ("ice_maker", "cuber", "kitchen/ice_maker.glb", ice_maker, ALL),
        ("hood", "canopy", "kitchen/hood.glb", hood, ALL),
        ("waste", "pedal", "kitchen/bin.glb", waste_bin, ALL),
        ("extinguisher", "red", "kitchen/extinguisher.glb", extinguisher, ALL),
        ("espresso", "steel_2g", "equipment/espresso_steel.glb", lambda n: espresso(n, "steel", "black_gloss"), t("industrial", "brutalist", "modern", "japandi", "scandinavian")),
        ("espresso", "black_2g", "equipment/espresso_black.glb", lambda n: espresso(n, "black_metal", "steel"), t("deco", "modern", "industrial", "brutalist", "midcentury")),
        ("espresso", "sage_2g", "equipment/espresso_sage.glb", lambda n: espresso(n, plain("enamel_sage", "#7f9682", 0.28, coat=0.7), "steel"), t("biophilic", "scandinavian", "japandi", "cozy", "mediterranean")),
        ("espresso", "cream_2g", "equipment/espresso_cream.glb", lambda n: espresso(n, plain("enamel_cream", "#e8dfcb", 0.28, coat=0.7), "chrome"), t("bistro", "retro", "mediterranean", "cozy", "midcentury")),
        ("espresso", "terra_3g", "equipment/espresso_terra.glb", lambda n: espresso(n, plain("enamel_terra", "#a9573a", 0.28, coat=0.7), "steel", groups=3), t("retro", "mediterranean", "biophilic", "cozy")),
        ("grinder", "conical", "equipment/grinder.glb", grinder, ALL),
        ("blender", "bar", "equipment/blender.glb", blender_bar, ALL),
        ("boiler", "tap", "equipment/boiler.glb", water_boiler, ALL),
        ("pos", "tablet", "equipment/pos.glb", pos_terminal, ALL),
        ("chair", "bentwood_walnut", "chair/bentwood_walnut.glb", lambda n: chair_bentwood(n, "walnut_h", "cane"), t("bistro", "cozy", "midcentury", "deco", "mediterranean")),
        ("chair", "bentwood_black", "chair/bentwood_black.glb", lambda n: chair_bentwood(n, "black", "cane"), t("bistro", "deco", "modern", "industrial")),
        ("chair", "bentwood_oak", "chair/bentwood_oak.glb", lambda n: chair_bentwood(n, "oak_f", "linen_o"), t("scandinavian", "japandi", "cozy", "biophilic")),
        ("chair", "shell_oak", "chair/shell_oak.glb", lambda n: chair_shell(n, "oak_f", "black_metal"), t("scandinavian", "japandi", "modern", "midcentury", "biophilic")),
        ("chair", "shell_walnut", "chair/shell_walnut.glb", lambda n: chair_shell(n, "walnut_f", "brass"), t("midcentury", "retro", "deco", "cozy")),
        ("chair", "shell_black", "chair/shell_black.glb", lambda n: chair_shell(n, "black_f", "chrome"), t("brutalist", "modern", "industrial")),
        ("chair", "metal_black", "chair/metal_black.glb", lambda n: chair_metal(n, "#1e1f21"), t("industrial", "brutalist", "bistro")),
        ("chair", "metal_olive", "chair/metal_olive.glb", lambda n: chair_metal(n, "#5a6345"), t("industrial", "biophilic", "retro")),
        ("chair", "metal_mustard", "chair/metal_mustard.glb", lambda n: chair_metal(n, "#c49120"), t("retro", "mediterranean")),
        ("lounge", "tub_sage", "lounge/tub_sage.glb", lambda n: chair_tub(n, "velvet_g", "brass"), t("biophilic", "deco", "cozy", "midcentury")),
        ("lounge", "tub_terra", "lounge/tub_terra.glb", lambda n: chair_tub(n, "velvet_t", "black_metal"), t("retro", "mediterranean", "cozy", "midcentury")),
        ("lounge", "tub_navy", "lounge/tub_navy.glb", lambda n: chair_tub(n, "velvet_i", "brass"), t("deco", "modern", "bistro")),
        ("lounge", "tub_boucle", "lounge/tub_boucle.glb", lambda n: chair_tub(n, "boucle_c", "oak_f"), t("scandinavian", "japandi", "modern", "brutalist")),
        ("stool", "leather_black", "stool/leather_black.glb", lambda n: stool_leather(n, "black_metal", "leather_b", "brass"), t("industrial", "deco", "bistro", "cozy", "retro", "midcentury")),
        ("stool", "leather_white", "stool/leather_white.glb", lambda n: stool_leather(n, "steel_dark", "leather_w", "chrome"), t("modern", "scandinavian", "brutalist", "mediterranean")),
        ("stool", "oak", "stool/oak.glb", lambda n: stool_wood(n, "oak_f"), t("scandinavian", "japandi", "biophilic", "cozy")),
        ("stool", "walnut", "stool/walnut.glb", lambda n: stool_wood(n, "walnut_f"), t("midcentury", "cozy", "mediterranean", "retro")),
        ("pendant", "dome_black", "lighting/dome_black.glb", lambda n: pendant_dome(n, "black_metal"), t("industrial", "brutalist", "modern", "bistro")),
        ("pendant", "dome_brass", "lighting/dome_brass.glb", lambda n: pendant_dome(n, "brass"), t("deco", "midcentury", "cozy", "bistro")),
        ("pendant", "dome_sage", "lighting/dome_sage.glb", lambda n: pendant_dome(n, plain("enamel_sage2", "#7f9682", 0.3, coat=0.6)), t("biophilic", "scandinavian", "retro")),
        ("pendant", "globe_brass", "lighting/globe_brass.glb", lambda n: pendant_globe(n, 0.15, "brass"), t("deco", "midcentury", "bistro", "modern", "cozy")),
        ("pendant", "globe_black", "lighting/globe_black.glb", lambda n: pendant_globe(n, 0.15, "black_metal"), t("scandinavian", "modern", "japandi", "industrial")),
        ("pendant", "rattan", "lighting/rattan.glb", pendant_rattan, t("mediterranean", "biophilic", "japandi", "cozy")),
        ("pendant", "fluted", "lighting/fluted.glb", pendant_fluted, t("deco", "retro", "mediterranean", "modern", "bistro")),
        ("pendant_linear", "bar_black", "lighting/bar_black.glb", lambda n: pendant_linear(n, 1.3, "black_metal"), t("industrial", "brutalist", "modern", "scandinavian", "japandi")),
        ("pendant_linear", "bar_brass", "lighting/bar_brass.glb", lambda n: pendant_linear(n, 1.3, "brass"), t("deco", "midcentury", "bistro", "cozy", "retro", "mediterranean", "biophilic")),
    ]


def export(o, rel):
    path = os.path.join(MODELS, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                              export_image_format="WEBP", export_image_quality=80, export_lights=False, export_cameras=False)
    return os.path.getsize(path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats()
    man = json.load(open(MANIFEST))
    fails = 0
    for cat, variant, rel, fn, tags in catalogue():
        if only and only not in rel:
            continue
        try:
            b = fn(variant)
            o = b.build()
            bb = [o.matrix_world @ __import__("mathutils").Vector(c) for c in o.bound_box]
            mn = [min(c[i] for c in bb) for i in range(3)]
            mx = [max(c[i] for c in bb) for i in range(3)]
            kb = export(o, rel) // 1024
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            items = [i for i in man.setdefault(cat, []) if i.get("variant") != variant]
            items.append({"variant": variant, "file": rel, "footprint": [round(mx[0] - mn[0], 3), round(mx[1] - mn[1], 3)], "height": round(mx[2] - mn[2], 3),
                          "forward_deg": 0, "fit": "real", "style_tags": tags, "tris": tris, "source": "custom:author_models.py", "license": "CC0"})
            man[cat] = items
            print(f"MODEL {rel:34s} {tris:7d} tris {kb:6d} KB  {mx[0]-mn[0]:.2f}x{mx[1]-mn[1]:.2f}x{mx[2]-mn[2]:.2f}  z0={mn[2]:.3f}", flush=True)
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception as e:  # noqa: BLE001
            fails += 1
            import traceback
            print(f"FAILED {rel}: {e}\n{traceback.format_exc()}", flush=True)
    json.dump(man, open(MANIFEST, "w"), indent=1)
    print(f"AUTHOR_DONE fails={fails}", flush=True)


if __name__ == "__main__":
    main()
