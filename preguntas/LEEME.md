# Preguntas con probabilidad

Acá viven **sólo las preguntas ya publicadas** por la dirección. Los borradores no están en este repositorio.

**Cómo llega una pregunta acá:** nace de un indicio o de una alerta candidata (se discuten en privado) → dos analistas la leen sin
verse y fijan la banda y el plazo → el décimo hombre la impugna con evidencia propia → la dirección cura y la publica agregando su
archivo a esta carpeta. Nadie la publica solo.

**Formato de cada archivo** (`Q-AAAA-NNN.json`):

```json
{
  "id": "Q-2026-001",
  "estado": "publicada",
  "enunciado": "¿El nivel del río en Asunción marcará 0,30 m o menos al menos un día entre el 3 y el 17 de octubre de 2026?",
  "creada": "2026-10-03",
  "vence": "2026-10-17",
  "banda": "posibilidades parejas",
  "confianza": "baja",
  "criterio": {"tipo": "nivel_estacion", "estacion": "Asunción", "operador": "<=", "umbral_m": 0.30, "desde": "2026-10-03", "hasta": "2026-10-17"},
  "disenso": {"decimo_hombre": "Qué sostiene lo contrario, con su evidencia", "dictamen": "publicar"}
}
```

**Bandas** (probabilidad anunciada): casi con certeza no 3 %, muy improbable 12 %, improbable 30 %, posibilidades parejas 50 %,
probable 70 %, muy probable 88 %, casi con certeza 97 %. Nunca 0 % ni 100 %.

**Al vencer** el robot diario (`colectores/resolver_preguntas.py`) lee el historial de niveles y escribe `resultado`,
`valor_observado` y `resuelta_el`. Si faltan lecturas, no resuelve: lo marca y decide la dirección. El puntaje es el de Brier;
el marcador se muestra «en calibración» hasta reunir 20 preguntas vencidas.
