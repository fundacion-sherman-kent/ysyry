#!/usr/bin/env python3
"""Escáner de Ysyry con modelo de pesos abiertos: segunda lectura, propone y no incorpora.

ORIGEN: adaptado del scanner de flujos y del buscador de fuentes de SIWA (`colectores/buscador_flujos_llama.py` y `buscador_llama.py`,
Fundación Sherman Kent, licencia MIT), de donde se tomaron, con su aviso, las funciones de llamada al modelo (Cloudflare Llama primero, Groq de
respaldo, con un modelo por familia y salto al siguiente si se agota la cuota), la comprobación de enlaces y la regla «no inventes». Lo
propio de Ysyry: lee los candidatos del escáner por reglas (`datos/publico/escaner.json`) y los titulares que nombran un lugar del
corredor pero que las reglas no supieron clasificar (`sin_tipo`), en vez de buscar en Google Noticias (cuyos términos limitan su uso a un
lector personal).

QUÉ HACE, EN ORDEN
1. Toma los candidatos y los titulares sin clasificar más recientes (tope por corrida, por la cuota gratuita).
2. Le pasa a un modelo de pesos abiertos sólo el titular, el medio, la fecha y el lugar detectado (todo ya público) y le pide, en JSON:
   si el titular cuenta un hecho ocurrido y real (no una opinión, un anuncio, una nota deportiva ni un hecho futuro), de qué tipo, en qué
   lugar y qué pasó, y si es pertinente al corredor.
3. COMPRUEBA que el enlace responda. Lo que no responde no se anota.
4. Deja un resumen en Markdown para la curaduría. Lo corre un flujo PRIVADO: nada de esto se publica.

LO QUE NO HACE
· No incorpora nada al sitio ni califica: dos fuentes independientes o rótulo «fuente única, no verificado», décimo hombre y dirección.
· No inventa: sólo acepta lo que el modelo puede apoyar en el titular que se le dio; los demás campos van null.
· No usa tokens de Claude. Sin clave de modelo no falla: avisa y termina.

Uso: escaner_modelo.py [ENTRADA.json|URL] [SALIDA.md]"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENTRADA = "https://raw.githubusercontent.com/fundacion-sherman-kent/ysyry/main/datos/publico/escaner.json"
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TOPE = 24             # titulares por corrida: el plan gratuito tiene tope de tokens por minuto
POR_LLAMADA = 4
PAUSA = 25            # segundos entre pedidos


# ───────────── de SIWA (MIT): red, comprobación de enlaces y elección de modelo ─────────────
def pedir_json(url, cabeceras=None, datos=None, espera=45, reintentar_429=True):
    h = {"User-Agent": NAVEGADOR, "Accept": "application/json"}
    h.update(cabeceras or {})
    cuerpo = None
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
        h["Content-Type"] = "application/json"
    for intento in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=h), timeout=espera) as r:
                return json.loads(r.read(6_000_000).decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404) or intento == 4:
                raise
            if e.code == 429 and not reintentar_429:
                raise
            if e.code == 429:
                try:
                    espera_429 = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    espera_429 = 0
                time.sleep(min(max(espera_429, 20), 90))
                continue
        except (urllib.error.URLError, TimeoutError):
            if intento == 4:
                raise
        time.sleep(5 * (intento + 1))


def comprobar(url):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR, "Range": "bytes=0-2047"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            r.read(2048)
            return {"responde": True, "estado": r.status}
    except urllib.error.HTTPError as e:
        return {"responde": e.code in (206, 416), "estado": e.code}
    except Exception as e:  # noqa: BLE001
        return {"responde": False, "estado": type(e).__name__}


def _version(nombre):
    m = re.findall(r"(\d+(?:\.\d+)?)", nombre)
    return float(m[0]) if m else 0.0


def elegir_groq_lista(clave):
    ids = [m["id"] for m in pedir_json("https://api.groq.com/openai/v1/models", {"Authorization": "Bearer " + clave}).get("data", []) if m.get("active", True)]
    ids = [i for i in ids if not re.search(r"guard|prompt|whisper|tts|compound", i, re.I)]
    orden = []
    for patron in (r"llama-4", r"llama-3\.\d-70b", r"llama", r"gpt-oss-120b", r"gpt-oss", r"qwen"):
        hallados = [i for i in ids if re.search(patron, i, re.I)]
        if hallados:
            mejor = sorted(hallados, key=_version, reverse=True)[0]
            if mejor not in orden:
                orden.append(mejor)
    return orden


def elegir_cloudflare(cuenta, token):
    d = pedir_json("https://api.cloudflare.com/client/v4/accounts/%s/ai/models/search?search=llama" % cuenta, {"Authorization": "Bearer " + token})
    nombres = [m.get("name", "") for m in d.get("result", [])]
    nombres = [n for n in nombres if re.search(r"llama", n, re.I) and not re.search(r"guard|vision", n, re.I)]
    for patron in (r"llama-4", r"llama-3\.\d-70b", r"llama"):
        hallados = [n for n in nombres if re.search(patron, n, re.I)]
        if hallados:
            return sorted(hallados, key=_version, reverse=True)[0]
    return None


def conversar(sistema, usuario):
    """(texto, «servicio · modelo»). Llama por Cloudflare primero; Groq de respaldo, recorriendo sus modelos abiertos."""
    groq = os.environ.get("GROQ_API_KEY")
    cuenta, token = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if cuenta and token:
        try:
            modelo = elegir_cloudflare(cuenta, token)
            if modelo:
                d = pedir_json("https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (cuenta, modelo), {"Authorization": "Bearer " + token},
                               {"messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], "temperature": 0, "max_tokens": 2048}, espera=120)
                r = (d.get("result") or {}).get("response", "")
                r = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                if r:
                    return r, "Cloudflare · " + modelo
        except Exception as e:  # noqa: BLE001
            print("  Cloudflare no respondió:", type(e).__name__, str(e)[:100], file=sys.stderr)
    if groq:
        try:
            modelos = elegir_groq_lista(groq)
        except Exception as e:  # noqa: BLE001
            print("  Groq no respondió:", type(e).__name__, str(e)[:100], file=sys.stderr)
            modelos = []
        for modelo in modelos:
            cuerpo = {"model": modelo, "temperature": 0, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
            try:
                try:
                    d = pedir_json("https://api.groq.com/openai/v1/chat/completions", {"Authorization": "Bearer " + groq}, cuerpo, espera=120, reintentar_429=False)
                except urllib.error.HTTPError as e:
                    if e.code != 400:
                        raise
                    cuerpo.pop("response_format")
                    d = pedir_json("https://api.groq.com/openai/v1/chat/completions", {"Authorization": "Bearer " + groq}, cuerpo, espera=120, reintentar_429=False)
                return d["choices"][0]["message"]["content"], "Groq · " + modelo
            except Exception as e:  # noqa: BLE001
                print("  Groq %s no respondió: %s" % (modelo, str(e)[:80]), file=sys.stderr)
                continue
    if not groq and not (cuenta and token):
        raise RuntimeError("No hay clave de Groq ni de Cloudflare cargada en el repositorio.")
    raise RuntimeError("Hay clave, pero ningún servicio ofreció un modelo abierto que responda.")


# ───────────── lo propio de Ysyry ─────────────
SISTEMA = """Sos un analista de fuentes abiertas de Ysyry, una plataforma pública sobre el corredor de la Hidrovía Paraguay-Paraná (Argentina, Bolivia, Brasil, Paraguay y Uruguay).
Te paso titulares de prensa y de organismos, con el medio, la fecha y el lugar que detectó una regla. Tu tarea es SOLO clasificar cada titular.
Reglas estrictas:
- No inventes nada. Usá únicamente lo que dice el titular. Si un dato no está en el titular, poné null.
- "hecho_real": true sólo si el titular cuenta un hecho YA OCURRIDO (decomiso, detención, operativo, asalto o robo, siniestro, bajante, conflicto gremial, medida regulatoria). Es false si es una opinión, un anuncio de algo futuro, una nota deportiva, una nota de espectáculos o una mención sin hecho.
- "pertinente": true sólo si el hecho ocurrió en el corredor (el río Paraná, el Paraguay, el Uruguay o el Río de la Plata, sus puertos y sus ciudades ribereñas, la Triple Frontera o el Alto Paraná) o involucra directamente a su tráfico fluvial. Una nota sobre otra región es false.
- "tipo" es uno de: decomiso, detencion, pirateria, siniestro, navegabilidad, regulatorio, estado, otro, o null.
- "lugar" es el lugar que nombra el titular, o null. "que" resume en una línea qué pasó, sin agregar nada que no esté en el titular.
- Devolvé sólo un JSON: {"resultados":[{"indice":int,"hecho_real":bool,"pertinente":bool,"tipo":str|null,"lugar":str|null,"que":str|null}]} con un resultado por titular."""


def cargar(entrada):
    if str(entrada).startswith("http"):
        return pedir_json(entrada)
    return json.load(open(entrada, encoding="utf-8"))


def seleccionar(d):
    """Primero los candidatos de las reglas con mayor puntaje; después los titulares sin clasificar. Los más recientes antes."""
    cand = sorted(d.get("eventos", []), key=lambda e: (e["fecha"], e["puntaje"]), reverse=True)
    sin = sorted(d.get("sin_tipo", []), key=lambda e: e["fecha"], reverse=True)
    out = []
    for e in cand:
        out.append({"titulo": e["titulo"], "url": e["url"], "medio": e["dominio"], "fecha": e["fecha"], "lugar": ", ".join(e.get("lugares") or []), "origen": "regla: " + ", ".join(r for _, r in e["tipos"])})
    for e in sin:
        out.append({"titulo": e["titulo"], "url": e["url"], "medio": e["dominio"], "fecha": e["fecha"], "lugar": ", ".join(e.get("lugares") or []), "origen": "sin clasificar por las reglas"})
    vistos, res = set(), []
    for x in out:
        if x["url"] not in vistos:
            vistos.add(x["url"])
            res.append(x)
    return res[:TOPE]


def clasificar(items):
    """[(item, resultado del modelo)], más el modelo usado. Un titular que el modelo no devolvió queda sin resultado."""
    out, modelo_usado = [], ""
    for i in range(0, len(items), POR_LLAMADA):
        lote = items[i:i + POR_LLAMADA]
        usuario = "Titulares:\n" + "\n".join("%d. [%s, %s, lugar detectado: %s] %s" % (n, x["medio"], x["fecha"], x["lugar"] or "ninguno", x["titulo"]) for n, x in enumerate(lote))
        texto, modelo_usado = conversar(SISTEMA, usuario)
        m = re.search(r"\{.*\}", texto, re.S)
        try:
            res = {r["indice"]: r for r in json.loads(m.group(0))["resultados"]} if m else {}
        except Exception:
            res = {}
        for n, x in enumerate(lote):
            out.append((x, res.get(n)))
        if i + POR_LLAMADA < len(items):
            time.sleep(PAUSA)
    return out, modelo_usado


def resumen(clasificados, modelo):
    ok, desc = [], 0
    for x, r in clasificados:
        if r and r.get("hecho_real") is True and r.get("pertinente") is True:
            c = comprobar(x["url"])
            if c["responde"]:
                ok.append((x, r))
                continue
        desc += 1
    L = ["# Escáner de Ysyry con modelo: candidatos confirmados por una segunda lectura", "",
         "Modelo: **%s**. Leyó %d titulares ya públicos (titular, medio, fecha y lugar detectado). Confirmó %d como hechos ocurridos y pertinentes con enlace que responde; descartó %d." % (modelo, len(clasificados), len(ok), desc),
         "", "**Ninguno está verificado ni calificado.** Un modelo no es una fuente: sólo ayuda a leer. Cada uno sigue siendo «fuente única, no verificado» hasta que una segunda fuente independiente lo confirme; después, analistas, décimo hombre y dirección.", ""]
    for x, r in ok:
        L.append("- %s · **%s** · %s · %s: «%s» (%s) — %s" % (x["fecha"], r.get("tipo") or "sin tipo", r.get("lugar") or x["lugar"] or "lugar sin dato", r.get("que") or "", x["titulo"][:140], x["medio"], x["url"]))
    return "\n".join(L), len(ok)


def main():
    entrada = sys.argv[1] if len(sys.argv) > 1 else ENTRADA
    salida = sys.argv[2] if len(sys.argv) > 2 else None
    if not (os.environ.get("GROQ_API_KEY") or (os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))):
        print("Falta la clave de un modelo abierto (GROQ_API_KEY, o CLOUDFLARE_ACCOUNT_ID y CLOUDFLARE_API_TOKEN) en los secretos del repositorio. No se hace nada y no falla.")
        return 0
    items = seleccionar(cargar(entrada))
    if not items:
        print("No hay titulares para leer.")
        return 0
    try:
        clasificados, modelo = clasificar(items)
    except RuntimeError as e:
        print("No se pudo consultar el modelo: %s" % e)
        return 0
    md, n = resumen(clasificados, modelo)
    if salida:
        Path(salida).write_text(md + "\n", encoding="utf-8")
    print(md)
    return 10 if n else 0


if __name__ == "__main__":
    sys.exit(main())
