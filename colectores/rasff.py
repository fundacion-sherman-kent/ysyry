#!/usr/bin/env python3
"""Alertas de la UE sobre alimentos y piensos (RASFF Window, https://webgate.ec.europa.eu/rasff-window/, datos públicos de la Comisión Europea) cuyo ORIGEN es un país del corredor:
Argentina, Brasil, Paraguay, Bolivia o Uruguay. Es la señal oficial más directa y abierta de contaminación o adulteración de cargas que salen por la hidrovía y los puertos del Plata
(aflatoxinas en maní, salmonela en carne de ave, residuos de plaguicidas, organismos modificados no autorizados, etc.).

Qué es y qué no es: cada notificación es una detección de las autoridades de un país de la UE sobre un producto ya llegado o por llegar a la UE. NO prueba que la contaminación ocurriera durante el
transporte por el río (casi siempre nace en el campo, el acopio o la planta), ni que el producto viajara por la hidrovía, ni dice nada de una empresa en particular (el asunto no la nombra).
El tipo de peligro se clasifica con palabras clave sobre un texto libre: puede equivocarse.

Se bajan hasta DIAS_ATRAS días hacia atrás (la API entrega 100 por página, de la más nueva a la más vieja). Escribe DATOS_DIR/rasff-corredor.json."""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://webgate.ec.europa.eu/rasff-window/backend/public/notification/search/consolidated/"
UA = "Ysyry-FUSK/1.0 (+https://github.com/fundacion-sherman-kent/ysyry)"
PAISES = {"AR": "Argentina", "BR": "Brasil", "PY": "Paraguay", "BO": "Bolivia", "UY": "Uruguay"}
DIAS_ATRAS = 365
PAGINA = 100
MAX_PAGINAS = 120

PELIGROS = [
    ("micotoxinas", "Micotoxinas (aflatoxinas, ocratoxina, etc.)", r"aflatox|ochratox|mycotox|deoxynivalenol|zearalenone|fumonisin|patulin"),
    ("microbiologia", "Microorganismos patógenos (salmonela, listeria, E. coli)", r"salmonell|listeria|e\. ?coli|escherichia|campylobacter|bacillus|vibrio|norovirus|hepatitis|clostridium|staphylococc"),
    ("plaguicidas", "Residuos de plaguicidas", r"pesticide|residue|chlorpyrifos|glyphosate|carbendazim|imidacloprid|acetamiprid|thiamethoxam|clothianidin|fipronil|ethylene oxide|chlormequat|dimethoate|pestyc|chloropir|dimetoat|diafenthiuron|\bndp\b|przekroczeni|maximum residue|\bmrl\b"),
    ("metales", "Metales pesados y contaminantes químicos", r"cadmium|lead\b|mercury|arsenic|heavy metal|dioxin|pcb|3-mcpd|glycidyl|benzo|polycyclic|melamine"),
    ("fraude", "Fraude, adulteración o sustancias no autorizadas", r"adulterat|fraud|illegal|unauthori[sz]ed|undeclared|not authori|banned|prohibited|sudan|counterfeit|mislabel|non dichiarato|suino|not approved|establishment of origin|substituted"),
    ("gmo", "Organismos modificados genéticamente no autorizados", r"genetically modified|\bgmo\b|\bgm\b"),
    ("fisico", "Cuerpos extraños y otros peligros físicos", r"foreign bod|glass|metal fragment|plastic|insect|infest|mould|mold|physical contamination|zanieczyszcz|biologicz"),
    ("conservacion", "Conservación y cadena de frío (temperatura, deterioro)", r"temperature control|preservation|deterioration|spoil|cold chain|defrost|thaw|vacuum seal|rancid|off-odour|off odor"),
    ("veterinario", "Residuos de medicamentos veterinarios", r"veterinary|antibiotic|nitrofuran|chloramphenicol|malachite|enrofloxacin|ractopamine|hormone"),
]


def _norm(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def peligro(asunto):
    t = _norm(asunto)
    for clave, _rotulo, rx in PELIGROS:
        if re.search(rx, t):
            return clave
    return "otro"


def pedir(n):
    cuerpo = {"parameters": {"pageNumber": n, "itemsPerPage": PAGINA, "sortProperty": "ecValidationDate", "sortDirection": "DESC"}}
    r = urllib.request.Request(URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", "User-Agent": UA})
    for intento in range(3):
        try:
            with urllib.request.urlopen(r, timeout=60) as x:
                return json.loads(x.read().decode("utf-8"))
        except Exception as e:
            print("página %d, intento %d: %s" % (n, intento + 1, str(e)[:80]))
            time.sleep(4)
    return None


def main():
    carpeta = Path(os.environ.get("DATOS_DIR", "datos/publico"))
    carpeta.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now(timezone.utc)
    corte = ahora - timedelta(days=DIAS_ATRAS)
    revisadas, hallazgos, llego_al_corte = 0, [], False
    for n in range(1, MAX_PAGINAS + 1):
        d = pedir(n)
        if d is None:
            print("RASFF no respondió en la página %d" % n)
            if n == 1:
                return 1
            break
        lista = d.get("notifications") or []
        if not lista:
            llego_al_corte = True
            break
        for x in lista:
            fecha = datetime.strptime(x["ecValidationDate"][:10], "%d-%m-%Y").replace(tzinfo=timezone.utc)
            if fecha < corte:
                llego_al_corte = True
                break
            revisadas += 1
            origen = [o["isoCode"] for o in (x.get("originCountries") or []) if o.get("isoCode") in PAISES]
            if origen:
                asunto = re.sub(r"\s*//.*$", "", (x.get("subject") or "").strip())      # se queda con el texto en inglés cuando viene traducido
                hallazgos.append({"ref": x["reference"], "fecha": fecha.strftime("%Y-%m-%d"), "asunto": asunto, "origen": origen,
                                  "clasificacion": (x.get("notificationClassification") or {}).get("description"), "riesgo": (x.get("riskDecision") or {}).get("description"),
                                  "categoria": (x.get("productCategory") or {}).get("description"), "peligro": peligro(asunto),
                                  "tipo": (x.get("productType") or {}).get("description")})
        if llego_al_corte:
            break
        time.sleep(1.0)
    if revisadas < 1000:
        print("Sólo %d notificaciones revisadas: no se toca el archivo anterior" % revisadas)
        return 1
    salida = {"obtenido": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "desde": corte.strftime("%Y-%m-%d"), "revisadas": revisadas,
              "fuente": {"nombre": "RASFF Window, Comisión Europea (sistema de alerta rápida para alimentos y piensos)", "url": "https://webgate.ec.europa.eu/rasff-window/screen/search",
                         "nota": "Datos públicos de la Comisión Europea. Cada notificación es una detección de una autoridad de un país de la UE; no prueba dónde ocurrió la contaminación ni nombra empresas. El tipo de peligro se clasifica por palabras clave."},
              "notificaciones": sorted(hallazgos, key=lambda h: h["fecha"], reverse=True)}
    with open(carpeta / "rasff-corredor.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("RASFF: %d notificaciones revisadas desde %s; %d con origen en el corredor" % (revisadas, salida["desde"], len(hallazgos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
