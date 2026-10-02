"""Motor de preguntas con probabilidad: una pregunta binaria con plazo, una banda de probabilidad en el léxico de Kent y un
criterio mecánico que se fijó antes de saber el resultado. Al vencer se resuelve sola contra los datos y entra al marcador,
acierte o no. Es el mismo método que FEMÓNOE aplica a sus alertas, reescrito acá: no se copia código suyo.

Una pregunta sólo llega a `preguntas/` (repositorio público) cuando una persona la escribió, el décimo hombre la impugnó y la
dirección la publicó. El código de este módulo no crea ni modifica preguntas: las lee, las puntúa y las muestra.

Puntaje: Brier = (anunciado − resultado)², con resultado 1 si ocurrió y 0 si no. 0 es perfecto; 0,25 es el de quien dice
siempre «posibilidades parejas». El marcador se muestra «en calibración» hasta reunir 20 preguntas vencidas."""
import html
import json
from datetime import date, datetime
from pathlib import Path

# banda -> probabilidad anunciada (centro de la banda). Los extremos nunca son 0 % ni 100 %.
BANDAS = {"casi con certeza no": 0.03, "muy improbable": 0.12, "improbable": 0.30, "posibilidades parejas": 0.50,
          "probable": 0.70, "muy probable": 0.88, "casi con certeza": 0.97}
MINIMO_CALIBRACION = 20


def cargar(carpeta):
    out = []
    for f in sorted(Path(carpeta).glob("*.json")):
        try:
            q = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if q.get("estado") in ("publicada", "resuelta") and q.get("banda") in BANDAS:
            out.append(q)
    return out


def brier(q):
    if q.get("resultado") not in (True, False):
        return None
    return (BANDAS[q["banda"]] - (1.0 if q["resultado"] else 0.0)) ** 2


def marcador(preguntas):
    res = [q for q in preguntas if q.get("resultado") in (True, False)]
    bs = [brier(q) for q in res]
    return {"vencidas": len(res), "brier_medio": (sum(bs) / len(bs)) if bs else None,
            "aciertos_de_lado": sum(1 for q in res if (BANDAS[q["banda"]] >= 0.5) == q["resultado"])}


def bloque_html(preguntas, hoy):
    e = html.escape
    m = marcador(preguntas)
    abiertas = [q for q in preguntas if q.get("resultado") not in (True, False)]
    cerradas = [q for q in preguntas if q.get("resultado") in (True, False)]
    if not preguntas:
        cuerpo = ('<p class="sub">Todavía no hay ninguna pregunta publicada. Hay un método: cada pregunta es binaria, con plazo, con una banda de probabilidad en el léxico de Kent '
                  'y un criterio mecánico fijado de antemano; la impugna el décimo hombre y la publica la dirección; al vencer se resuelve sola contra los datos y entra al marcador, acierte o no. '
                  'Preferimos dejar este espacio vacío antes que mostrar un número sin respaldo.</p>')
    else:
        filas = []
        for q in abiertas + cerradas:
            vence = q.get("vence", "")
            if q.get("resultado") in (True, False):
                est = "Resuelta: %s · valor observado: %s · Brier %s" % ("ocurrió" if q["resultado"] else "no ocurrió", e(str(q.get("valor_observado", "—"))), ("%.2f" % brier(q)).replace(".", ","))
            else:
                est = "Abierta · vence el %s" % e(vence)
            filas.append('<tr><td><b>%s</b><br>%s</td><td>%s<br><small>anunciado %d %%</small></td><td>%s</td><td>%s</td></tr>'
                         % (e(q["id"]), e(q["enunciado"]), e(q["banda"]), round(100 * BANDAS[q["banda"]]), e(est),
                            e((q.get("disenso") or {}).get("decimo_hombre", "—"))))
        cuerpo = ('<div class="tabla-pulso"><table><thead><tr><th>Pregunta</th><th>Probabilidad</th><th>Estado</th><th>Disenso del décimo hombre</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(filas))
    if m["vencidas"] < MINIMO_CALIBRACION:
        marc = ("Marcador <b>en calibración</b>: %d de %d preguntas vencidas%s. Con menos de %d no se muestra ningún porcentaje de acierto, porque no significaría nada."
                % (m["vencidas"], MINIMO_CALIBRACION, (" · Brier medio provisorio %s (0,25 es el de decir siempre «posibilidades parejas»)" % ("%.2f" % m["brier_medio"]).replace(".", ",")) if m["brier_medio"] is not None else "", MINIMO_CALIBRACION))
    else:
        marc = "Marcador: %d preguntas vencidas · Brier medio %s (0,25 es el de decir siempre «posibilidades parejas»)." % (m["vencidas"], ("%.2f" % m["brier_medio"]).replace(".", ","))
    return ('<div class="prospectiva" id="prospectiva"><h2>Prospectiva · preguntas con probabilidad</h2>%s<p class="sub">%s</p>'
            '<p class="sub">Nada de esto es una predicción de lo que hará un grupo o una persona: son preguntas sobre hechos medibles del corredor. Consultado el %s (UTC).</p></div>'
            % (cuerpo, marc, e(hoy)))
