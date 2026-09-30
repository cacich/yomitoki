"""產生 Yomitoki 的預設手繪素材，輸出到 assets/defaults/（每張都是獨立 SVG）。

這些只是「預設版本」：使用者可以用任何工具產生的圖片替換，不必動這支腳本。
狸貓在各張圖裡共用同一組部件，改造型時只要改 tanuki() 再重跑一次即可。

用法：python scripts/make-default-art.py [輸出資料夾]
"""
import re
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "assets" / "defaults"
OUT.mkdir(parents=True, exist_ok=True)

# 色票
OAT, CREAM, TERRA, TERRA_D = "#F7F0E4", "#FFFBF4", "#D98B6A", "#A8573B"
SAGE, SAGE_D, BUTTER, ROSE = "#9DB08A", "#7A8F68", "#F2CF7E", "#E8B4A8"
COCOA, WALNUT, NIGHT = "#4A3B32", "#6B5A4E", "#2E2621"
# 狸貓專用
FUR, FUR_D, MASK = "#C9A07A", "#A07B5B", "#7A6555"

JP_FONT = "'Yu Gothic UI','Yu Gothic','Meiryo','Microsoft JhengHei','Noto Sans JP','Noto Sans CJK JP',sans-serif"


def sketch_filter(fid="sketch", freq=0.018, scale=4, seed=7):
    return (
        f'<filter id="{fid}" x="-10%" y="-10%" width="120%" height="120%">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{seed}" result="n"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{scale}" xChannelSelector="R" yChannelSelector="G"/>'
        "</filter>"
    )


def svg(w, h, body, defs="", title="", extra_style=""):
    style = f"<style>{extra_style}</style>" if extra_style else ""
    t = f"<title>{title}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"{t}<defs>{defs}</defs>{style}{body}</svg>\n"
    )


def mirror(d: str, cx=200) -> str:
    """把路徑裡的 x 座標以 cx 鏡射（路徑只用絕對座標、逗號分隔的 x y）。"""
    out, expect_x = [], True
    for tok in re.findall(r"[A-Za-z]|-?\d*\.?\d+", d):
        if tok.isalpha():
            out.append(tok)
            expect_x = True
        else:
            out.append(f"{2 * cx - float(tok):g}" if expect_x else tok)
            expect_x = not expect_x
    return " ".join(out)


# ── 狸貓部件（400×400 座標系，正面） ───────────────────────────
EAR_L = "M112 124 C 98 84,114 50,142 52 C 162 55,174 78,170 98 Z"
EAR_IN_L = "M124 110 C 116 86,127 67,142 68 C 153 70,159 83,157 94 Z"
MASK_L = "M116 170 C 112 140,140 126,166 134 C 187 141,193 162,186 180 C 177 200,150 203,131 195 C 121 190,117 180,116 170 Z"
HEAD = "M94 162 C 90 100,140 70,200 70 C 260 70,310 100,306 162 C 303 214,258 242,200 242 C 142 242,97 214,94 162 Z"
BODY = "M118 305 C 112 245,150 218,200 218 C 250 218,288 245,282 305 C 279 350,246 370,200 370 C 154 370,121 350,118 305 Z"
TAIL = "M272 318 C 330 318,378 272,364 222 C 354 186,318 184,306 212 C 296 236,300 262,262 288 Z"


def tanuki(eyes="open", arm="book", mouth="smile", book=True, tilt=0, head_only=False):
    """回傳一組 <g>，座標系 400×400。"""
    s = f'stroke="{WALNUT}" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"'
    parts = [f'<g transform="rotate({tilt} 200 230)">']
    if head_only:
        book = False
        arm = None
    # 尾巴（含條紋）
    if not head_only:
        parts.append(f'<clipPath id="tailclip"><path d="{TAIL}"/></clipPath>')
        parts.append(f'<path d="{TAIL}" fill="{FUR}" {s}/>')
        parts.append(
            f'<g clip-path="url(#tailclip)" fill="{FUR_D}">'
            '<path d="M300 200 L372 214 L368 236 L296 222 Z"/>'
            '<path d="M290 250 L376 262 L360 286 L280 272 Z"/>'
            "</g>"
        )
        parts.append(f'<path d="{TAIL}" fill="none" {s}/>')
        # 腳
        parts.append(f'<ellipse cx="158" cy="366" rx="30" ry="16" fill="{FUR_D}" {s}/>')
        parts.append(f'<ellipse cx="242" cy="366" rx="30" ry="16" fill="{FUR_D}" {s}/>')
        # 身體與肚子
        parts.append(f'<path d="{BODY}" fill="{FUR}" {s}/>')
        parts.append(f'<ellipse cx="200" cy="308" rx="56" ry="50" fill="{CREAM}"/>')
    # 舉手（揮手）
    if arm == "wave":
        parts.append(f'<path d="M262 250 C 290 236,312 214,322 186" fill="none" stroke="{WALNUT}" stroke-width="34" stroke-linecap="round"/>')
        parts.append(f'<path d="M262 250 C 290 236,312 214,322 186" fill="none" stroke="{FUR}" stroke-width="22" stroke-linecap="round"/>')
        parts.append(f'<circle cx="326" cy="176" r="21" fill="{FUR}" {s}/>')
        parts.append(f'<path d="M346 150 q10 -6 14 -18 M356 170 q12 -2 20 -10" fill="none" stroke="{WALNUT}" stroke-width="5" stroke-linecap="round"/>')
    # 耳朵
    parts.append(f'<path d="{EAR_L}" fill="{FUR}" {s}/>')
    parts.append(f'<path d="{mirror(EAR_L)}" fill="{FUR}" {s}/>')
    parts.append(f'<path d="{EAR_IN_L}" fill="{MASK}"/>')
    parts.append(f'<path d="{mirror(EAR_IN_L)}" fill="{MASK}"/>')
    # 頭
    parts.append(f'<path d="{HEAD}" fill="{FUR}" {s}/>')
    parts.append(f'<path d="M176 76 C 186 96,214 96,224 76" fill="{CREAM}" opacity="0.7"/>')
    parts.append(f'<path d="{MASK_L}" fill="{MASK}"/>')
    parts.append(f'<path d="{mirror(MASK_L)}" fill="{MASK}"/>')
    parts.append(f'<ellipse cx="200" cy="196" rx="46" ry="34" fill="{CREAM}"/>')
    # 眼睛
    if eyes == "open":
        for x in (156, 244):
            parts.append(f'<circle cx="{x}" cy="166" r="12" fill="{NIGHT}"/>')
            parts.append(f'<circle cx="{x + 4}" cy="161" r="4.5" fill="#FFFFFF"/>')
    elif eyes == "happy":
        for x in (156, 244):
            parts.append(f'<path d="M{x - 13} 170 Q{x} 154 {x + 13} 170" fill="none" stroke="{NIGHT}" stroke-width="6" stroke-linecap="round"/>')
    elif eyes == "down":
        for x in (156, 244):
            parts.append(f'<path d="M{x - 12} 166 Q{x} 176 {x + 12} 166" fill="none" stroke="{NIGHT}" stroke-width="6" stroke-linecap="round"/>')
    elif eyes == "dizzy":
        for x in (156, 244):
            parts.append(
                f'<path d="M{x} 166 m-3 0 a3 3 0 1 1 6 0 a6 6 0 1 1 -12 0 a9 9 0 1 1 18 0 a12 12 0 1 1 -24 0" '
                f'fill="none" stroke="{NIGHT}" stroke-width="4" stroke-linecap="round"/>'
            )
    # 鼻子、嘴巴、腮紅
    parts.append(f'<path d="M187 182 Q200 175 213 182 Q207 195 200 196 Q193 195 187 182 Z" fill="{NIGHT}"/>')
    if mouth == "smile":
        parts.append(f'<path d="M188 206 Q194 214 200 206 Q206 214 212 206" fill="none" stroke="{WALNUT}" stroke-width="4.5" stroke-linecap="round"/>')
    elif mouth == "open":
        parts.append(f'<path d="M188 205 Q200 226 212 205 Z" fill="{TERRA_D}" stroke="{WALNUT}" stroke-width="4" stroke-linejoin="round"/>')
    elif mouth == "wobble":
        parts.append(f'<path d="M184 212 q6 -6 12 0 t12 0 t12 0" fill="none" stroke="{WALNUT}" stroke-width="4.5" stroke-linecap="round"/>')
    parts.append(f'<ellipse cx="128" cy="206" rx="15" ry="9" fill="{ROSE}"/>')
    parts.append(f'<ellipse cx="272" cy="206" rx="15" ry="9" fill="{ROSE}"/>')
    # 書與手
    if book:
        parts.append(f'<path d="M122 282 L200 298 L278 282 L278 344 L200 360 L122 344 Z" fill="{TERRA}" {s}/>')
        page_l = "M130 276 C 158 271,184 278,200 290 L200 350 C 184 340,158 334,130 338 Z"
        parts.append(f'<path d="{page_l}" fill="{CREAM}" {s}/>')
        parts.append(f'<path d="{mirror(page_l)}" fill="{CREAM}" {s}/>')
        for i, y in enumerate((296, 309, 322)):
            parts.append(f'<path d="M146 {y - 6 + i} Q166 {y - 8 + i} 186 {y + i}" fill="none" stroke="{TERRA}" stroke-width="3.5" stroke-linecap="round"/>')
            parts.append(f'<path d="M214 {y + i} Q234 {y - 8 + i} 254 {y - 6 + i}" fill="none" stroke="{TERRA}" stroke-width="3.5" stroke-linecap="round"/>')
        parts.append(f'<ellipse cx="126" cy="312" rx="19" ry="23" fill="{FUR}" {s}/>')
        if arm != "wave":
            parts.append(f'<ellipse cx="274" cy="312" rx="19" ry="23" fill="{FUR}" {s}/>')
    parts.append("</g>")
    return "".join(parts)


def sparkle(x, y, r, color=BUTTER):
    k = r * 0.28
    return (
        f'<path d="M{x} {y - r} Q{x + k} {y - k} {x + r} {y} Q{x + k} {y + k} {x} {y + r} '
        f'Q{x - k} {y + k} {x - r} {y} Q{x - k} {y - k} {x} {y - r} Z" fill="{color}" '
        f'stroke="{WALNUT}" stroke-width="{max(2, r / 7):.1f}" stroke-linejoin="round"/>'
    )


def blob(cx, cy, rx, ry, color, opacity=1.0):
    return (
        f'<path d="M{cx} {cy - ry} C {cx + rx * 0.62} {cy - ry * 1.04},{cx + rx * 1.02} {cy - ry * 0.44},{cx + rx} {cy + ry * 0.06} '
        f'C {cx + rx * 0.98} {cy + ry * 0.66},{cx + rx * 0.46} {cy + ry * 1.02},{cx - rx * 0.08} {cy + ry} '
        f'C {cx - rx * 0.7} {cy + ry * 0.98},{cx - rx * 1.04} {cy + ry * 0.5},{cx - rx} {cy - ry * 0.04} '
        f'C {cx - rx * 0.96} {cy - ry * 0.62},{cx - rx * 0.56} {cy - ry * 0.98},{cx} {cy - ry} Z" '
        f'fill="{color}" opacity="{opacity}"/>'
    )


# ── App 圖示 ───────────────────────────────────────────────
def icon_shapes(stroke=22):
    s = f'stroke="{WALNUT}" stroke-width="{stroke}" stroke-linejoin="round" stroke-linecap="round"'
    page_l = "M226 612 C 330 580,436 596,512 646 L512 806 C 436 758,330 744,226 770 Z"
    return "".join(
        [
            f'<rect x="72" y="72" width="880" height="880" rx="210" fill="{OAT}" {s}/>',
            blob(250, 780, 150, 110, SAGE, 0.35),
            blob(800, 250, 110, 90, ROSE, 0.35),
            # 書
            f'<path d="M196 628 L512 676 L828 628 L828 800 L512 846 L196 800 Z" fill="{TERRA_D}" {s}/>',
            f'<path d="{page_l}" fill="{TERRA}" {s}/>',
            f'<path d="{mirror(page_l, 512)}" fill="{TERRA}" {s}/>',
            f'<path d="M280 660 Q380 640 470 676 M280 710 Q380 690 470 726" fill="none" stroke="{CREAM}" stroke-width="14" stroke-linecap="round" opacity="0.85"/>',
            f'<path d="M744 660 Q644 640 554 676 M744 710 Q644 690 554 726" fill="none" stroke="{CREAM}" stroke-width="14" stroke-linecap="round" opacity="0.85"/>',
            # 對話框
            f'<path d="M512 196 C 700 196,806 266,806 368 C 806 466,704 528,566 532 L528 604 L494 530 C 338 522,218 460,218 368 C 218 266,324 196,512 196 Z" fill="{CREAM}" {s}/>',
            sparkle(846, 196, 44),
            sparkle(178, 250, 30),
        ]
    )


def icon_text():
    return (
        f'<text x="372" y="420" text-anchor="middle" font-family="{JP_FONT}" font-size="168" font-weight="700" fill="{TERRA_D}">あ</text>'
        f'<path d="M462 370 L548 370 M520 338 L556 370 L520 402" fill="none" stroke="{SAGE_D}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<text x="652" y="420" text-anchor="middle" font-family="{JP_FONT}" font-size="168" font-weight="700" fill="{COCOA}">中</text>'
    )


def app_icon():
    return svg(1024, 1024, f'<g filter="url(#sketch)">{icon_shapes()}</g>{icon_text()}', sketch_filter(freq=0.012, scale=5), "Yomitoki")


def app_icon_small():
    s = f'stroke="{WALNUT}" stroke-width="12" stroke-linejoin="round"'
    body = (
        f'<rect x="12" y="12" width="232" height="232" rx="56" fill="{OAT}" {s}/>'
        f'<path d="M36 160 L128 176 L220 160 L220 214 L128 230 L36 214 Z" fill="{TERRA_D}" {s}/>'
        f'<path d="M128 44 C 180 44,212 66,212 96 C 212 124,184 142,146 144 L130 172 L116 142 C 76 138,44 120,44 96 C 44 66,76 44,128 44 Z" fill="{CREAM}" {s}/>'
    )
    return svg(256, 256, body, title="Yomitoki")


def extension_icon():
    s = f'stroke="{WALNUT}" stroke-width="16" stroke-linejoin="round"'
    head = tanuki(head_only=True)
    body = (
        f'<rect x="24" y="24" width="464" height="464" rx="116" fill="{OAT}" {s}/>'
        f'<g transform="translate(-50 80) scale(1.42)">{head}</g>'
        f'<path d="M400 52 C 446 52,470 72,470 100 C 470 126,446 144,414 146 L402 170 L394 146 C 356 142,330 126,330 100 C 330 72,356 52,400 52 Z" fill="{CREAM}" stroke="{WALNUT}" stroke-width="11" stroke-linejoin="round"/>'
        f'<circle cx="374" cy="100" r="8" fill="{TERRA_D}"/><circle cx="400" cy="100" r="8" fill="{TERRA_D}"/><circle cx="426" cy="100" r="8" fill="{TERRA_D}"/>'
    )
    return svg(512, 512, body, sketch_filter(), "Yomitoki extension")


# ── 吉祥物 ────────────────────────────────────────────────
def mascot_welcome():
    body = (
        blob(400, 430, 300, 270, SAGE, 0.32)
        + blob(560, 230, 110, 90, BUTTER, 0.55)
        + f'<g filter="url(#sketch)" transform="translate(40 40) scale(1.8)">{tanuki(arm="wave", mouth="open")}</g>'
        + sparkle(150, 200, 34)
        + sparkle(660, 520, 26, ROSE)
        + sparkle(120, 560, 20)
    )
    return svg(800, 800, body, sketch_filter(scale=3), "Yomitoki 歡迎")


def mascot_guide():
    body = (
        blob(200, 250, 170, 140, BUTTER, 0.35)
        + f'<g filter="url(#sketch)" transform="translate(20 16) scale(0.9)">{tanuki(tilt=-4)}</g>'
        + sparkle(346, 78, 20)
    )
    return svg(400, 400, body, sketch_filter(scale=3), "Yomitoki 小狸貓")


def mascot_loading():
    css = (
        "@keyframes sway{0%,100%{transform:rotate(-3deg)}50%{transform:rotate(3deg)}}"
        "@keyframes dot{0%,80%,100%{opacity:.25}40%{opacity:1}}"
        ".sway{transform-origin:200px 380px;animation:sway 2.4s ease-in-out infinite}"
        ".d{animation:dot 1.4s ease-in-out infinite}.d2{animation-delay:.2s}.d3{animation-delay:.4s}"
        "@media (prefers-reduced-motion: reduce){.sway,.d{animation:none}.d{opacity:1}}"
    )
    body = (
        blob(200, 250, 170, 140, SAGE, 0.3)
        + f'<g class="sway"><g filter="url(#sketch)" transform="translate(30 36) scale(0.85)">{tanuki(eyes="down")}</g></g>'
        + f'<path d="M292 40 C 342 40,372 60,372 88 C 372 114,346 130,312 132 L300 154 L292 130 C 254 126,228 110,228 88 C 228 60,254 40,292 40 Z" fill="{CREAM}" stroke="{WALNUT}" stroke-width="5" stroke-linejoin="round"/>'
        + f'<circle class="d" cx="272" cy="88" r="9" fill="{TERRA_D}"/>'
        + f'<circle class="d d2" cx="300" cy="88" r="9" fill="{TERRA_D}"/>'
        + f'<circle class="d d3" cx="328" cy="88" r="9" fill="{TERRA_D}"/>'
    )
    return svg(400, 400, body, sketch_filter(scale=3), "翻譯中", css)


def mascot_error():
    s = f'stroke="{WALNUT}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"'
    body = (
        blob(400, 450, 300, 250, ROSE, 0.3)
        # 掉在地上的書與散落的紙
        + f'<g filter="url(#sketch)">'
        + f'<path d="M480 640 L600 610 L700 650 L700 690 L600 660 L480 690 Z" fill="{TERRA}" {s}/>'
        + f'<path d="M488 628 C 530 610,570 604,600 616 L600 656 C 570 646,530 650,488 670 Z" fill="{CREAM}" {s}/>'
        + f'<path d="M600 616 C 630 606,664 616,694 636 L694 676 C 664 658,630 652,600 656 Z" fill="{CREAM}" {s}/>'
        + f'<path d="M110 640 L170 624 L182 670 L122 686 Z" fill="{CREAM}" {s}/>'
        + f'<path d="M640 470 L690 490 L672 536 L622 516 Z" fill="{CREAM}" {s}/>'
        + f'<g transform="translate(60 40) scale(1.7)">{tanuki(eyes="dizzy", mouth="wobble", book=False, tilt=6)}</g>'
        + "</g>"
        # 汗滴與亂線
        + f'<path d="M620 250 C 606 272,604 290,618 298 C 632 306,646 292,640 272 Z" fill="#CFE3EE" stroke="{WALNUT}" stroke-width="5"/>'
        + f'<path d="M300 90 c 20 -30 60 -30 70 0 c 10 30 -40 40 -30 10 c 10 -30 60 -20 70 10" fill="none" stroke="{WALNUT}" stroke-width="6" stroke-linecap="round"/>'
    )
    return svg(800, 800, body, sketch_filter(scale=3), "發生錯誤")


def empty_shelf():
    s = f'stroke="{WALNUT}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"'
    plank = "#E6CFAE"
    body = (
        blob(600, 430, 520, 320, SAGE, 0.22)
        + '<g filter="url(#sketch)">'
        # 書架框
        + f'<path d="M250 170 L950 170 L950 640 L250 640 Z" fill="{CREAM}" {s}/>'
        + f'<path d="M236 158 L964 158 L964 186 L236 186 Z" fill="{plank}" {s}/>'
        + f'<path d="M250 400 L950 400 L950 424 L250 424 Z" fill="{plank}" {s}/>'
        + f'<path d="M236 628 L964 628 L964 656 L236 656 Z" fill="{plank}" {s}/>'
        + f'<path d="M270 690 L270 656 M930 690 L930 656" fill="none" {s}/>'
        # 一本斜靠的書（空書架的孤單感）
        + f'<path d="M860 250 L900 244 L926 398 L886 404 Z" fill="{TERRA}" {s}/>'
        + f'<path d="M872 290 L906 285" fill="none" stroke="{CREAM}" stroke-width="5" stroke-linecap="round"/>'
        # 盆栽
        + f'<path d="M300 560 L380 560 L370 628 L310 628 Z" fill="{TERRA_D}" {s}/>'
        + f'<path d="M340 560 C 330 520,300 500,290 470 C 320 480,340 510,340 560 C 350 510,370 470,400 460 C 395 500,360 520,340 560 Z" fill="{SAGE}" {s}/>'
        + "</g>"
        + f'<g filter="url(#sketch)" transform="translate(470 330) scale(0.78)">{tanuki(tilt=-5)}</g>'
        + sparkle(1010, 140, 30)
        + sparkle(180, 300, 22, ROSE)
        + f'<path d="M180 120 L300 104" stroke="{ROSE}" stroke-width="30" stroke-linecap="butt" opacity="0.7"/>'
    )
    return svg(1200, 800, body, sketch_filter(scale=4), "書架還沒有作品")


def empty_series():
    s = f'stroke="{WALNUT}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"'
    page_l = "M200 210 C 330 180,470 190,600 240 L600 640 C 470 590,330 580,200 610 Z"
    lines = "".join(
        f'<path d="M250 {y} Q400 {y - 22} 560 {y + 14}" fill="none" stroke="{SAGE_D}" stroke-width="4" stroke-dasharray="4 14" stroke-linecap="round"/>'
        f'<path d="M640 {y + 14} Q800 {y - 22} 950 {y}" fill="none" stroke="{SAGE_D}" stroke-width="4" stroke-dasharray="4 14" stroke-linecap="round"/>'
        for y in (300, 370, 440, 510)
    )
    body = (
        blob(600, 420, 520, 330, BUTTER, 0.28)
        + '<g filter="url(#sketch)">'
        + f'<path d="M180 232 L600 262 L1020 232 L1020 640 L600 672 L180 640 Z" fill="{TERRA}" {s}/>'
        + f'<path d="{page_l}" fill="{CREAM}" {s}/>'
        + f'<path d="{mirror(page_l, 600)}" fill="{CREAM}" {s}/>'
        + lines
        # 鉛筆
        + f'<path d="M820 600 L960 460 L990 490 L850 630 Z" fill="{BUTTER}" {s}/>'
        + f'<path d="M820 600 L850 630 L806 644 Z" fill="{CREAM}" {s}/>'
        + f'<path d="M960 460 L974 446 C 982 438,996 438,1004 446 C 1012 454,1012 468,1004 476 L990 490 Z" fill="{ROSE}" {s}/>'
        + "</g>"
        + f'<g filter="url(#sketch)" transform="translate(20 400) scale(0.9)">{tanuki(arm="wave", book=False, eyes="happy")}</g>'
        + sparkle(1060, 170, 28)
        + sparkle(130, 190, 22, ROSE)
    )
    return svg(1200, 800, body, sketch_filter(scale=4), "還沒有任何一話")


def paper_texture():
    defs = (
        '<filter id="grain" filterUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="3" stitchTiles="stitch" result="fine"/>'
        '<feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="11" stitchTiles="stitch" result="coarse"/>'
        '<feComposite in="fine" in2="coarse" operator="arithmetic" k1="0" k2="0.7" k3="0.5" k4="0" result="mix"/>'
        '<feColorMatrix in="mix" type="matrix" values="0 0 0 0 0.42  0 0 0 0 0.35  0 0 0 0 0.30  0 0 0 -1.1 0.62"/>'
        "</filter>"
    )
    body = f'<rect width="512" height="512" fill="{OAT}"/><rect width="512" height="512" filter="url(#grain)" opacity="0.55"/>'
    return svg(512, 512, body, defs, "paper texture")


def readme_hero():
    s = f'stroke="{WALNUT}" stroke-width="5" stroke-dasharray="2 14" stroke-linecap="round" fill="none"'
    defs = (
        sketch_filter(freq=0.012, scale=5)
        + sketch_filter("sketch2", scale=3, seed=4)
        + '<filter id="grain" filterUnits="userSpaceOnUse" x="0" y="0" width="1280" height="640">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" seed="3" result="fine"/>'
        '<feColorMatrix in="fine" type="matrix" values="0 0 0 0 0.42  0 0 0 0 0.35  0 0 0 0 0.30  0 0 0 -1.2 0.6"/>'
        "</filter>"
    )
    body = (
        f'<rect width="1280" height="640" fill="{OAT}"/>'
        '<rect width="1280" height="640" filter="url(#grain)" opacity="0.35"/>'
        + blob(250, 330, 230, 220, SAGE, 0.28)
        + blob(1050, 360, 220, 210, ROSE, 0.3)
        + f'<rect x="28" y="28" width="1224" height="584" rx="28" {s}/>'
        + f'<g transform="translate(80 150) scale(0.34)"><g filter="url(#sketch)">{icon_shapes()}</g>{icon_text()}</g>'
        + f'<text x="470" y="290" font-family="Fraunces,Georgia,\'Times New Roman\',serif" font-size="100" font-weight="700" fill="{COCOA}">Yomitoki</text>'
        + f'<text x="476" y="356" font-family="{JP_FONT}" font-size="40" fill="{TERRA_D}" font-weight="700">よみとき ・ 讀解</text>'
        + f'<text x="476" y="424" font-family="Nunito,\'Segoe UI\',sans-serif" font-size="28" fill="{COCOA}">A cozy, local-first reader that translates</text>'
        + f'<text x="476" y="462" font-family="Nunito,\'Segoe UI\',sans-serif" font-size="28" fill="{COCOA}">the manga screenshots you take yourself.</text>'
        + f'<g filter="url(#sketch2)" transform="translate(930 210) scale(0.9)">{tanuki(arm="wave", mouth="open")}</g>'
        + f'<path d="M60 70 L200 50" stroke="{BUTTER}" stroke-width="34" opacity="0.75"/>'
        + f'<path d="M1110 590 L1240 566" stroke="{ROSE}" stroke-width="34" opacity="0.75"/>'
        + sparkle(900, 120, 26)
        + sparkle(430, 520, 18, ROSE)
    )
    return svg(1280, 640, body, defs, "Yomitoki")


FILES = {
    "app-icon.svg": app_icon,
    "app-icon-small.svg": app_icon_small,
    "extension-icon.svg": extension_icon,
    "mascot-welcome.svg": mascot_welcome,
    "mascot-guide.svg": mascot_guide,
    "mascot-loading.svg": mascot_loading,
    "mascot-error.svg": mascot_error,
    "empty-shelf.svg": empty_shelf,
    "empty-series.svg": empty_series,
    "paper-texture.svg": paper_texture,
    "readme-hero.svg": readme_hero,
}

for name, fn in FILES.items():
    (OUT / name).write_text(fn(), encoding="utf-8", newline="\n")
    print("wrote", name)
