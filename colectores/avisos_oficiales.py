#!/usr/bin/env python3
"""Avisos oficiales en tiempo casi real que afectan la navegación y la vida en el corredor.

Fuentes (todas de acceso libre, sin clave):
  · INMET (Brasil): avisos meteorológicos vigentes y próximos; se conservan los que nombran municipios del corredor (Corumbá, Ladário,
    Porto Murtinho, Cáceres, Foz do Iguaçu, Ponta Porã, Guaíra).
  · Dirección de Meteorología e Hidrología de Paraguay: la página de avisos dice si hay un aviso vigente (se lee el título de la página).
  · GDACS (ONU y Comisión Europea): alertas de desastres del mundo; se conservan las que caen dentro del corredor.
  · Servicio Meteorológico Nacional de Argentina (SMN): feed GeoRSS de avisos (licencia CC BY 4.0, sin clave); se conservan los que tocan provincias
    del corredor con un vértice del polígono dentro de la franja Paraná-Paraguay-Uruguay. (Su API de pronósticos sí exige clave: no se usa.)
NO consultado, y declarado así en el archivo: el INUMET de Uruguay (sin API pública). Un «sin avisos» sólo vale para las fuentes consultadas.

Escribe DATOS_DIR/avisos_oficiales.json."""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (compatible; YsyryFUSK/1.0; +https://github.com/fundacion-sherman-kent/ysyry)"
CAJA = (-36.5, -71.5, -15.0, -51.8)
MUNICIPIOS = {"Corumbá - MS": "Corumbá", "Ladário - MS": "Ladário", "Porto Murtinho - MS": "Porto Murtinho", "Cáceres - MT": "Cáceres",
              "Foz do Iguaçu - PR": "Foz do Iguaçu", "Ponta Porã - MS": "Ponta Porã", "Guaíra - PR": "Guaíra"}


def bajar(url, t=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=t) as r:
        return r.read().decode("utf-8-sig", "replace")


def inmet():
    d = json.loads(bajar("https://apiprevmet3.inmet.gov.br/avisos/ativos"))
    out = []
    for a in (d.get("hoje") or []) + (d.get("futuro") or []):
        muni = a.get("municipios") or ""
        tocados = [v for k, v in MUNICIPIOS.items() if k in muni]
        if not tocados:
            continue
        out.append({"fuente": "INMET (Brasil)", "pais": "BRA", "fenomeno": a.get("descricao", ""), "severidad": a.get("severidade", ""), "color": a.get("aviso_cor", ""),
                    "inicio": (a.get("data_inicio") or "")[:10] + " " + (a.get("hora_inicio") or ""), "fin": (a.get("data_fim") or "")[:10] + " " + (a.get("hora_fim") or ""),
                    "lugares": tocados, "riesgos": (" ".join(a["riscos"]) if isinstance(a.get("riscos"), list) else (a.get("riscos") or ""))[:300], "id": "inmet-%s" % a.get("id_aviso")})
    return out


def dmh():
    t = bajar("https://www.meteorologia.gov.py/avisos/")
    m = re.search(r"twitter:title' content='([^']*)'", t)
    titulo = m.group(1).strip() if m else ""
    if not titulo:
        raise ValueError("la página cambió: no se encontró el título")
    if re.search(r"no hay aviso", titulo, re.I):
        return []
    return [{"fuente": "Dirección de Meteorología e Hidrología (Paraguay)", "pais": "PRY", "fenomeno": titulo[:200], "severidad": "", "color": "", "inicio": "", "fin": "",
             "lugares": ["Paraguay"], "riesgos": "", "id": "dmh-vigente"}]


PROVINCIAS_AR = ("FORMOSA", "CHACO", "CORRIENTES", "MISIONES", "SANTA FE", "ENTRE RIOS", "BUENOS AIRES", "CIUDAD AUTONOMA", "CAPITAL FEDERAL")
FRANJA_AR = (-35.3, -61.5, -24.0, -53.0)      # lat mín, lon mín, lat máx, lon máx: de Posadas y Formosa al Delta y el Plata


def smn():
    t = bajar("https://ssl.smn.gob.ar/feeds/avisocorto_GeoRSS.xml")
    if "<item>" not in t and "<channel>" not in t:
        raise ValueError("el feed cambió")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", t, re.S):
        tit = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", it, re.S)
        desc = re.search(r"<description>\s*<!\[CDATA\[(.*?)\]\]>", it, re.S)
        fecha = re.search(r"<dc:date>([^<]+)", it)
        poli = re.search(r"<georss:polygon>([^<]+)", it)
        if not (tit and desc):
            continue
        cuerpo = desc.group(1)
        fen = re.search(r"<b>(.*?)</b>", cuerpo)
        fenomeno = re.sub(r"\s+", " ", fen.group(1)).strip() if fen else tit.group(1)
        provs = [re.sub(r"\s+", " ", p).strip() for p in re.findall(r"<b>([A-ZÁÉÍÓÚÑ .]+):</b>", cuerpo)]
        provs_corredor = [p for p in provs if any(k in p.upper().replace("Ó", "O").replace("Í", "I") for k in PROVINCIAS_AR)]
        if not provs_corredor:
            continue
        if poli:
            n = [float(x) for x in poli.group(1).split()]
            pts = list(zip(n[0::2], n[1::2]))
            if not any(FRANJA_AR[0] <= la <= FRANJA_AR[2] and FRANJA_AR[1] <= lo <= FRANJA_AR[3] for la, lo in pts):
                continue
        lugares = re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/>", "; ", cuerpo.split("Departamentos:")[-1]))
        lugares = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", lugares)).strip(" ;")[:300]
        num = re.search(r"N° (\d+)", tit.group(1))
        out.append({"fuente": "Servicio Meteorológico Nacional (Argentina)", "pais": "ARG", "fenomeno": fenomeno[:200], "severidad": "", "color": "",
                    "inicio": fecha.group(1)[:16].replace("T", " ") if fecha else "", "fin": "", "lugares": [lugares] if lugares else provs_corredor,
                    "riesgos": "", "id": "smn-%s" % (num.group(1) if num else tit.group(1)[:30])})
    return out


def gdacs():
    t = bajar("https://www.gdacs.org/xml/rss.xml")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", t, re.S):
        la, lo = re.search(r"<geo:lat>([^<]+)", it), re.search(r"<geo:long>([^<]+)", it)
        if not (la and lo):
            continue
        lat, lon = float(la.group(1)), float(lo.group(1))
        if CAJA[0] <= lat <= CAJA[2] and CAJA[1] <= lon <= CAJA[3]:
            tit = re.search(r"<title>(.*?)</title>", it, re.S).group(1).strip()
            lk = re.search(r"<link>(.*?)</link>", it, re.S)
            out.append({"fuente": "GDACS (ONU y Comisión Europea)", "pais": "", "fenomeno": tit[:200], "severidad": "", "color": "", "inicio": "", "fin": "",
                        "lugares": ["%.2f, %.2f" % (lat, lon)], "riesgos": "", "id": "gdacs-" + (lk.group(1).strip()[-20:] if lk else tit[:20]), "lat": lat, "lon": lon})
    return out


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    avisos, fuentes = [], []
    for nombre, f in (("INMET (Brasil)", inmet), ("Meteorología de Paraguay", dmh), ("SMN (Argentina)", smn), ("GDACS", gdacs)):
        try:
            r = f()
            avisos += r
            fuentes.append({"nombre": nombre, "ok": True, "avisos_en_el_corredor": len(r)})
            print("%-26s ok, %d avisos en el corredor" % (nombre, len(r)))
        except Exception as e:
            fuentes.append({"nombre": nombre, "ok": False, "error": str(e)[:100]})
            print("%-26s falló: %s" % (nombre, str(e)[:80]))
    if not any(x["ok"] for x in fuentes):
        print("Ninguna fuente respondió: no se toca el archivo anterior")
        return 1
    salida = {"obtenido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "fuentes": fuentes, "avisos": avisos,
              "no_consultadas": ["INUMET de Uruguay (sin API pública)"],
              "aviso": "Sólo vale para las fuentes consultadas: «sin avisos» no significa que no haya en los países no consultados."}
    with open(carpeta / "avisos_oficiales.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
