"""Render a 1080x1920 "Top 10 finds under $20" reel from the RepsRB Finds photo sheets.

Usage: python3 make_top10_reel.py SHEETS_DIR OUT.mp4
SHEETS_DIR holds the gallery sheets published with the finds page (img/g/NNN.jpg):
4 products per sheet, one row each, up to 6 photos of 520x650 per row.
Needs Pillow and ffmpeg.
"""
import json, math, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BG, INK, MUTED, ACCENT = (16, 16, 15), (250, 249, 245), (170, 168, 160), (212, 255, 58)
CNY_TO_USD = 0.14  # same rate as index.html
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# Countdown order, #10 first. (product index in PRODUCTS, gallery photo slots to show)
PICKS = [
    (37, [0, 2, 5]),    # Cross Patch Ribbed Knit Beanie
    (47, [0, 1, 4]),    # Mirrored Shield Sport Sunglasses
    (156, [0, 2, 4]),   # Washed Graphic Print Heavyweight Tee
    (274, [0, 2, 4]),   # Retro Mesh Basketball Shorts
    (332, [0, 1, 4]),   # Marbled Foam Runner Clogs
    (261, [0, 3, 4]),   # Padded Sports Backpack
    (310, [0, 5, 4]),   # Retro Panel Nylon Track Jacket
    (1213, [0, 3, 5]),  # Logo Hood Fleece Hoodie
    (599, [0, 1, 3]),   # Black Straight Leg Denim Jeans
    (712, [0, 1, 4]),   # Quarter Zip Knit Pullover
]
INTRO, ITEM, OUTRO = 2.2, 2.6, 2.6

def font(path, size): return ImageFont.truetype(path, size)

def load_products():
    src = (Path(__file__).resolve().parent.parent / "index.html").read_text()
    body = src[src.index("const PRODUCTS = [") + len("const PRODUCTS = "):]
    body = body[:body.index("\n];") + 2]
    return json.loads(re.sub(r",\s*\]$", "]", body))

def photo(sheets, idx, slot):
    sheet = Image.open(f"{sheets}/img/g/{idx // 4:03d}.jpg").convert("RGB")
    r = idx % 4
    cell = sheet.crop((slot * 520, r * 650, slot * 520 + 520, r * 650 + 650))
    # trim the dark letterbox the sheet builder pads each photo with
    bbox = Image.eval(cell.convert("L"), lambda v: 255 if v > 30 else 0).getbbox() or (0, 0, 520, 650)
    return cell.crop(bbox)

def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def back(t):  # ease-out with a little overshoot, for pops
    t = max(0.0, min(1.0, t)); c = 1.7; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

def center_text(d, y, text, f, fill, anchor="ma"):
    d.text((W // 2, y), text, font=f, fill=fill, anchor=anchor)

def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur]

def card(img, w, h, zoom):
    """Photo on a white rounded card, cover-fit with a slow zoom."""
    s = max(w / img.width, h / img.height) * zoom
    im = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    im = im.crop((x, y, x + w, y + h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), 36, fill=255)
    return im, mask

def item_frame(n, p, photos, t, total):
    f = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(f)
    # progress bar
    d.rectangle((0, 0, W, 10), fill=(40, 40, 38))
    d.rectangle((0, 0, int(W * (10 - n + min(t / ITEM, 1)) / 10), 10), fill=ACCENT)
    # rank slides in from the left
    k = ease(t / 0.35)
    d.text((70 - int((1 - k) * 300), 70), f"#{n}", font=font(BOLD, 190), fill=ACCENT)
    cat = p["category"].upper()
    d.text((W - 70, 120), cat, font=font(BOLD, 40), fill=MUTED, anchor="ra")
    # photo card: cross-fade through the listing photos
    cw, ch, cy = 900, 1050, 300
    seg = ITEM / len(photos)
    i = min(int(t / seg), len(photos) - 1)
    zoom = 1.0 + 0.06 * (t / ITEM)
    im, mask = card(photos[i], cw, ch, zoom)
    fade = (t - i * seg) / 0.18
    if i > 0 and fade < 1:
        prev, _ = card(photos[i - 1], cw, ch, zoom)
        im = Image.blend(prev, im, max(0.0, fade))
    rise = int((1 - ease(t / 0.4)) * 120)
    f.paste(im, ((W - cw) // 2, cy + rise), mask)
    # name
    nf = font(BOLD, 64)
    y = 1400
    for line in wrap(d, p["name"], nf, 940)[:2]:
        center_text(d, y, line, nf, INK); y += 76
    # price pill pops in
    usd = p["priceCNY"] * CNY_TO_USD
    s = back((t - 0.35) / 0.35)
    if s > 0:
        pf = font(BOLD, int(96 * s) or 1)
        txt = f"${usd:.2f}"
        tw = d.textlength(txt, font=pf)
        ph = int(130 * s)
        py = 1600 + (130 - ph) // 2
        d.rounded_rectangle((W // 2 - tw / 2 - 44 * s, py, W // 2 + tw / 2 + 44 * s, py + ph), ph // 2, fill=ACCENT)
        d.text((W // 2, py + ph // 2), txt, font=pf, fill=BG, anchor="mm")
        if s >= 0.98:
            center_text(d, 1760, f"¥{p['priceCNY']:g} on Weidian", font(REG, 40), MUTED)
    return f

def intro_frame(t, thumbs):
    f = Image.new("RGB", (W, H), BG)
    # drifting grid of the ten finds, dimmed
    tw, th = 360, 450
    off = int(t * 60)
    for k in range(15):
        c, r = k % 3, k // 3
        x, y = c * tw, r * th - 120 - off + (c % 2) * 120
        f.paste(thumbs[k % 10].resize((tw - 12, th - 12)), (x + 6, y + 6))
    f = Image.blend(f, Image.new("RGB", (W, H), BG), 0.72)
    d = ImageDraw.Draw(f)
    a, b, c = back(t / 0.4), back((t - 0.25) / 0.4), ease((t - 0.6) / 0.4)
    if a > 0: center_text(d, 760, "TOP 10", font(BOLD, max(1, int(250 * a))), ACCENT, "mm")
    if b > 0: center_text(d, 960, "FINDS UNDER", font(BOLD, max(1, int(110 * b))), INK, "mm")
    if b > 0: center_text(d, 1110, "$20", font(BOLD, max(1, int(190 * b))), INK, "mm")
    if c > 0:
        center_text(d, 1290, "Kakobuy · Weidian", font(REG, 52),
                    tuple(int(BG[j] + (MUTED[j] - BG[j]) * c) for j in range(3)), "mm")
    return f

def outro_frame(t, thumbs):
    f = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(f)
    # all ten as a 5x2 recap strip
    tw, th = 196, 245
    for k in range(10):
        s = ease((t - k * 0.05) / 0.3)
        if s <= 0: continue
        x = 25 + (k % 5) * (tw + 10)
        y = 420 + (k // 5) * (th + 10) + int((1 - s) * 80)
        f.paste(thumbs[k].resize((tw, th)), (x, y))
    a = back((t - 0.5) / 0.4)
    if a > 0:
        center_text(d, 1150, "SAVE THIS", font(BOLD, max(1, int(150 * a))), ACCENT, "mm")
        center_text(d, 1290, "for your next haul", font(BOLD, max(1, int(64 * a))), INK, "mm")
    if t > 1.0:
        center_text(d, 1480, "All 10 links in bio", font(REG, 56), MUTED, "mm")
    return f

def main(sheets, out):
    P = load_products()
    items = [(P[i], [photo(sheets, i, s) for s in slots]) for i, slots in PICKS]
    for p, _ in items: assert p["priceCNY"] * CNY_TO_USD < 20, p["name"]
    thumbs = [card(ph[0], 360, 450, 1.0)[0] for _, ph in items]
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    def emit(img): ff.stdin.write(img.tobytes())
    for fr in range(int(INTRO * FPS)): emit(intro_frame(fr / FPS, thumbs))
    for k, (p, ph) in enumerate(items):
        for fr in range(int(ITEM * FPS)): emit(item_frame(10 - k, p, ph, fr / FPS, ITEM))
    for fr in range(int(OUTRO * FPS)): emit(outro_frame(fr / FPS, thumbs))
    ff.stdin.close(); sys.exit(ff.wait())

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
