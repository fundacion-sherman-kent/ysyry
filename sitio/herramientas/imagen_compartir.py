#!/usr/bin/env python3
"""Genera la miniatura para compartir Ysyry en redes (1200 x 630, la medida de las tarjetas de Open Graph y X/Twitter).
Dibuja el río real del mapa (Paraná y Paraguay, de sitio/datos/mapa_v10.json) sobre el azul de la casa, con el nombre y la bajada.
Uso: imagen_compartir.py [SALIDA.png]   (por defecto sitio/compartir/ysyry-compartir.png)
Fuentes: Arial del sistema (Windows). Si falta, usa la fuente por defecto de Pillow y la imagen sale peor: revisar a ojo."""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
W, H, S = 1200, 630, 2          # tamaño final y sobremuestreo para suavizar los bordes
AZUL, AZUL2 = (0, 18, 30), (7, 19, 30)
MENTA, NARANJA, ACERO, PAPEL = (143, 217, 196), (251, 101, 0), (102, 123, 137), (249, 249, 247)
FUENTES = Path("C:/Windows/Fonts")


def fuente(nombre, tam):
    try:
        return ImageFont.truetype(str(FUENTES / nombre), tam * S)
    except Exception:
        return ImageFont.load_default()


def subtrazos(d):
    """Lista de polilíneas [(x, y), ...] de un path SVG con M/L/Z."""
    out, actual = [], []
    for cmd, x, y in re.findall(r"([MLZ])\s*([-\d.]+)?,?([-\d.]+)?", d):
        if cmd == "M":
            if len(actual) > 1:
                out.append(actual)
            actual = [(float(x), float(y))]
        elif cmd == "L":
            actual.append((float(x), float(y)))
    if len(actual) > 1:
        out.append(actual)
    return out


def main():
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "sitio" / "compartir" / "ysyry-compartir.png"
    mapa = json.load(open(RAIZ / "sitio" / "datos" / "mapa_v10.json", encoding="utf-8"))
    rios = subtrazos(mapa["rio_parana"]) + subtrazos(mapa["rio_paraguay"])
    pts = [p for r in rios for p in r]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    # el corredor cabe en la franja derecha de la imagen
    caja = (930, 30, 1170, 600)
    esc = min((caja[2] - caja[0]) / (x1 - x0), (caja[3] - caja[1]) / (y1 - y0))
    ox = caja[0] + ((caja[2] - caja[0]) - (x1 - x0) * esc) / 2
    oy = caja[1] + ((caja[3] - caja[1]) - (y1 - y0) * esc) / 2
    tr = lambda p: ((ox + (p[0] - x0) * esc) * S, (oy + (p[1] - y0) * esc) * S)

    fondo = Image.new("RGB", (W * S, H * S), AZUL)
    g = ImageDraw.Draw(fondo)
    for y in range(H * S):                       # degradado vertical muy suave
        t = y / (H * S)
        g.line([(0, y), (W * S, y)], fill=tuple(int(AZUL[i] + (AZUL2[i] - AZUL[i]) * t) for i in range(3)))

    # contornos de los países, tenues, para dar contexto
    contexto = Image.new("RGBA", fondo.size, (0, 0, 0, 0))
    c = ImageDraw.Draw(contexto)
    for p in mapa["paths_pais"]:
        for sub in subtrazos(p["d"]):
            c.line([tr(q) for q in sub], fill=(102, 123, 137, 70), width=2 * S // 2)
    fondo.paste(contexto, (0, 0), contexto)

    # el río con resplandor
    brillo = Image.new("RGBA", fondo.size, (0, 0, 0, 0))
    b = ImageDraw.Draw(brillo)
    for r in rios:
        b.line([tr(q) for q in r], fill=MENTA + (255,), width=9 * S)
    brillo = brillo.filter(ImageFilter.GaussianBlur(10 * S))
    fondo.paste(brillo, (0, 0), brillo)
    nitido = Image.new("RGBA", fondo.size, (0, 0, 0, 0))
    n = ImageDraw.Draw(nitido)
    for r in rios:
        n.line([tr(q) for q in r], fill=MENTA + (255,), width=int(3.2 * S))
    fondo.paste(nitido, (0, 0), nitido)

    puntos_rio = [tr(q) for r in rios for q in r]
    # las ciudades que están sobre el corredor
    d = ImageDraw.Draw(fondo)
    for poi in mapa["poi"]:
        if poi.get("clase") == "ciudad":
            x, y = tr((poi["x"], poi["y"]))
            cerca = min((x - q[0]) ** 2 + (y - q[1]) ** 2 for q in puntos_rio) < (22 * S) ** 2
            if cerca:
                d.ellipse([x - 4 * S, y - 4 * S, x + 4 * S, y + 4 * S], fill=PAPEL)

    # texto, centrado: si una red recorta la imagen en cuadrado (WhatsApp, a veces), el recorte central de 630 px conserva el nombre y la bajada
    cx = 600 * S
    d.text((cx, 52 * S), "YSYRY", font=fuente("arialbd.ttf", 150), fill=PAPEL, anchor="ma")
    d.rectangle([540 * S, 232 * S, 660 * S, 238 * S], fill=NARANJA)
    bajada = ["Evidencia, alertas y", "prospectiva sobre la Hidrovía", "Paraguay-Paraná"]
    for i, linea in enumerate(bajada):
        d.text((cx, (262 + i * 48) * S), linea, font=fuente("arial.ttf", 38), fill=PAPEL, anchor="ma")
    d.text((cx, 438 * S), "Nivel del río · AIS · Avisos oficiales", font=fuente("arial.ttf", 25), fill=MENTA, anchor="ma")
    d.text((cx, 474 * S), "Dos fuentes independientes como mínimo", font=fuente("arial.ttf", 25), fill=MENTA, anchor="ma")
    d.text((cx, 544 * S), "ysyry.fundacionkent.org", font=fuente("arialbd.ttf", 30), fill=PAPEL, anchor="ma")
    d.text((cx, 586 * S), "Fundación Sherman Kent", font=fuente("arial.ttf", 22), fill=ACERO, anchor="ma")
    # sello beta, a la izquierda arriba (queda fuera del recorte cuadrado)
    d.rounded_rectangle([64 * S, 30 * S, 184 * S, 72 * S], radius=21 * S, outline=NARANJA, width=3 * S)
    d.text((124 * S, 51 * S), "BETA", font=fuente("arialbd.ttf", 22), fill=NARANJA, anchor="mm")

    destino.parent.mkdir(parents=True, exist_ok=True)
    final = fondo.resize((W, H), Image.LANCZOS)
    # paleta reducida y sin tramado: un fondo plano con trazos pesa unos 50 KB y WhatsApp sólo muestra la tarjeta grande con imágenes livianas
    final.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(destino, optimize=True)
    print("imagen:", destino, destino.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
