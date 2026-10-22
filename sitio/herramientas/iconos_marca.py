#!/usr/bin/env python3
"""Iconos de la marca de Ysyry («La confluencia», ver sitio/marca/*.svg): favicon de 32 px y apple-touch-icon de 180 px, en PNG,
dibujados con la misma geometría del SVG sobre el azul de la casa. Los navegadores modernos usan el SVG; el PNG es el respaldo.
Uso: iconos_marca.py   (escribe en sitio/marca/)"""
from pathlib import Path

from PIL import Image, ImageDraw

AZUL = (0, 18, 30)
SENAL = (81, 143, 184)       # #518FB8, el azul de la casa con la luz subida (fondo oscuro)
BRAZO = (138, 148, 160)      # #8A94A0
RAIZ = Path(__file__).resolve().parents[1] / "marca"
S = 8                        # sobremuestreo


def bezier(p0, p1, p2, p3, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def isotipo(d, ox, oy, k):
    """Dibuja la marca (lienzo de 48 unidades) con origen (ox, oy) y k píxeles por unidad."""
    P = lambda x, y: (ox + x * k, oy + y * k)
    def trazo(pts, color, ancho):
        pts = [P(*p) for p in pts]
        d.line(pts, fill=color, width=max(1, round(ancho * k)), joint="curve")
        r = ancho * k / 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    trazo([(6, 8), (23, 23)], BRAZO, 2.6)
    trazo([(6, 33), (23, 23)], BRAZO, 2.6)
    trazo(bezier((23, 23), (31, 27), (34, 33), (43, 38)), SENAL, 3.4)
    cx, cy = P(23, 23)
    d.ellipse([cx - 4.6 * k, cy - 4.6 * k, cx + 4.6 * k, cy + 4.6 * k], fill=SENAL)
    halo = (int(AZUL[0] + (SENAL[0] - AZUL[0]) * .55), int(AZUL[1] + (SENAL[1] - AZUL[1]) * .55), int(AZUL[2] + (SENAL[2] - AZUL[2]) * .55))
    d.ellipse([cx - 8.2 * k, cy - 8.2 * k, cx + 8.2 * k, cy + 8.2 * k], outline=halo, width=max(1, round(1.3 * k)))


def icono(lado, margen):
    im = Image.new("RGB", (lado * S, lado * S), AZUL)
    d = ImageDraw.Draw(im)
    area = lado * S * (1 - 2 * margen)
    k = area / 48
    off = lado * S * margen
    isotipo(d, off, off, k)
    return im.resize((lado, lado), Image.LANCZOS)


if __name__ == "__main__":
    RAIZ.mkdir(parents=True, exist_ok=True)
    icono(32, 0.04).save(RAIZ / "favicon-32.png", optimize=True)
    icono(180, 0.14).save(RAIZ / "apple-touch-icon.png", optimize=True)
    print("iconos escritos en", RAIZ)
