#!/usr/bin/env python3
"""Avisos oficiales en tiempo casi real que afectan la navegación y la vida en el corredor.

Fuentes (todas de acceso libre, sin clave):
  · INMET (Brasil): avisos meteorológicos vigentes y próximos; se conservan los que nombran municipios del corredor (Corumbá, Ladário,
    Porto Murtinho, Cáceres, Foz do Iguaçu, Ponta Porã, Guaíra).
  · Dirección de Meteorología e Hidrología de Paraguay: la página de avisos dice si hay un aviso vigente (se lee el título de la página).
  · GDACS (ONU y Comisión Europea): alertas de desastres del mundo; se conservan las que caen dentro del corredor.
NO consultadas, y declaradas así en el archivo: el Servicio Meteorológico Nacional de Argentina (su API exige una clave) y el INUMET de Uruguay
(sin API pública). Un «sin avisos» sólo vale para las fuentes consultadas.

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
    for nombre, f in (("INMET (Brasil)", inmet), ("Meteorología de Paraguay", dmh), ("GDACS", gdacs)):
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
              "no_consultadas": ["Servicio Meteorológico Nacional de Argentina (su API exige una clave)", "INUMET de Uruguay (sin API pública)"],
              "aviso": "Sólo vale para las fuentes consultadas: «sin avisos» no significa que no haya en los países no consultados."}
    with open(carpeta / "avisos_oficiales.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
