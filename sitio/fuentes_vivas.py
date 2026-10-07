"""Estado de las fuentes en vivo: qué se lee, cada cuánto está previsto leerlo, cuándo se leyó por última vez y si está al día.
Es la respuesta pública a «¿qué tan en tiempo real es esto?»: sin esconder las fuentes que son diarias o semanales."""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

# (rótulo, archivo relativo a datos/publico o None si viene del historial de AIS, campo de fecha, cadencia prevista en horas, tipo)
FUENTES = [
    ("Posiciones de buques (AIS)", None, None, 1, "Una captura por hora; los robots de GitHub se retrasan a veces"),
    ("Escáner de hechos (RSS de medios y organismos)", "escaner.json", "obtenido", 3, "Candidatos sin verificar"),
    ("Avisos oficiales (INMET, Meteorología de Paraguay, GDACS)", "avisos_oficiales.json", "obtenido", 3, "No incluye el SMN de Argentina ni el INUMET de Uruguay"),
    ("Focos de calor cerca del río (NASA FIRMS)", "focos_corredor.json", "obtenido", 3, "Dos satélites VIIRS"),
    ("Escalas de la Prefectura vía INA (nivel del río, Argentina)", "nivel-rio-ar.json", "obtenido", 24, "Lectura diaria de cada escala"),
    ("Telemetría de la ANA (nivel del río, Brasil)", "nivel-rio-br.json", "obtenido", 6, "Lecturas cada 15 minutos"),
    ("Mareógrafos del Servicio de Hidrografía Naval (Río de la Plata)", "nivel-rio-shn.json", "obtenido", 6, "Alturas horarias"),
    ("Nivel del río, Meteorología de Paraguay", "nivel-rio-py.json", "obtenido", 24, "El organismo actualiza a diario, no en vivo"),
    ("Lista de sanciones OFAC (buques con IMO)", "ofac_buques.json", "obtenido", 24 * 7, "Semanal"),
]


def _edad(iso, ahora):
    try:
        return (ahora - datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600
    except Exception:
        return None


def tabla_html(raiz_datos, ultima_ais, ahora=None):
    e = html.escape
    ahora = ahora or datetime.now(timezone.utc)
    filas = []
    for rotulo, archivo, campo, cadencia, nota in FUENTES:
        iso = ultima_ais if archivo is None else None
        if archivo:
            try:
                iso = json.load(open(Path(raiz_datos) / archivo, encoding="utf-8")).get(campo)
            except Exception:
                iso = None
        edad = _edad(iso, ahora) if iso else None
        if edad is None:
            estado, txt = "sin dato", "sin lectura"
        else:
            estado = "al día" if edad <= max(2 * cadencia, 2) else "retrasada"
            txt = "hace %s" % (("%d min" % round(edad * 60)) if edad < 1.5 else ("%.0f h" % edad if edad < 48 else "%.0f días" % (edad / 24)))
        previsto = ("cada %d h" % cadencia) if cadencia < 24 else ("diaria" if cadencia == 24 else "semanal")
        filas.append("<tr><td>%s</td><td>%s</td><td>%s</td><td><b>%s</b></td><td>%s</td></tr>" % (e(rotulo), e(previsto), e(txt), e(estado), e(nota)))
    return ('<div class="pulso" id="fuentes-vivas"><h2>Fuentes en vivo y qué tan frescas están</h2>'
            '<p class="sub">Qué se lee, cada cuánto está previsto leerlo y cuándo se leyó por última vez. «En tiempo real» depende de cada fuente: unas son por hora, otras diarias y otras semanales, y los robots programados de GitHub se retrasan a veces. '
            'Una fuente «retrasada» pasó el doble de su cadencia sin actualizarse.</p>'
            '<div class="tabla-pulso"><table><thead><tr><th>Fuente</th><th>Cadencia prevista</th><th>Última lectura</th><th>Estado</th><th>Nota</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="sub">Calculado al construir la página (%s UTC).</p></div>' % ("".join(filas), e(ahora.strftime("%Y-%m-%d %H:%M"))))
