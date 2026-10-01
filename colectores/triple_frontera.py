"""Reconocedor de menciones a la Triple Frontera, propio de Ysyry.

Escrito desde cero, sin copiar código de FEMÓNOE — se toma sólo el método
que ya validaron: las tres ciudades, más un filtro de dos pasos contra la
trampa conocida: "Ciudad del Este" también es un centro comercial de
Curridabat, Costa Rica, que se incendió y aparece en cualquier búsqueda del
nombre sin desambiguar.

No reemplaza a FEMÓNOE ni depende de su rama interna: es la medición propia
de Ysyry para el corredor.
"""
import re

CIUDADES = {
    "Puerto Iguazú": {"pais": "AR", "lat": -25.6107508, "lon": -54.5764199},
    "Foz do Iguaçu": {"pais": "BR", "lat": -25.5304023, "lon": -54.5830692},
    "Ciudad del Este": {"pais": "PY", "lat": -25.5169015, "lon": -54.6168645},
}

# Señales de que "Ciudad del Este" es, en realidad, el centro comercial de
# Curridabat (Costa Rica) y no la ciudad paraguaya — primer paso del filtro.
TRAMPA_COSTA_RICA = re.compile(
    r"\b(Curridabat|Costa Rica|centro comercial|mall)\b", re.IGNORECASE
)


def detectar(texto):
    """Devuelve la lista de ciudades de la Triple Frontera mencionadas en
    `texto`, aplicando el filtro de dos pasos para «Ciudad del Este»:
    paso 1, señal de que es la trampa de Costa Rica -> se descarta;
    paso 2, sin esa señal, se acepta pero se marca como no desambiguada del
    todo (un texto corto puede seguir siendo ambiguo sin más contexto)."""
    encontradas = []
    for nombre in CIUDADES:
        if nombre == "Ciudad del Este":
            if re.search(r"\bCiudad del Este\b", texto, re.IGNORECASE):
                if TRAMPA_COSTA_RICA.search(texto):
                    continue  # paso 1: descartado, es la trampa conocida
                encontradas.append({
                    "ciudad": nombre,
                    "desambiguada": False,  # paso 2: aceptada con reserva
                    "nota": "sin señal de Costa Rica, pero no confirmada contra otras fuentes",
                })
        elif re.search(r"\b%s\b" % re.escape(nombre), texto, re.IGNORECASE):
            encontradas.append({"ciudad": nombre, "desambiguada": True, "nota": ""})
    return encontradas


if __name__ == "__main__":
    pruebas = [
        "Un incendio afectó el centro comercial Ciudad del Este en Curridabat, Costa Rica.",
        "La policía de Ciudad del Este, Paraguay, decomisó mercadería de contrabando.",
        "Reunión trilateral entre Puerto Iguazú, Foz do Iguaçu y Ciudad del Este.",
    ]
    for p in pruebas:
        print(p[:60], "->", detectar(p))
