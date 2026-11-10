"""gen_client_textures.py — Coffee Berry finish textures from the client's own references
(clientsDocs/7. Photo references + CB Leo ΥΛΙΚΑ schedule). Writes public/textures/<name>/{color,normal,rough}.jpg + meta.json
at true tile size, with rectified grout joints.  python3 blender/gen_client_textures.py"""
import json, os
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "client_src")
OUT = os.path.join(HERE, "..", "public", "textures")
N = 1024


def crop(img, box_frac):
    w, h = img.size
    x0, y0, x1, y1 = box_frac
    return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def tiled(src, field_m, tile_wh_m, grout="#8d8a84", grout_px=2, jitter=True):
    """Fill a square field_m×field_m texture with tiles of size tile_wh_m, each a different crop of src."""
    img = Image.open(src).convert("RGB")
    out = Image.new("RGB", (N, N))
    px = N / field_m
    tw, th = tile_wh_m
    nx, ny = round(field_m / tw), round(field_m / th)
    k = 0
    for j in range(ny):
        for i in range(nx):
            fw, fh = min(1.0, tw / max(tw, th)), min(1.0, th / max(tw, th))
            ox, oy = ((k * 0.37) % (1 - fw * 0.6)) * 0.5, ((k * 0.61) % (1 - fh * 0.6)) * 0.5
            c = crop(img, (ox, oy, min(1, ox + fw * 0.6 + 0.4), min(1, oy + fh * 0.6 + 0.4)))
            if jitter and k % 2:
                c = ImageOps.mirror(c)
            c = c.resize((int(round(tw * px)), int(round(th * px))), Image.LANCZOS)
            c = ImageEnhance.Brightness(c).enhance(1.0 + ((k * 7) % 5 - 2) * 0.012)
            out.paste(c, (int(round(i * tw * px)), int(round(j * th * px))))
            k += 1
    d = ImageDraw.Draw(out)
    for i in range(nx + 1):
        x = int(round(i * tw * px)) % N
        d.rectangle([x - grout_px // 2, 0, x + grout_px - grout_px // 2 - 1, N], fill=grout)
    for j in range(ny + 1):
        y = int(round(j * th * px)) % N
        d.rectangle([0, y - grout_px // 2, N, y + grout_px - grout_px // 2 - 1], fill=grout)
    return out


def single(src, box=(0, 0, 1, 1)):
    return crop(Image.open(src).convert("RGB"), box).resize((N, N), Image.LANCZOS)


def write(name, color, size_m, rough_base=0.75, rough_var=0.25, bump=1.5, src_id=""):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    color.save(os.path.join(d, "color.jpg"), quality=90)
    g = ImageOps.grayscale(color)
    lo, hi = g.getextrema()
    r = g.point(lambda v: int(255 * min(1, max(0, rough_base + rough_var * ((v - lo) / max(1, hi - lo) - 0.5)))))
    r.save(os.path.join(d, "rough.jpg"), quality=90)
    # normal from luminance gradient (subtle stone relief, sunk grout)
    h = g.filter(ImageFilter.GaussianBlur(1.2))
    W, H = h.size
    p = h.load()
    nimg = Image.new("RGB", (W, H))
    q = nimg.load()
    for y in range(H):
        for x in range(W):
            dx = (p[(x + 1) % W, y] - p[(x - 1) % W, y]) / 255 * bump
            dy = (p[x, (y + 1) % H] - p[x, (y - 1) % H]) / 255 * bump
            nx_, ny_, nz = -dx, dy, 1.0
            l = (nx_ * nx_ + ny_ * ny_ + nz * nz) ** 0.5
            q[x, y] = (int((nx_ / l * 0.5 + 0.5) * 255), int((ny_ / l * 0.5 + 0.5) * 255), int((nz / l * 0.5 + 0.5) * 255))
    nimg.save(os.path.join(d, "normal.jpg"), quality=90)
    json.dump({"id": src_id, "license": "client reference", "size_m": [size_m, size_m]}, open(os.path.join(d, "meta.json"), "w"))
    print("wrote", name)


# Bar: COEM Sassiepietre Grigio 90.6×90.6 rectified
write("cb_sassiepietre", tiled(os.path.join(SRC, "sassiepietre_grigio.jpg"), 1.812, (0.906, 0.906), grout="#77746e"), 1.812, 0.7, 0.2, src_id="client:COEM Sassiepietre Grigio 90.6x90.6")
# Main floor + WC floor/walls: Soulant gris mat 60×120
write("cb_soulant", tiled(os.path.join(SRC, "soulant_gris.jpg"), 2.4, (0.6, 1.2), grout="#6f716e"), 2.4, 0.72, 0.15, bump=1.0, src_id="client:Soulant gris mat 60x120")
# Prep room (Lab): Ariman grey mat R10 30×60 — darker, finer
ar = ImageEnhance.Brightness(Image.open(os.path.join(SRC, "soulant_gris.jpg")).convert("RGB")).enhance(0.82)
ar.save(os.path.join(SRC, "_ariman_tmp.jpg"))
write("cb_ariman", tiled(os.path.join(SRC, "_ariman_tmp.jpg"), 1.2, (0.3, 0.6), grout="#5d5e5b"), 1.2, 0.85, 0.1, bump=1.0, src_id="client:Ariman grey mat R10 30x60")
os.remove(os.path.join(SRC, "_ariman_tmp.jpg"))
# Table tops: HPL Milazza matt (terrazzo-look)
write("cb_milazza", single(os.path.join(SRC, "milazza.jpg"), (0, 0.1, 1, 0.1 + 768 / 1229)), 0.6, 0.6, 0.15, src_id="client:HPL Millaza matt")

# Bar kick plinth (μπάζα πάγκου, recessed): COEM Sassiepietre Grigio SCURO 90.6×90.6 — swatch from the COEM catalogue p.A-11
write("cb_sassiepietre_scuro", tiled(os.path.join(SRC, "sassiepietre_grigio_scuro.jpg"), 1.812, (0.906, 0.906), grout="#4a4743"), 1.812, 0.7, 0.2, src_id="client:COEM Sassiepietre Grigio Scuro 90.6x90.6")

