#!/usr/bin/env python3
"""gen_textures.py — procedural textures Poly Haven lacks (glazed tile, white marble, art prints, menu boards).
Plain Python + Pillow:  python3 blender/gen_textures.py"""
import json, math, os, random
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "textures"))


def normal_from_height(h, strength=2.0):
    """Sobel normal map (OpenGL) from an L height image."""
    def sob(k):
        return h.filter(ImageFilter.Kernel((3, 3), k, scale=max(1, 8 / strength), offset=128))
    gx = sob((-1, 0, 1, -2, 0, 2, -1, 0, 1))
    gy = sob((-1, -2, -1, 0, 0, 0, 1, 2, 1))
    return Image.merge("RGB", (ImageOps.invert(gx), gy, Image.new("L", h.size, 255)))


def save(name, color, rough, height, size_m, strength=2.0):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    color.convert("RGB").save(os.path.join(d, "color.jpg"), quality=90)
    rough.convert("RGB").save(os.path.join(d, "rough.jpg"), quality=90)
    normal_from_height(height, strength).save(os.path.join(d, "normal.jpg"), quality=90)
    json.dump({"id": "procedural", "license": "CC0", "size_m": [size_m, size_m]}, open(os.path.join(d, "meta.json"), "w"))
    print("ok", name)


def tiles(name, layout, nx, ny, size_m, var=16, glaze=(40, 85), base=205, grout=150, seed=1, strength=2.2):
    """layout 'grid' | 'brick' | 'hex'. Colour image stays neutral light so any tint works (tile colour is chosen by the kit)."""
    random.seed(seed)
    S = 1024
    col = Image.new("L", (S, S), grout)
    hgt = Image.new("L", (S, S), 60)
    rgh = Image.new("L", (S, S), 190)
    dc, dh, dr = ImageDraw.Draw(col), ImageDraw.Draw(hgt), ImageDraw.Draw(rgh)
    tw, th = S / nx, S / ny
    g = max(3, int(S / nx * 0.045))
    def paint(poly):
        v = base + random.randint(-var, var)
        dc.polygon(poly, fill=max(0, min(255, v)))
        dh.polygon(poly, fill=210 + random.randint(-22, 22))
        dr.polygon(poly, fill=random.randint(*glaze))
    if layout == "hex":
        R = tw / math.sqrt(3)
        rows = int(S / (1.5 * R)) + 2
        for r in range(-1, rows):
            for c in range(-1, nx + 2):
                cx = c * tw + (tw / 2 if r % 2 else 0)
                cy = r * 1.5 * R
                rr = R - g * 0.7
                paint([(cx + rr * math.cos(math.radians(60 * k + 30)), cy + rr * math.sin(math.radians(60 * k + 30))) for k in range(6)])
    else:
        for j in range(-1, ny + 1):
            off = tw / 2 if (layout == "brick" and j % 2) else 0
            for i in range(-1, nx + 2):
                x, y = i * tw + off, j * th
                jit = 1.5 if name.startswith("zellige") else 0.0
                paint([(x + g / 2 + random.uniform(-jit, jit), y + g / 2 + random.uniform(-jit, jit)), (x + tw - g / 2 + random.uniform(-jit, jit), y + g / 2 + random.uniform(-jit, jit)),
                       (x + tw - g / 2 + random.uniform(-jit, jit), y + th - g / 2 + random.uniform(-jit, jit)), (x + g / 2 + random.uniform(-jit, jit), y + th - g / 2 + random.uniform(-jit, jit))])
    hgt = hgt.filter(ImageFilter.GaussianBlur(1.6))
    if name.startswith(("zellige", "terracotta")):   # hand-made surface undulation
        n = Image.effect_noise((S // 8, S // 8), 70).resize((S, S), Image.BICUBIC)
        hgt = ImageChops.add(hgt, n.point(lambda p: (p - 128) * 0.35), offset=0)
        col = ImageChops.multiply(col, n.point(lambda p: 215 + (p - 128) * 0.28).convert("L"))
    save(name, col, rgh, hgt, size_m, strength)


def carrara():
    """White marble from the dark veined source: invert, lift, keep veins subtle."""
    s = Image.open(os.path.join(OUT, "marble", "color.jpg")).convert("L")
    v = ImageOps.invert(s)
    v = ImageOps.autocontrast(v, cutoff=1).point(lambda p: 150 + p * 0.41)
    d = os.path.join(OUT, "marble_carrara")
    os.makedirs(d, exist_ok=True)
    c = Image.merge("RGB", (v, v.point(lambda p: p * 0.99), v.point(lambda p: p * 0.97)))
    c.save(os.path.join(d, "color.jpg"), quality=90)
    Image.new("RGB", (64, 64), (46, 46, 46)).save(os.path.join(d, "rough.jpg"))
    Image.new("RGB", (64, 64), (128, 128, 255)).save(os.path.join(d, "normal.jpg"))
    json.dump({"id": "derived:marble", "license": "CC0", "size_m": [1.2, 1.2]}, open(os.path.join(d, "meta.json"), "w"))
    print("ok marble_carrara")


PALS = [("#e9dfcc", "#b9583a", "#2f3e46", "#d8a24a"), ("#f1ebe0", "#1f2a30", "#a9b8a2", "#c97b56"), ("#20302b", "#d9c7a3", "#7c8f6c", "#b5563a"),
        ("#efe7d9", "#3b2a22", "#c29a55", "#8c3b2a"), ("#dfe3dd", "#51645a", "#e2b98f", "#232323"), ("#1c1c20", "#c8a35a", "#e8e0d0", "#7c2f2a")]


def art():
    d = os.path.join(OUT, "art")
    os.makedirs(d, exist_ok=True)
    W, H = 900, 1200
    for n in range(12):
        random.seed(100 + n)
        bg, a, b, c = PALS[n % len(PALS)]
        im = Image.new("RGB", (W, H), bg)
        dr = ImageDraw.Draw(im)
        k = n % 6
        if k == 0:      # arches
            for i in range(5):
                w = W - 120 - i * 130
                x0 = (W - w) / 2
                col = (a, b, c, bg, a)[i]
                dr.pieslice((x0, 260 + i * 65, x0 + w, 260 + i * 65 + w), 180, 360, fill=col)
                dr.rectangle((x0, 260 + i * 65 + w / 2, x0 + w, H - 120), fill=col)
        elif k == 1:    # sun over hills
            dr.ellipse((230, 170, 670, 610), fill=a)
            for i, col in enumerate((b, c, a)):
                pts = [(0, H)] + [(x, 690 + i * 150 + 70 * math.sin(x / (170 - i * 25) + i * 2)) for x in range(0, W + 20, 20)] + [(W, H)]
                dr.polygon(pts, fill=col)
        elif k == 2:    # bauhaus blocks
            s = 225
            for j in range(5):
                for i in range(4):
                    x, y = i * s, j * s + 40
                    col = random.choice((a, b, c))
                    t = random.randint(0, 3)
                    if t == 0:
                        dr.rectangle((x, y, x + s, y + s), fill=col)
                    elif t == 1:
                        dr.ellipse((x, y, x + s, y + s), fill=col)
                    elif t == 2:
                        dr.pieslice((x - s, y - s if random.random() < .5 else y, x + s, y + s if random.random() < .5 else y + 2 * s), 0, 180, fill=col)
                    else:
                        dr.polygon([(x, y), (x + s, y), (x, y + s)], fill=col)
        elif k == 3:    # botanical line stems
            for i in range(7):
                x = 130 + i * 110
                y1 = random.randint(180, 420)
                dr.line((x, H - 80, x + random.randint(-30, 30), y1), fill=a, width=7)
                for t in range(7):
                    yy = H - 170 - t * (H - 170 - y1) / 7
                    for s_ in (-1, 1):
                        dr.ellipse((x + s_ * 62 - 42, yy - 15, x + s_ * 62 + 42, yy + 15), fill=random.choice((b, c)))
        elif k == 4:    # horizon bands
            y = 0
            for col in (a, bg, b, c, a, b):
                h_ = random.randint(120, 300)
                dr.rectangle((0, y, W, y + h_), fill=col)
                y += h_
            dr.ellipse((300, 300, 600, 600), fill=bg)
        else:           # matisse blobs
            for i in range(11):
                cx, cy, r = random.randint(60, W - 60), random.randint(60, H - 60), random.randint(70, 180)
                dr.polygon([(cx + (r + random.randint(-55, 55)) * math.cos(t / 11 * 6.283), cy + (r + random.randint(-55, 55)) * math.sin(t / 11 * 6.283)) for t in range(11)], fill=random.choice((a, b, c)))
        im = im.filter(ImageFilter.GaussianBlur(0.7))
        grain = Image.effect_noise((W, H), 16).convert("RGB")
        im = Image.blend(im, ImageChops.overlay(im, grain), 0.35)
        im.save(os.path.join(d, f"art_{n:02d}.jpg"), quality=86)
    print("ok art x12")


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


MENU = [("COFFEE", [("Espresso", "2.60"), ("Cortado", "3.40"), ("Flat White", "4.20"), ("Cappuccino", "4.20"), ("Latte", "4.50"), ("Filter", "3.60")]),
        ("COLD", [("Cold Brew", "4.50"), ("Iced Latte", "4.80"), ("Tonic Espresso", "5.20"), ("Lemonade", "4.20")]),
        ("BAKERY", [("Croissant", "3.20"), ("Pain au Chocolat", "3.60"), ("Carrot Cake", "4.80"), ("Banana Bread", "3.90")])]


def menus():
    d = os.path.join(OUT, "menu")
    os.makedirs(d, exist_ok=True)
    for n, (bg, fg, ac) in enumerate((("#14110e", "#efe6d5", "#c9a35a"), ("#f2ecdf", "#23201c", "#a4502f"), ("#1d2b26", "#e9e3d1", "#c7ab6a"))):
        W, H = 1600, 900
        im = Image.new("RGB", (W, H), bg)
        dr = ImageDraw.Draw(im)
        for c, (title, rows) in enumerate(MENU):
            x = 70 + c * 505
            dr.text((x, 60), title, font=font(62), fill=ac)
            dr.line((x, 145, x + 450, 145), fill=ac, width=3)
            for i, (a, p) in enumerate(rows):
                y = 180 + i * 104
                dr.text((x, y), a, font=font(40), fill=fg)
                pw = dr.textlength(p, font=font(40))
                dr.text((x + 450 - pw, y), p, font=font(40), fill=fg)
        im.save(os.path.join(d, f"menu_{n}.jpg"), quality=88)
    print("ok menus x3")


if __name__ == "__main__":
    tiles("zellige", "grid", 8, 8, 0.8, var=26, glaze=(18, 60), base=205, grout=165, strength=3.0)
    tiles("subway", "brick", 6, 12, 0.9, var=7, glaze=(28, 48), base=222, grout=170, seed=2)
    tiles("hex_tile", "hex", 8, 8, 0.8, var=8, glaze=(55, 90), base=222, grout=150, seed=3)
    tiles("terracotta_tile", "grid", 4, 4, 0.8, var=30, glaze=(120, 175), base=190, grout=135, seed=4, strength=2.6)
    tiles("square_tile", "grid", 3, 3, 1.8, var=8, glaze=(60, 95), base=212, grout=165, seed=5)
    carrara(); art(); menus()
    # honest real-world scale for the original set (terrazzo chips were rendering 3x too big)
    for n, s in (("terrazzo", 0.42), ("plaster", 2.0), ("oak", 2.0), ("wood", 1.5), ("marble", 1.2), ("concrete", 2.0), ("fabric", 0.4), ("checker", 0.6)):
        p = os.path.join(OUT, n, "meta.json")
        if not os.path.isfile(p):
            json.dump({"id": "ambientcg", "license": "CC0", "size_m": [s, s]}, open(p, "w"))
