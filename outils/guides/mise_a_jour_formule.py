"""Mise à jour des deux guides publics après la revue de la formule (28/11/2026).

Les sources HTML des guides vivaient sur l'ancien PC (perdu le 26/11/2026) : on garde les PDF tels quels et on pose, par
calque, de nouveaux encadrés sur les seuls passages devenus faux (« 50 % YouTube / 50 % écoutes », « Top 5 = 2 sources »).
Le calque est vectoriel (texte net dans le PDF) et le même calque est collé sur les aperçus JPG du site.

    python outils/guides/mise_a_jour_formule.py

Coordonnées : pixels des aperçus (1600 px de large).
"""
import io
import os
import shutil

from PIL import Image
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter, Transformation

ICI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ICI, "..", ".."))
DOCS = os.path.join(REPO, "public", "documents")
F = "file:///" + os.path.join(REPO, "resources", "fonts").replace("\\", "/") + "/"
LOGOS = "file:///" + os.path.join(REPO, "public", "assets", "img", "plateformes").replace("\\", "/") + "/"
W, H = 1600, 1131

CSS = f"""
@font-face{{font-family:Anton;src:url("{F}Anton-Regular.ttf")}}
@font-face{{font-family:Pop;src:url("{F}Poppins-Regular.ttf");font-weight:400}}
@font-face{{font-family:Pop;src:url("{F}Poppins-Bold.ttf");font-weight:700}}
@font-face{{font-family:Serif;src:url("{F}PT_Serif-Web-Regular.ttf")}}
@page{{size:{W}px {H}px;margin:0}}
html,body{{margin:0;padding:0;background:transparent}}
.page{{position:relative;width:{W}px;height:{H}px;overflow:hidden;font-family:Pop,Arial,sans-serif;color:#1a1530}}
.cache{{position:absolute;-webkit-mask-composite:source-in}}
.abs{{position:absolute}}
.carte{{position:absolute;background:#fff;border-radius:18px;box-shadow:0 14px 34px rgba(80,70,160,.10);text-align:center;box-sizing:border-box;padding:18px 20px}}
.big{{font-family:Anton;font-size:58px;line-height:1.12;letter-spacing:.5px}}
.grad{{background:linear-gradient(90deg,#c64ee8,#4f8bff);-webkit-background-clip:text;color:transparent}}
.logos img{{height:30px;margin:0 3px;vertical-align:middle}}
.b{{font-weight:700;font-size:15px;margin-top:8px}}
.t{{font-size:13px;color:#5a5670;line-height:1.35;margin-top:2px}}
.note{{position:absolute;border-left:2px solid #cfc9ee;padding-left:14px;width:300px}}
.note b{{display:block;font-size:15px}} .note span{{font-size:13px;color:#5a5670;line-height:1.35}}
.anton{{font-family:Anton;text-transform:uppercase;letter-spacing:.3px}}
"""

def cache(x0, y0, x1, y1, fond, m=14):
    """Rectangle opaque sur (x0, y0, x1, y1), bordé d'un fondu de m px À L'EXTÉRIEUR : l'ancien texte reste entièrement caché."""
    f = (f"linear-gradient(90deg,transparent,#000 {m}px,#000 calc(100% - {m}px),transparent),"
         f"linear-gradient(180deg,transparent,#000 {m}px,#000 calc(100% - {m}px),transparent)")
    return (f'<div class="cache" style="left:{x0 - m}px;top:{y0 - m}px;width:{x1 - x0 + 2 * m}px;height:{y1 - y0 + 2 * m}px;'
            f'background:{fond};-webkit-mask-image:{f}"></div>')

LOGOS5 = "".join(f'<img src="{LOGOS}{n}.png">' for n in ("spotify", "apple-music", "boomplay", "deezer", "shazam"))

# ------------------------------------------------------------------ Le voyage d'un titre
VOYAGE_6 = (
    cache(70, 204, 760, 252, "#fff", 5)
    + '<div class="abs" style="left:76px;top:212px;font-family:Serif;font-size:19px;color:#4a4a5a">'
      "Pour chaque titre, chaque semaine : les écoutes et les vues, pesées pays par pays.</div>"
    + cache(246, 510, 592, 746, "#fff")
    + '<div class="carte" style="left:260px;top:519px;width:318px;height:222px;border-top:4px solid #ff3b3b">'
      '<div class="big" style="color:#ff3b3b">VUES</div>'
      f'<div class="logos" style="margin-top:8px"><img src="{LOGOS}youtube.png" style="height:34px"></div>'
      '<div class="b">YouTube</div><div class="t">les vues du clip officiel ; leur poids baisse là où les écoutes du pays sont bien mesurées</div></div>'
    + cache(1006, 510, 1352, 756, "linear-gradient(90deg,#fff 70%,#f9fdff)")
    + '<div class="carte" style="left:1021px;top:519px;width:318px;height:222px;border-top:4px solid #8b5cf6">'
      '<div class="big grad">ÉCOUTES</div>'
      f'<div class="logos" style="margin-top:8px">{LOGOS5}</div>'
      '<div class="b">Les tops des plateformes</div><div class="t">chaque place devient une part d\'écoute ; Spotify compte double</div></div>'
    + cache(942, 584, 1010, 629, "#fff", 3)
    + '<div class="abs" style="left:866px;top:578px;padding:7px 15px;border:1.5px solid #c9b8f7;border-radius:20px;background:#fff;'
      'font-weight:700;font-size:15px;color:#7c4dff">Tout s\'équilibre !</div>'
    + cache(446, 952, 1540, 1030, "linear-gradient(90deg,#fcf9ff,#fff)", 16)
    + '<div class="note" style="left:458px;top:960px"><b>Indice Cauri</b><span>le N°1 vaut 100, les autres en proportion de leur score.</span></div>'
    + '<div class="note" style="left:822px;top:960px"><b>Seulement sur YouTube ?</b><span>le titre compte aussi, avec un poids réduit (depuis le 27 novembre 2026).</span></div>'
    + '<div class="note" style="left:1186px;top:960px"><b>Formule figée</b><span>Chaque classement publié garde sa formule : mêmes données, même résultat.</span></div>'
)
VOYAGE_7 = (
    cache(1100, 244, 1536, 300, "linear-gradient(90deg,#f7fbfe,#f1f8ff)", 4)
    + '<div class="abs anton" style="left:1104px;top:247px;font-size:25px">Seulement YouTube ?</div>'
    + '<div class="abs" style="left:1104px;top:281px;font-size:14.5px;color:#55526a">il entre aussi, avec un poids réduit (clip de moins d\'un an)</div>'
)

# ------------------------------------------------------------------ Comprendre nos classements
COMPRENDRE_1 = (
    cache(1112, 212, 1352, 250, "linear-gradient(90deg,#fcfdff,#e2f4ff)", 4)
    + '<div class="abs" style="left:1118px;top:212px;width:230px;text-align:center;font-size:13.5px;color:#55526a;line-height:1.3">'
      "Écoutes et vues pesées pays par pays : indice Cauri de 0 à 100.</div>"
    + cache(540, 699, 1052, 999, "linear-gradient(90deg,#fffdff,#fbfcff)", 8)
    + '<div class="abs" style="left:548px;top:707px;width:495px;height:283px;border-radius:22px;background:#fbfcff;border:1px solid #e4e7f4;box-sizing:border-box"></div>'
    + '<div class="abs" style="left:569px;top:726px;width:34px;height:20px;border-radius:10px;background:linear-gradient(90deg,#4f8bff,#7b5cf5);'
      'color:#fff;font-family:Anton;font-size:14px;text-align:center;line-height:20px">02</div>'
    + '<div class="abs anton" style="left:617px;top:718px;font-size:29px">Le score d\'un titre</div>'
    + '<div class="abs" style="left:572px;top:790px;width:112px;height:112px;border-radius:50%;background:conic-gradient(#c64ee8,#7b5cf5,#4f8bff,#c64ee8)"></div>'
    + '<div class="abs" style="left:586px;top:804px;width:84px;height:84px;border-radius:50%;background:#fbfcff;text-align:center">'
      '<div style="font-family:Anton;font-size:30px;margin-top:12px">100</div><div style="font-size:10px;color:#8a87a0;margin-top:-2px">le N°1</div></div>'
    + '<div class="abs" style="left:705px;top:764px;width:325px;line-height:1.3">'
      '<div class="anton grad" style="font-size:23px;line-height:1.1">Les tops des plateformes</div>'
      '<div class="t" style="font-size:12.5px;margin-top:1px">chaque place dans les tops du pays devient une part d\'écoute (Spotify compte double)</div>'
      f'<div class="logos" style="margin-top:5px">{LOGOS5.replace("<img ", "<img style=\'height:22px\' ")}</div>'
      '<div class="anton" style="font-size:23px;line-height:1.1;color:#ff3b3b;margin-top:8px">YouTube</div>'
      '<div class="t" style="font-size:12.5px;margin-top:1px">les vues du clip officiel, avec moins de poids là où les écoutes sont bien mesurées</div></div>'
    + '<div class="abs t" style="left:570px;top:930px;width:460px;font-size:12px;line-height:1.3">Le N°1 vaut 100, les autres en proportion. Un tube vu '
      "seulement sur YouTube entre aussi, avec un poids réduit. Formule en vigueur depuis le 27 novembre 2026.</div>"
)
COMPRENDRE_2 = (
    cache(384, 251, 712, 347, "linear-gradient(90deg,#fffaff,#fff)", 6)
    + '<div class="abs" style="left:391px;top:258px;width:314px;height:82px;border-radius:16px;background:#fff6ff;border:1px solid #f3dcf6;box-sizing:border-box"></div>'
    + '<div class="abs" style="left:406px;top:275px;width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#b350f6,#e04fd0)">'
      '<svg viewBox="0 0 24 24" width="48" height="48"><path d="M10 8.5v7l6-3.5z" fill="#fff"/><rect x="5" y="6" width="14" height="12" rx="3" fill="none" stroke="#fff" stroke-width="1.6"/></svg></div>'
    + '<div class="abs anton" style="left:467px;top:266px;font-size:24px">YouTube seul ?</div>'
    + '<div class="abs t" style="left:467px;top:298px;width:228px;font-size:12.5px">Un tube vu seulement sur YouTube entre, avec un poids réduit.</div>'
)

PATCHS = {
    "cauri-charts-le-voyage-d-un-titre": {6: VOYAGE_6, 7: VOYAGE_7},
    "cauri-charts-comprendre-nos-classements": {1: COMPRENDRE_1, 2: COMPRENDRE_2},
}


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": W, "height": H})
        for fichier, pages in PATCHS.items():
            pdf = os.path.join(DOCS, fichier + ".pdf")
            orig = os.path.join(ICI, "originaux", fichier + ".pdf")
            os.makedirs(os.path.dirname(orig), exist_ok=True)
            if not os.path.exists(orig):
                shutil.copy(pdf, orig)          # on repart toujours de l'original : relancer ne superpose pas deux calques
            lecteur, sortie = PdfReader(orig), PdfWriter()
            calques = {}
            for n, html in pages.items():
                tmp = os.path.join(ICI, "_calque.html")
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='page'>{html}</div></body></html>")
                pg.goto("file:///" + tmp.replace("\\", "/"), wait_until="networkidle")
                pg.evaluate("document.fonts.ready")
                calques[n] = PdfReader(io.BytesIO(pg.pdf(width=f"{W}px", height=f"{H}px", print_background=True))).pages[0]
                png = Image.open(io.BytesIO(pg.screenshot(omit_background=True, full_page=False))).convert("RGBA")
                apercu = os.path.join(DOCS, "apercus", fichier, f"page-{n:02d}.jpg")
                ref = os.path.join(ICI, "originaux", fichier, f"page-{n:02d}.jpg")
                os.makedirs(os.path.dirname(ref), exist_ok=True)
                if not os.path.exists(ref):
                    shutil.copy(apercu, ref)
                fond = Image.open(ref).convert("RGBA")
                calque = png.resize(fond.size, Image.LANCZOS)
                Image.alpha_composite(fond, calque).convert("RGB").save(apercu, quality=85, optimize=True, progressive=True)
            sortie = PdfWriter(clone_from=lecteur)
            for i, page in enumerate(sortie.pages, start=1):
                if i in calques:
                    lw, lh = float(page.mediabox.width), float(page.mediabox.height)
                    c = calques[i]
                    cw, ch = float(c.mediabox.width), float(c.mediabox.height)
                    page.merge_transformed_page(c, Transformation().scale(lw / cw, lh / ch))
            with open(pdf, "wb") as f:
                sortie.write(f)
            print(fichier, ": pages", sorted(pages), "mises à jour")
        b.close()


if __name__ == "__main__":
    main()
