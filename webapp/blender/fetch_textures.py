#!/usr/bin/env python3
"""
fetch_textures.py — download the curated CC0 Poly Haven PBR set into public/textures/<name>/.

    python3 blender/fetch_textures.py

Each folder gets color.jpg / rough.jpg / normal.jpg (1k, OpenGL normals) plus meta.json holding the
texture's REAL-WORLD size from Poly Haven, so cafe_kit tiles every material at true scale.
Already-downloaded folders are skipped. Plain Python + Pillow; no Blender needed.
"""
import io
import json
import os
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "public", "textures"))
UA = {"User-Agent": "cafevision-asset-fetch/1.0"}

# kit name -> Poly Haven id
SET = {
    # timber
    "parquet_herringbone": "herringbone_parquet", "oak_light": "oak_veneer_01", "oak_grey": "grey_oak_veneer_01",
    "veneer_a": "american_walnut_veneer", "veneer_b": "black_walnut_veneer_01", "ash": "ash_veneer",
    "veneer_c": "flamed_black_veneer", "hinoki": "hinoki_planks", "cedar": "japanese_cedar_planks",
    "old_boards": "old_wood_floor",
    # masonry
    "brick_red": "brick_wall_001", "brick_white": "castle_brick_02_white", "brick_dark": "dark_brick_wall",
    "brick_herringbone": "herringbone_brick",
    # plaster / concrete
    "clay_plaster": "clay_plaster", "beige_plaster": "beige_wall_001", 
    "concrete_brushed": "brushed_concrete", "concrete_ribbed": "ribbed_concrete_wall", 
    # stone / tile
    "limestone_tile": "marble_01", "marble_tile": "marble_tiles", "marble_mosaic": "marble_mosaic_tiles",
    "tile_interior": "interior_tiles", "tile_patterned": "floor_tiles_06",
    "slate": "slate_floor", "granite_tile": "granite_tile",
    # outdoor ground
    "paving": "concrete_pavers", "paving_herringbone": "herringbone_pavement", "cobble": "cobblestone_floor_02",
    # textiles
    "linen": "rough_linen", "velvet": "velour_velvet", "boucle_teddy": "curly_teddy_natural", "leather_brown": "brown_leather",
    "leather_white": "leather_white", "tatami": "tatami_mat", "hessian": "hessian_230", "corduroy": "ribbed_corduroy",
}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def jpg(url, dest):
    Image.open(io.BytesIO(get(url))).convert("RGB").save(dest, "JPEG", quality=85)


def main():
    done = 0
    for name, pid in SET.items():
        d = os.path.join(OUT, name)
        if os.path.isfile(os.path.join(d, "meta.json")):
            continue
        try:
            files = json.loads(get(f"https://api.polyhaven.com/files/{pid}"))
            info = json.loads(get(f"https://api.polyhaven.com/info/{pid}"))
            os.makedirs(d, exist_ok=True)
            jpg(files["Diffuse"]["1k"]["jpg"]["url"], os.path.join(d, "color.jpg"))
            jpg(files["Rough"]["1k"]["jpg"]["url"], os.path.join(d, "rough.jpg"))
            jpg(files["nor_gl"]["1k"]["jpg"]["url"], os.path.join(d, "normal.jpg"))
            dims = info.get("dimensions") or [2000, 2000]
            meta = {"id": pid, "license": "CC0", "source": f"https://polyhaven.com/a/{pid}", "size_m": [dims[0] / 1000.0, dims[1] / 1000.0]}
            json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=1)
            done += 1
            print("ok", name, pid, meta["size_m"])
        except Exception as e:  # noqa: BLE001
            print("FAILED", name, pid, repr(e))
    print(f"fetched {done}")


if __name__ == "__main__":
    main()
