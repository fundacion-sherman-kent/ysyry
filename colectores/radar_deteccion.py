#!/usr/bin/env python3
"""Detección de objetos brillantes sobre el agua en una imagen de radar Sentinel-1.

Contiene sólo la parte matemática (sin red ni archivos), para poder probarla con
cualquier recorte. Método clásico y simple, deliberadamente conservador:

  1. Máscara de agua: el río calmo devuelve muy poco al radar (~ -20 dB) y la tierra
     bastante más (~ -11 dB), dos modos bien separados. Se umbraliza la imagen suavizada.
  2. Fondo local de agua: media y desvío del retorno del agua en una ventana alrededor
     de cada píxel, calculados SÓLO con píxeles de agua (convolución normalizada).
  3. Candidatos: píxeles claramente más brillantes que ese fondo (CFAR) y fuertes en
     valor absoluto. Se agrupan en objetos conectados.
  4. Contexto: de cada objeto se mide qué fracción de su alrededor es agua. Un buque en
     el canal está rodeado de agua; un edificio, una grúa o un puente de la orilla no.
     Se conservan sólo los rodeados de agua. Los de muelle, a medio rodear, quedan
     aparte: no se afirman como buques.

Qué NO hace, y por qué importa: no distingue un buque de una boya, un pontón o la
pila de un puente en el agua (para eso hay que comparar varias pasadas: lo que no se
mueve entre pasadas es fijo); y no puede decir que un buque tiene el AIS apagado, sólo
que no hay un AIS recibido en ese lugar. Todo lo que sale de acá es una CANDIDATA.
"""
import numpy as np
from scipy import ndimage as ndi

UMBRAL_AGUA_DB = -16.5      # sobre la imagen suavizada 9x9
VENTANA_FONDO = 41          # píxeles (410 m a 10 m/px)
K_CFAR = 6.0                # desvíos por encima del fondo de agua
MINIMO_DB = -8.0            # y un mínimo absoluto: lo más débil es ruido y vegetación; -5 dB perdía buques evidentes, -12 dB dejaba pasar ruido
                            # (en una pasada real, con -12 dB salían 1.145 candidatos y la mediana era -11 dB)
BRILLANTES_MIN = 4          # píxeles realmente brillantes (sin ensanchar) que debe tener el objeto
AREA_MAX = 600              # píxeles de 10 m, ya unidas las manchas: ~6 ha
CUERPO_AGUA_MIN = 40_000    # píxeles (4 km2): un canal, no una laguna del Delta (el río principal se parte en pedazos de ~60.000)
FRACCION_AGUA_MIN = 0.65    # rodeado de agua: candidato en el agua
FRACCION_ORILLA_MIN = 0.30  # entre ambos: junto a la orilla o al muelle


def a_db(lineal):
    return 10.0 * np.log10(np.clip(lineal, 1e-5, None))


def mascara_agua(lineal, valido):
    suave = ndi.uniform_filter(lineal, 9)
    agua = (a_db(suave) < UMBRAL_AGUA_DB) & valido
    agua = ndi.binary_opening(agua, iterations=1)
    # un buque es un "agujero" brillante dentro del agua: se rellena para no perder el contexto
    agua = ndi.binary_closing(agua, structure=np.ones((5, 5)), iterations=1)
    return agua


def fondo_agua(lineal, agua):
    """Media y desvío del retorno del agua en una ventana, usando sólo píxeles de agua."""
    w = agua.astype('float32')
    v = VENTANA_FONDO
    n = ndi.uniform_filter(w, v)
    m = ndi.uniform_filter(np.where(agua, lineal, 0.0), v) / np.maximum(n, 1e-6)
    m2 = ndi.uniform_filter(np.where(agua, lineal ** 2, 0.0), v) / np.maximum(n, 1e-6)
    sd = np.sqrt(np.maximum(m2 - m ** 2, 0.0))
    return m, sd, n


def detectar(lineal, valido=None):
    """lineal: retorno VV en potencia (no dB). Devuelve (lista de objetos, máscara de agua).

    Cada objeto: dict con fila, col (centroide en píxeles), area_px, largo_px, pico_db,
    fraccion_agua y clase ('agua' o 'orilla')."""
    lineal = lineal.astype('float32')
    if valido is None:
        valido = lineal > 0
    agua = mascara_agua(lineal, valido)
    m, sd, n = fondo_agua(lineal, agua)
    cerca_de_agua = ndi.binary_dilation(agua, iterations=6)
    cuerpos, _n = ndi.label(agua)
    tam_cuerpo = np.bincount(cuerpos.ravel())
    brillante = (lineal > m + K_CFAR * sd) & (a_db(lineal) > MINIMO_DB) & (n > 0.15) & cerca_de_agua & valido
    # unir las puntas de un mismo buque (el radar lo muestra como varias manchas)
    objetos_bin = ndi.binary_dilation(brillante, iterations=2)
    etiquetas, cuantos = ndi.label(objetos_bin)
    if cuantos == 0:
        return [], agua
    sl = ndi.find_objects(etiquetas)
    anillo_base = ndi.binary_dilation
    salida = []
    for i, s in enumerate(sl, start=1):
        r0, r1 = max(s[0].start - 14, 0), min(s[0].stop + 14, lineal.shape[0])
        c0, c1 = max(s[1].start - 14, 0), min(s[1].stop + 14, lineal.shape[1])
        local = etiquetas[r0:r1, c0:c1] == i
        area = int(local.sum())
        n_bril = int((brillante[r0:r1, c0:c1] & local).sum())
        if n_bril < BRILLANTES_MIN or area > AREA_MAX:
            continue
        anillo = anillo_base(local, iterations=12) & ~anillo_base(local, iterations=4)
        validos_anillo = valido[r0:r1, c0:c1] & anillo
        if validos_anillo.sum() < 20:
            continue
        frac = float(agua[r0:r1, c0:c1][validos_anillo].mean())
        if frac < FRACCION_ORILLA_MIN:
            continue
        # tamaño del cuerpo de agua que rodea al objeto (el más frecuente en su anillo)
        lab = cuerpos[r0:r1, c0:c1][validos_anillo & agua[r0:r1, c0:c1]]
        lab = lab[lab > 0]
        if lab.size == 0 or tam_cuerpo[np.bincount(lab).argmax()] < CUERPO_AGUA_MIN:
            continue
        rr, cc = np.nonzero(local)
        sub = lineal[r0:r1, c0:c1]
        largo = float(max(rr.max() - rr.min(), cc.max() - cc.min()) + 1)
        salida.append({
            "fila": float(rr.mean() + r0), "col": float(cc.mean() + c0), "area_px": area, "brillantes_px": n_bril,
            "largo_px": largo, "pico_db": float(a_db(sub[local].max())),
            "fraccion_agua": round(frac, 2),
            "clase": "agua" if frac >= FRACCION_AGUA_MIN else "orilla"})
    return salida, agua
