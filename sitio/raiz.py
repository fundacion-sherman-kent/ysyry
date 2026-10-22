#!/usr/bin/env python3
"""Página raíz de Ysyry (la dirección que se comparte): lleva el título, la descripción y las etiquetas para compartir en redes, y redirige
a la aplicación en /sitio/. Misma idea que la raíz de SIWA: una redirección pelada daba una tarjeta vacía al compartir el enlace.
Uso: raiz.py SALIDA.html"""
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import direccion

TITULO = "Ysyry — Evidencia, alertas y prospectiva sobre la Hidrovía Paraguay-Paraná"
DESCRIPCION = ("Plataforma pública y gratuita sobre el corredor de la Hidrovía Paraguay-Paraná: nivel del río, buques por AIS, avisos oficiales, "
               "indicios con su fuente y su nivel de evidencia, y preguntas con probabilidad que se resuelven solas. Regla de la casa: dos fuentes independientes como mínimo.")


def pagina():
    e = html.escape
    return """<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(t)s</title>
<meta name="description" content="%(d)s">
<link rel="canonical" href="%(app)s">
<meta name="author" content="Fundación Sherman Kent">
<meta name="theme-color" content="#00121E">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Fundación Sherman Kent">
<meta property="og:locale" content="es_AR">
<meta property="og:url" content="%(base)s">
<meta property="og:title" content="%(t)s">
<meta property="og:description" content="%(d)s">
<meta property="og:image" content="%(img)s">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Ysyry: el río Paraguay-Paraná dibujado sobre fondo azul, con el nombre de la plataforma">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="%(img)s">
<meta name="twitter:title" content="%(t)s">
<meta name="twitter:description" content="%(d)s">
<link rel="icon" type="image/svg+xml" href="sitio/marca/ysyry-marca.svg">
<link rel="icon" type="image/png" sizes="32x32" href="sitio/marca/favicon-32.png">
<link rel="apple-touch-icon" href="sitio/marca/apple-touch-icon.png">
<meta http-equiv="refresh" content="0; url=sitio/">
<style>body{font-family:system-ui,sans-serif;background:#00121E;color:#e8eef2;margin:0;display:grid;place-items:center;min-height:100vh;text-align:center;padding:16px}a{color:#8fd9c4}</style>
</head>
<body>
<main>
<h1>Ysyry</h1>
<p>%(d)s</p>
<p><a href="sitio/index.html">Entrar a Ysyry</a></p>
</main>
</body>
</html>
""" % {"t": e(TITULO), "d": e(DESCRIPCION), "app": e(direccion.APP), "base": e(direccion.BASE), "img": e(direccion.IMAGEN)}


if __name__ == "__main__":
    destino = Path(sys.argv[1])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(pagina(), encoding="utf-8", newline="\n")
    print("raíz escrita:", destino)
