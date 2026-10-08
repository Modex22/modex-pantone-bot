import csv, math
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

def load_palette(path):
    palette = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rgb = (int(row["r"]), int(row["g"]), int(row["b"]))
                palette.append({
                    "name": row["name"],
                    "r": rgb[0], "g": rgb[1], "b": rgb[2],
                    "rgb": rgb,
                    "description": row.get("description", ""),
                    "collection": row.get("collection", "")
                })
            except Exception:
                continue
    return palette

def hex_to_rgb(value):
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)

def rgb_to_lab(rgb):
    # sRGB D65 -> CIE Lab
    vals = []
    for v in rgb:
        v /= 255
        vals.append(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92)
    r, g, b = vals
    x = (r*0.4124 + g*0.3576 + b*0.1805) / 0.95047
    y = (r*0.2126 + g*0.7152 + b*0.0722)
    z = (r*0.0193 + g*0.1192 + b*0.9505) / 1.08883
    def f(t):
        return t ** (1/3) if t > 0.008856 else (7.787*t) + 16/116
    x, y, z = f(x), f(y), f(z)
    return (116*y-16, 500*(x-y), 200*(y-z))

def lab_distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a,b)))

def nearest_matches(rgb, palette, collection=None, limit=3):
    target = rgb_to_lab(rgb)
    candidates = [
        p for p in palette
        if not collection or p.get("collection","").upper() == collection.upper()
    ]
    scored = []
    for p in candidates:
        d = lab_distance(target, rgb_to_lab(p["rgb"]))
        item = dict(p)
        item["distance"] = d
        scored.append(item)
    scored.sort(key=lambda x: x["distance"])
    return scored[:limit]

def extract_dominant_colors(img, count=4):
    img = img.copy()
    img.thumbnail((250, 250))
    # Quantize gives a compact approximation of dominant visible colors.
    q = img.quantize(colors=max(8, count*3))
    pal = q.getpalette()
    counts = q.getcolors()
    counts.sort(reverse=True)
    result = []
    for n, idx in counts:
        rgb = tuple(pal[idx*3:idx*3+3])
        # Avoid nearly identical colors.
        if all(sum((rgb[i]-x[i])**2 for i in range(3)) > 900 for x in result):
            result.append(rgb)
        if len(result) >= count:
            break
    return result

def _font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

def make_color_tile(rgb, match, width=900, height=500):
    img = Image.new("RGB", (width, height), rgb)
    d = ImageDraw.Draw(img)
    text_color = (255,255,255) if sum(rgb) < 420 else (15,15,15)
    d.rectangle((0, height-150, width, height), fill=(255,255,255) if text_color==(15,15,15) else (15,15,15))
    d.text((35, height-125), match["name"], fill=text_color if text_color==(255,255,255) else (15,15,15), font=_font(38))
    d.text((35, height-75), rgb_to_hex(rgb), fill=text_color if text_color==(255,255,255) else (15,15,15), font=_font(28))
    return img

def make_color_card(matches, width=1200, tile_w=260, tile_h=360):
    cols = max(1, min(4, len(matches)))
    rows = math.ceil(len(matches)/cols)
    img = Image.new("RGB", (width, rows*tile_h+130), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 35), "MODEX COLOR CARD", fill=(20,20,20), font=_font(48))
    for i, (rgb, m) in enumerate(matches):
        x = 40 + (i % cols) * tile_w
        y = 110 + (i // cols) * tile_h
        d.rectangle((x, y, x+tile_w-30, y+200), fill=rgb)
        d.text((x, y+215), m["name"], fill=(20,20,20), font=_font(23))
        d.text((x, y+250), rgb_to_hex(rgb), fill=(80,80,80), font=_font(20))
        d.text((x, y+280), f"ΔE {m['distance']:.1f}", fill=(80,80,80), font=_font(18))
    return img
