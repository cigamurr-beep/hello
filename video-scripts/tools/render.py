#!/usr/bin/env python3
"""Render the silent Kakobuy vs LitBuy comparison video (EN or SR).

usage: render.py <en|sr> <out.mp4> [--preview t1,t2,...]
"""
import math, os, random, subprocess, sys
from functools import lru_cache
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
W, H, FPS = 1080, 1920, 30
CX = 520  # content centre, nudged left of TikTok's right-side buttons
MAXW = 920
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

RED = (255, 59, 59)
GREEN = (46, 230, 120)
GOLD = (255, 200, 40)
WHITE = (255, 255, 255)
GREY = (150, 150, 160)
DARK = (11, 11, 16)

# ---------------------------------------------------------------- copy ----
TEXT = {
    "en": dict(
        hook_top="SAME 2 KG PARCEL TO SERBIA",
        kako="KAKOBUY", lit="LITBUY",
        hook_foot="*with the 40% sign-up coupon · link in bio",
        who="WHO'S CHEAPER?",
        r1="ROUND 1: SHIPPING", r1_sub="2 kg → Serbia",
        cheapest="cheapest line",
        no_coupon="EVEN WITHOUT A COUPON",
        bonus="BONUS",
        signup="SIGN UP WITH THE LINK IN MY BIO",
        minus40="= −40% SHIPPING",
        bonus_foot="*$24.94 only with the sign-up coupon (link in bio)",
        cheaper="CHEAPER", than_kako="THAN KAKOBUY",
        half="BASICALLY HALF PRICE",
        r2="ROUND 2: COUPONS",
        kako_c1="10% shipping subsidy", kako_c2="(11.11 sale)",
        lit_c1="−40% sign-up coupon", lit_c2="+ −25% with Discord",
        wins="LITBUY WINS",
        score="FINAL SCORE",
        s1="Cheaper with no coupon", s2="−40% shipping with my link",
        s3="$24.94 vs $50.63*", s4="Better coupons",
        link="LINK IN BIO",
        cta1a="SIGN UP", cta1b="−40% SHIPPING",
        cta2a="SHEET IN BIO", cta2b="HUGE SELECTION OF ITEMS",
        disclose="affiliate link · prices checked 3 Nov 2026",
        stamp="2 kg to Serbia · prices checked 3 Nov 2026",
        dec=".",
    ),
    "sr": dict(
        hook_top="ISTI PAKET OD 2 KG DO SRBIJE",
        kako="KAKOBUY", lit="LITBUY",
        hook_foot="*uz kupon od 40% za registraciju · link u biou",
        who="KO JE JEFTINIJI?",
        r1="RUNDA 1: DOSTAVA", r1_sub="2 kg → Srbija",
        cheapest="najjeftinija linija",
        no_coupon="I TO BEZ KUPONA",
        bonus="BONUS",
        signup="REGISTRUJ SE PREKO LINKA U BIOU",
        minus40="= −40% NA DOSTAVU",
        bonus_foot="*$24,94 samo uz kupon za registraciju (link u biou)",
        cheaper="JEFTINIJE", than_kako="OD KAKOBUY-A",
        half="PRAKTIČNO POLA CENE",
        r2="RUNDA 2: KUPONI",
        kako_c1="10% subvencija za dostavu", kako_c2="(11.11 akcija)",
        lit_c1="−40% kupon za registraciju", lit_c2="+ −25% preko Discorda",
        wins="LITBUY POBEĐUJE",
        score="KONAČAN REZULTAT",
        s1="Jeftinije i bez kupona", s2="−40% na dostavu preko mog linka",
        s3="$24,94 vs $50,63*", s4="Bolji kuponi",
        link="LINK U BIOU",
        cta1a="REGISTRUJ SE", cta1b="−40% NA DOSTAVU",
        cta2a="SHEET U BIOU", cta2b="BRDO STVARI",
        disclose="affiliate link · cene proverene 03.11.2026.",
        stamp="2 kg do Srbije · cene proverene 03.11.2026.",
        dec=",",
    ),
}
L = None  # set per language


def money(v):
    return "$" + f"{v:.2f}".replace(".", L["dec"])


# -------------------------------------------------------------- easing ----
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


def out_cubic(x):
    return 1 - (1 - x) ** 3


def out_back(x, s=2.2):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def in_out(x):
    return 3 * x * x - 2 * x * x * x


def lerp(a, b, x):
    return a + (b - a) * x


# ------------------------------------------------------------- drawing ----
@lru_cache(maxsize=512)
def font(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=512)
def text_img(s, size, fill=WHITE, path=FONT_BLACK, stroke=None, maxw=MAXW,
             stroke_fill=(0, 0, 0)):
    """RGBA image of text with a black outline, shrunk to fit maxw."""
    while True:
        f = font(path, size)
        sw = max(2, int(size * 0.09)) if stroke is None else stroke
        l, t, r, b = f.getbbox(s, stroke_width=sw)
        if r - l <= maxw or size <= 14:
            break
        size = int(size * 0.94)
    pad = sw + 4
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad - l, pad - t), s, font=f, fill=fill + (255,), stroke_width=sw,
           stroke_fill=stroke_fill + (255,))
    return im


def put(c, layer, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if alpha <= 0.003 or scale <= 0.01:
        return
    im = layer
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.BILINEAR)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    c.alpha_composite(im, (x, y)) if 0 <= x and 0 <= y and x + im.width <= W and y + im.height <= H \
        else _paste_clipped(c, im, x, y)


def _paste_clipped(c, im, x, y):
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, W - x), min(im.height, H - y)
    if r <= l or b <= t:
        return
    c.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


def txt(c, s, cx, cy, size, fill=WHITE, scale=1.0, alpha=1.0, angle=0.0,
        path=FONT_BLACK, maxw=MAXW, stroke=None):
    put(c, text_img(s, size, fill, path, stroke, maxw), cx, cy, scale, alpha, angle)


def pop(t, start, dur=0.35):
    """(scale, alpha) for a pop-in that starts at `start`."""
    p = prog(t, start, dur)
    if p <= 0:
        return 0.0, 0.0
    return out_back(p), clamp(p * 3)


@lru_cache(maxsize=64)
def pill_img(s, size, bg, fg=WHITE, padx=40, pady=22, path=FONT_BLACK, stroke=0, maxw=MAXW):
    t = text_img(s, size, fg, path, stroke, maxw - 2 * padx)
    w, h = t.width + 2 * padx, t.height + 2 * pady
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg + (255,))
    im.alpha_composite(t, (padx, pady))
    return im


@lru_cache(maxsize=64)
def rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    return m


@lru_cache(maxsize=64)
def shadow(w, h, r, blur=30, a=170):
    pad = blur * 2
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), radius=r,
                                         fill=(0, 0, 0, a))
    return im.filter(ImageFilter.GaussianBlur(blur))


def card(c, img, cx, cy, radius=34, border=None, alpha=1.0, scale=1.0):
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         Image.BILINEAR)
    w, h = img.size
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im.paste(img.convert("RGB"), (0, 0), rounded_mask(w, h, radius))
    if border:
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                                             outline=border + (255,), width=6)
    put(c, shadow(w, h, radius), cx, cy + 14, alpha=alpha)
    put(c, im, cx, cy, alpha=alpha)
    return (cx - w / 2, cy - h / 2, w, h)


@lru_cache(maxsize=8)
def bg_grad(tint):
    top, bot = DARK, tuple(int(DARK[i] * 0.5 + tint[i] * 0.22) for i in range(3))
    g = Image.new("RGBA", (1, H))
    for y in range(H):
        k = y / H
        g.putpixel((0, y), tuple(int(lerp(top[i], bot[i], k)) for i in range(3)) + (255,))
    return g.resize((W, H))


def background(tint=(80, 80, 120)):
    return bg_grad(tint).copy()



class Dr:
    """ImageDraw proxy that alpha-blends translucent shapes onto an RGBA canvas."""
    def __init__(self, c):
        self.c = c

    def __getattr__(self, name):
        def f(*a, **k):
            o = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            getattr(ImageDraw.Draw(o), name)(*a, **k)
            self.c.alpha_composite(o)
        return f


def flash(c, color, a):
    if a > 0:
        c.alpha_composite(Image.new("RGBA", (W, H), color + (int(255 * clamp(a)),)))


def check(c, cx, cy, r, color=GREEN, s=1.0, alpha=1.0):
    if s <= 0:
        return
    r = r * s
    lay = Image.new("RGBA", (int(2 * r + 4), int(2 * r + 4)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse((2, 2, 2 * r + 2, 2 * r + 2), fill=color + (255,))
    k = r / 30
    pts = [(2 + r - 14 * k, 2 + r + 1 * k), (2 + r - 4 * k, 2 + r + 11 * k),
           (2 + r + 15 * k, 2 + r - 10 * k)]
    d.line(pts, fill=(0, 0, 0, 255), width=max(3, int(7 * k)), joint="curve")
    put(c, lay, cx, cy, alpha=alpha)


def arrow_up(c, cx, cy, size, color=GOLD):
    d = Dr(c)
    s = size
    d.polygon([(cx, cy - s), (cx - s * 0.8, cy), (cx - s * 0.3, cy), (cx - s * 0.3, cy + s),
               (cx + s * 0.3, cy + s), (cx + s * 0.3, cy), (cx + s * 0.8, cy)],
              fill=color + (255,), outline=(0, 0, 0, 255), width=5)


def confetti(c, t, t0, cx, cy, n=140, seed=7):
    dt = t - t0
    if dt < 0 or dt > 2.2:
        return
    rnd = random.Random(seed)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cols = [GREEN, GOLD, WHITE, (90, 200, 255)]
    fade = clamp(1 - (dt - 1.4) / 0.8)
    for _ in range(n):
        ang = rnd.uniform(0, 2 * math.pi)
        sp = rnd.uniform(500, 1500)
        vx, vy = math.cos(ang) * sp, math.sin(ang) * sp - 600
        x = cx + vx * dt
        y = cy + vy * dt + 0.5 * 2200 * dt * dt
        sz = rnd.uniform(9, 20)
        col = rnd.choice(cols)
        rot = rnd.uniform(0, 6.28) + dt * rnd.uniform(-8, 8)
        dx, dy = math.cos(rot) * sz, math.sin(rot) * sz * 0.5
        d.polygon([(x - dx, y - dy), (x + dy, y - dx * 0.3), (x + dx, y + dy), (x - dy, y + dx * 0.3)],
                  fill=col + (int(255 * fade),))
    c.alpha_composite(ov)


def zoom_frame(c, s, dx=0, dy=0):
    if abs(s - 1) < 1e-3 and dx == 0 and dy == 0:
        return c
    w, h = W / s, H / s
    x0, y0 = (W - w) / 2 - dx / s, (H - h) / 2 - dy / s
    return c.transform((W, H), Image.EXTENT, (x0, y0, x0 + w, y0 + h), Image.BILINEAR)


def shake(t, t0, dur=0.25, amp=22, seed=1):
    p = prog(t, t0, dur)
    if p <= 0 or p >= 1:
        return 0, 0
    rnd = random.Random(seed * 1000 + int(t * FPS))
    a = amp * (1 - p)
    return rnd.uniform(-a, a), rnd.uniform(-a, a)


def punch(t, t0, amt=0.12, dur=0.3):
    p = prog(t, t0, dur)
    if p <= 0 or p >= 1:
        return 1.0
    return 1 + amt * (1 - out_cubic(p))


# ------------------------------------------------------------- sources ----
@lru_cache(maxsize=1)
def stills():
    lit = Image.open(os.path.join(SRC, "lit_freeze.jpg")).convert("RGB")
    lit0 = Image.open(os.path.join(SRC, "lit_t0.jpg")).convert("RGB")
    kako = Image.open(os.path.join(SRC, "kako_t0.jpg")).convert("RGB")
    return dict(
        lit=lit, kako=kako,
        lit_banner=lit0.crop((0, 143, 1170, 327)),
        kako_banner=kako.crop((0, 140, 1170, 300)),
        blur_kako=kako.crop((0, 300, 1170, 2300)).resize((540, 923)).filter(ImageFilter.GaussianBlur(14)),
        blur_lit=lit.crop((0, 345, 1170, 2345)).resize((540, 923)).filter(ImageFilter.GaussianBlur(14)),
    )


@lru_cache(maxsize=8)
def lit_seq(i):
    i = max(1, min(78, i))
    return Image.open(os.path.join(SRC, "litseq", f"{i:03d}.jpg")).convert("RGB")


def view(img, rect, box_w):
    """Crop rect (x0,y0,x1,y1) from img, scaled to box_w wide."""
    x0, y0, x1, y1 = rect
    bw = int(box_w)
    bh = int(box_w * (y1 - y0) / (x1 - x0))
    return img.transform((bw, bh), Image.EXTENT, rect, Image.BILINEAR)


def lerp_rect(a, b, x):
    return tuple(lerp(a[i], b[i], x) for i in range(4))


def map_pt(rect, box, px, py):
    x0, y0, x1, y1 = rect
    bx, by, bw, bh = box
    return bx + (px - x0) / (x1 - x0) * bw, by + (py - y0) / (y1 - y0) * bh


def highlight(c, rect, box, src_box, t, t0, color=GOLD):
    p = prog(t, t0, 0.3)
    if p <= 0:
        return
    (ax, ay), (bx, by) = map_pt(rect, box, src_box[0], src_box[1]), map_pt(rect, box, src_box[2], src_box[3])
    s = 1 + 0.25 * (1 - out_back(p))
    pulse = 1 + 0.03 * math.sin((t - t0) * 9)
    mx, my = (ax + bx) / 2, (ay + by) / 2
    hw, hh = (bx - ax) / 2 * s * pulse + 16, (by - ay) / 2 * s * pulse + 12
    Dr(c).rounded_rectangle((mx - hw, my - hh, mx + hw, my + hh), radius=18,
                                        outline=color + (int(255 * clamp(p * 2)),), width=9)


def footer(c, s, y=1478, alpha=1.0):
    txt(c, s, CX, y, 30, (220, 220, 230), path=FONT_B, stroke=3, alpha=alpha)


# -------------------------------------------------------------- scenes ----
KAKO_PRICE, LIT_PRICE = 50.63, 41.57
LIT_COUPON = round(LIT_PRICE * 0.6, 2)           # 24.94
DIFF1 = round(KAKO_PRICE - LIT_PRICE, 2)          # 9.06
PCT1 = round(DIFF1 / KAKO_PRICE * 100)            # 18
DIFF2 = round(KAKO_PRICE - LIT_COUPON, 2)         # 25.69
PCT2 = round(DIFF2 / KAKO_PRICE * 100)            # 51

KAKO_FULL = (0, 300, 1170, 2250)
KAKO_ZOOM = (0, 640, 1170, 1560)
KAKO_HL = (180, 1125, 300, 1180)
LIT_FULL = (0, 0, 1170, 2075)          # coords inside the cropped sequence
LIT_FULL_ABS = (0, 345, 1170, 2420)    # same rect in the full-res still
LIT_ZOOM = (30, 960, 1140, 1740)
LIT_HL = (88, 1468, 300, 1535)


def s_hook(c, t, loop=False):
    st = stills()
    c.alpha_composite(st["blur_kako"].convert("RGBA").resize((540, 1920)), (0, 0))
    c.alpha_composite(st["blur_lit"].convert("RGBA").resize((540, 1920)), (540, 0))
    c.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 175)))
    d = Dr(c)
    d.rectangle((0, 0, 540, H), fill=RED + (38,))
    d.rectangle((540, 0, W, H), fill=GREEN + (30,))
    d.rectangle((536, 0, 544, H), fill=(255, 255, 255, 200))
    k = 99 if loop else t
    sc, a = pop(k, 0.0, 0.3)
    put(c, pill_img(L["hook_top"], 54, (0, 0, 0), maxw=980), CX, 330, sc, a)
    sc, a = pop(k, 0.25)
    txt(c, money(KAKO_PRICE), 270, 760, 150, RED, sc, a, maxw=500)
    txt(c, L["kako"], 270, 885, 60, WHITE, sc, a)
    sc2, a2 = pop(k, 0.8)
    txt(c, money(LIT_COUPON) + "*", 790, 760, 150, GREEN, sc2, a2, maxw=480)
    txt(c, L["lit"], 790, 885, 60, WHITE, sc2, a2)
    sc3, a3 = pop(k, 0.55, 0.3)
    txt(c, "VS", 540, 1060, 120, GOLD, sc3, a3, angle=-8)
    txt(c, L["hook_foot"], CX, 1250, 38, WHITE, alpha=prog(k, 1.0, 0.2), path=FONT_XB, stroke=4)


def s_title(c, t):
    c.alpha_composite(background((120, 40, 160)))
    p = out_cubic(prog(t, 0.0, 0.35))
    put(c, pill_img(L["kako"], 92, RED), lerp(-400, CX, p), 760, 1, 1, 6)
    put(c, pill_img(L["lit"], 92, (20, 170, 85)), lerp(W + 400, CX, p), 1010, 1, 1, -6)
    sc, a = pop(t, 0.35, 0.3)
    txt(c, "VS", CX, 885, 150, GOLD, sc, a)
    sc, a = pop(t, 0.7)
    txt(c, L["who"], CX, 1240, 76, WHITE, sc, a)


def round_header(c, t, title, sub=None, y=250):
    sc, a = pop(t, 0.0)
    put(c, pill_img(title, 64, GOLD, (0, 0, 0)), CX, y, sc, a)
    if sub:
        txt(c, sub, CX, y + 105, 50, WHITE, *pop(t, 0.2), path=FONT_XB, stroke=5)


def s_kako(c, t):
    c.alpha_composite(background(RED))
    round_header(c, t, L["r1"], L["r1_sub"])
    st = stills()
    z = in_out(prog(t, 0.6, 1.0))
    rect = lerp_rect(KAKO_FULL, KAKO_ZOOM, z)
    bw = lerp(560, 960, z)
    img = view(st["kako"], rect, bw)
    cy = lerp(910, 820, z)
    sc, a = pop(t, 0.1, 0.4)
    box = card(c, img, CX, cy, alpha=a, scale=lerp(0.85, 1, sc) if sc < 1 else 1)
    highlight(c, rect, box, KAKO_HL, t, 1.7)
    sc, a = pop(t, 2.1)
    put(c, pill_img(f"{L['kako']}: {money(KAKO_PRICE)}", 74, RED), CX, 1320, sc, a)
    txt(c, f"({L['cheapest']})", CX, 1420, 40, WHITE, *pop(t, 2.3), path=FONT_XB, stroke=4)
    footer(c, L["stamp"], 1490, prog(t, 0.5, 0.3))


def s_lit(c, t):
    c.alpha_composite(background(GREEN))
    round_header(c, t, L["r1"], L["r1_sub"])
    st = stills()
    if t < 2.6:
        img = lit_seq(int(t * FPS) + 1)
        rect = LIT_FULL
        box_img = view(img, rect, 560)
        sc, a = pop(t, 0.0, 0.35)
        card(c, box_img, CX, 910, alpha=a)
    else:
        z = in_out(prog(t, 2.7, 0.9))
        rect = lerp_rect(LIT_FULL_ABS, LIT_ZOOM, z)
        img = view(st["lit"], rect, lerp(560, 960, z))
        box = card(c, img, CX, lerp(910, 800, z))
        highlight(c, rect, box, LIT_HL, t, 3.6)
    sc, a = pop(t, 4.0)
    put(c, pill_img(f"{L['lit']}: {money(LIT_PRICE)}", 74, (20, 170, 85)), CX, 1320, sc, a)
    footer(c, L["stamp"], 1490, prog(t, 0.5, 0.3))


def split_bg(c, dim_left=0.0):
    c.alpha_composite(background((60, 60, 90)))
    d = Dr(c)
    d.rectangle((0, 0, 540, H), fill=RED + (int(55 * (1 - dim_left)),))
    d.rectangle((540, 0, W, H), fill=GREEN + (45,))
    d.rectangle((536, 360, 544, 1380), fill=(255, 255, 255, 160))


def s_compare(c, t):
    split_bg(c)
    txt(c, L["kako"], 270, 520, 64, WHITE, *pop(t, 0.0))
    txt(c, money(KAKO_PRICE), 270, 660, 130, RED, *pop(t, 0.15), maxw=500)
    txt(c, L["lit"], 800, 520, 64, WHITE, *pop(t, 0.35))
    txt(c, money(LIT_PRICE), 800, 660, 130, GREEN, *pop(t, 0.5), maxw=480)
    sc, a = pop(t, 1.0, 0.3)
    put(c, pill_img(f"−{money(DIFF1)}  (−{PCT1}%)", 96, (20, 170, 85)), CX, 930, sc * (1.25 - 0.25 * sc) if sc else 0, a, -4)
    txt(c, L["no_coupon"], CX, 1110, 72, GOLD, *pop(t, 1.5))
    footer(c, L["stamp"], 1490)


def s_bonus(c, t):
    c.alpha_composite(background((140, 110, 20)))
    st = stills()
    flash(c, GOLD, 0.85 * (1 - prog(t, 0.0, 0.35)))
    p = prog(t, 0.1, 0.45)
    y = lerp(-150, 250, out_back(p, 1.6)) if p > 0 else -300
    put(c, pill_img(L["bonus"], 110, GOLD, (0, 0, 0)), CX, y, angle=-3)
    sc, a = pop(t, 0.5, 0.35)
    card(c, st["lit_banner"].resize((940, int(940 * 184 / 1170))), CX, 500, radius=24,
         border=GOLD, alpha=a, scale=max(0.01, sc) if sc < 1 else 1)
    txt(c, L["signup"], CX, 690, 56, WHITE, *pop(t, 0.9))
    txt(c, L["minus40"], CX, 790, 80, GREEN, *pop(t, 1.2))
    # price-drop animation
    t0 = 2.5
    if t >= t0:
        land = t0 + 1.7
        if t < land:
            sc, a = pop(t, t0, 0.3)
            r = in_out(prog(t, t0 + 0.6, 1.1))
            v = lerp(LIT_PRICE, LIT_COUPON, r)
            jitter = 0 if r in (0, 1) else math.sin(t * 90) * 10
            col = WHITE if r == 0 else (255, 240, 200)
            txt(c, money(v), CX, 1080 + jitter, 190, col, sc, a, maxw=900)
            sp = prog(t, t0 + 0.3, 0.2)
            if sp > 0 and r < 0.15:
                lay = text_img(money(LIT_PRICE), 190, WHITE, FONT_BLACK, None, 900)
                hw = lay.width / 2
                Dr(c).line((CX - hw, 1110, CX - hw + 2 * hw * sp, 1050), fill=RED + (255,), width=22)
        else:
            sc = punch(t, land, 0.35, 0.35)
            txt(c, money(LIT_COUPON) + "*", CX, 1080, 190, GREEN, sc, maxw=900)
            txt(c, money(LIT_PRICE), CX - 150, 920, 70, GREY, alpha=prog(t, land, 0.2))
            Dr(c).line((CX - 320, 925, CX + 20, 915), fill=RED + (int(255 * prog(t, land, 0.2)),), width=10)
            sc2, a2 = pop(t, land + 0.1)
            ang = 12 + 6 * math.sin((t - land) * 6)
            put(c, pill_img("−40%", 78, RED), CX + 300, 930, sc2, a2, ang)
            confetti(c, t, land, CX, 1080)
        footer(c, L["bonus_foot"], 1300, prog(t, t0 + 1.7, 0.3))


def s_result(c, t):
    split_bg(c, dim_left=prog(t, 0.4, 0.4))
    st = 0.4
    gp = prog(t, st, 0.4)
    kc = tuple(int(lerp(RED[i], 120, gp)) for i in range(3))
    dx, dy = shake(t, st, 0.4, 18)
    txt(c, L["kako"], 270 + dx, 420, 60, WHITE)
    txt(c, money(KAKO_PRICE), 270 + dx, 540 + dy, 120, kc, maxw=500)
    if gp > 0.5:
        d = Dr(c)
        pts = [(150, 490), (215, 545), (190, 560), (265, 600), (240, 520), (330, 580), (395, 515)]
        d.line([(x + dx, y + dy) for x, y in pts], fill=(240, 240, 240, 140), width=4)
    glow = 1 + 0.04 * math.sin(t * 8)
    txt(c, L["lit"], 800, 420, 60, WHITE)
    txt(c, money(LIT_COUPON) + "*", 800, 540, 120, GREEN, glow, maxw=480)
    sc, a = pop(t, 0.9, 0.3)
    s = sc * (1.3 - 0.3 * sc) if sc else 0
    txt(c, money(DIFF2), CX, 820, 190, GREEN, s, a)
    txt(c, L["cheaper"], CX, 975, 110, WHITE, s, a)
    txt(c, L["than_kako"], CX, 1090, 80, WHITE, *pop(t, 1.2))
    put(c, pill_img(f"−{PCT2}%", 80, RED), CX, 1225, *pop(t, 1.5), -5)
    txt(c, L["half"], CX, 1350, 58, GOLD, *pop(t, 1.9))
    footer(c, L["hook_foot"], 1450)
    footer(c, L["stamp"], 1500)


def s_coupons(c, t):
    c.alpha_composite(background((150, 60, 200)))
    st = stills()
    round_header(c, t, L["r2"])
    dim = prog(t, 3.0, 0.4)
    sc, a = pop(t, 0.3)
    kb = st["kako_banner"].resize((900, int(900 * 160 / 1170)))
    if dim:
        kb = Image.blend(kb, ImageOps.grayscale(kb).convert("RGB"), dim)
    card(c, kb, CX, 500, radius=22, border=RED, alpha=a * (1 - 0.45 * dim))
    txt(c, L["kako_c1"], CX, 650, 52, WHITE, *pop(t, 0.6), path=FONT_XB, stroke=5)
    txt(c, L["kako_c2"], CX, 715, 40, (210, 210, 220), *pop(t, 0.7), path=FONT_XB, stroke=4)
    sc, a = pop(t, 1.4)
    card(c, st["lit_banner"].resize((900, int(900 * 184 / 1170))), CX, 900, radius=22,
         border=GREEN, alpha=a)
    txt(c, L["lit_c1"], CX, 1065, 58, GREEN, *pop(t, 1.7))
    txt(c, L["lit_c2"], CX, 1140, 52, GREEN, *pop(t, 2.0))
    sc, a = pop(t, 3.0, 0.3)
    s = sc * (1.4 - 0.4 * sc) if sc else 0
    put(c, pill_img(L["wins"], 92, (20, 170, 85)), CX, 1300, s, a, -6)


def s_score(c, t):
    c.alpha_composite(background((40, 120, 200)))
    txt(c, L["score"], CX, 250, 90, GOLD, *pop(t, 0.0))
    rows = [L["s1"], L["s2"], L["s3"], L["s4"]]
    subs = [f"{money(LIT_PRICE)} vs {money(KAKO_PRICE)} (−{PCT1}%)", None, f"(−{PCT2}%)", f"−40% + −25%"]
    y = 430
    for i, (r, sub) in enumerate(zip(rows, subs)):
        st = 0.35 + i * 0.45
        sc, a = pop(t, st, 0.3)
        if a <= 0:
            y += 175
            continue
        check(c, 110, y, 34, s=sc, alpha=a)
        lay = text_img(r, 54, WHITE, FONT_BLACK, None, 800)
        put(c, lay, 170 + lay.width / 2, y, alpha=a)
        if sub:
            sl = text_img(sub, 40, GREEN, FONT_XB, 4, 800)
            put(c, sl, 170 + sl.width / 2, y + 62, alpha=a)
        y += 175
    sc, a = pop(t, 2.5, 0.3)
    put(c, pill_img(f"{L['lit']} 2 – 0 {L['kako']}", 82, (20, 170, 85)), CX, 1210, sc, a)
    footer(c, L["hook_foot"], 1330, prog(t, 2.6, 0.3))


def s_cta(c, t):
    c.alpha_composite(background(GREEN))
    bob = math.sin(t * 7) * 18
    arrow_up(c, CX, 300 + bob, 75)
    txt(c, L["link"], CX, 470, 120, GOLD, *pop(t, 0.0))
    sc, a = pop(t, 0.5)
    put(c, pill_img(L["cta1a"], 56, (0, 0, 0), maxw=900), CX, 650, sc, a)
    put(c, pill_img(L["cta1b"], 84, (20, 170, 85), maxw=920), CX, 775, sc, a)
    sc, a = pop(t, 1.2)
    put(c, pill_img(L["cta2a"], 56, (0, 0, 0), maxw=900), CX, 960, sc, a)
    put(c, pill_img(L["cta2b"], 70, WHITE, (0, 0, 0), maxw=920), CX, 1080, sc, a)


# (scene fn, duration, entry punch-zoom amount)
SCENES = [
    (s_hook, 2.6, 0.15),
    (s_title, 1.6, 0.10),
    (s_kako, 4.0, 0.06),
    (s_lit, 5.0, 0.06),
    (s_compare, 3.4, 0.08),
    (s_bonus, 6.6, 0.0),
    (s_result, 3.8, 0.10),
    (s_coupons, 5.0, 0.08),
    (s_score, 4.4, 0.06),
    (s_cta, 5.4, 0.06),
]
LOOP_TAIL = 0.3  # final frames match the hook so the replay feels seamless
TOTAL = sum(d for _, d, _ in SCENES) + LOOP_TAIL


def render(t):
    c = Image.new("RGBA", (W, H), DARK + (255,))
    acc = 0.0
    for i, (fn, dur, pz) in enumerate(SCENES):
        if t < acc + dur:
            lt = t - acc
            fn(c, lt)
            s = punch(lt, 0, pz, 0.28) if pz else 1.0
            dx, dy = shake(lt, 0, 0.18, 14, seed=i) if i in (1, 4, 6) else (0, 0)
            if i == 5:  # extra punch when the price lands
                s *= punch(lt, 4.2, 0.08, 0.3)
            if i == 7:
                s *= punch(lt, 3.0, 0.06, 0.3)
            return zoom_frame(c, s, dx, dy).convert("RGB")
        acc += dur
    s_hook(c, 0, loop=True)
    return c.convert("RGB")


def frame_bytes(n):
    return render(n / FPS).tobytes()


def init(lang):
    global L
    L = TEXT[lang]


def main():
    lang, out = sys.argv[1], sys.argv[2]
    init(lang)
    if len(sys.argv) > 3 and sys.argv[3] == "--preview":
        ts = [float(x) for x in sys.argv[4].split(",")]
        ims = [render(x).resize((360, 640)) for x in ts]
        cols = min(6, len(ims))
        rows = math.ceil(len(ims) / cols)
        sheet = Image.new("RGB", (cols * 360, rows * 640), "black")
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * 360, (i // cols) * 640))
        sheet.save(out)
        return
    n = int(round(TOTAL * FPS))
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
         "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)
    with Pool(4, initializer=init, initargs=(lang,)) as pool:
        for i, b in enumerate(pool.imap(frame_bytes, range(n), chunksize=6)):
            ff.stdin.write(b)
            if i % 150 == 0:
                print(f"{lang}: frame {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{TOTAL:.1f}s")


if __name__ == "__main__":
    main()
