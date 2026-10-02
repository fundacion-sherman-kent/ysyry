"""Consulta OpenStreetMap (Overpass) por puertos, muelles, atracaderos, marinas, rampas y amarraderos a lo largo
del corredor. Se corre a mano, rara vez (los datos cambian despacio): python osm_amarres.py desde sitio/datos/.
Escribe osm_amarres_crudo.json, que NO se versiona (pesa ~1 MB); luego procesar_amarres.py genera amarres_osm.json."""
import json, sys, time, urllib.request, urllib.parse
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'colectores'))
import ais_vivo
EP = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
Q = """[out:json][timeout:120];
(
 nwr["harbour"]({bb});
 nwr["landuse"="port"]({bb});
 nwr["industrial"="port"]({bb});
 nwr["man_made"="pier"]({bb});
 nwr["man_made"="quay"]({bb});
 nwr["amenity"="ferry_terminal"]({bb});
 nwr["leisure"="marina"]({bb});
 nwr["leisure"="slipway"]({bb});
 nwr["waterway"="dock"]({bb});
 nwr["waterway"="boatyard"]({bb});
 nwr["mooring"]({bb});
 nwr["seamark:type"~"harbour|mooring|berth|small_craft_facility"]({bb});
 nwr["name"~"caleta|amarradero|embarcadero|fondeadero|atracadero|varadero|astillero",i]["man_made"]({bb});
);
out center tags;"""
def consulta(bb):
    for ep in EP:
        for intento in range(2):
            try:
                d = urllib.parse.urlencode({'data': Q.format(bb=bb)}).encode()
                r = urllib.request.urlopen(urllib.request.Request(ep, data=d, headers={'User-Agent': 'YsyryFUSK/1.0'}), timeout=180)
                return json.load(r)['elements']
            except Exception as e:
                print('   fallo', ep[:28], str(e)[:60], flush=True); time.sleep(8)
    return None
def partir(b):
    s, w, n, e = b; ms, mw = (s + n) / 2, (w + e) / 2
    return [(s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)]
todo = {}
for nombre, b in ais_vivo.TRAMOS.items():
    print(nombre, flush=True)
    els = consulta('%s,%s,%s,%s' % b)
    if els is None:
        els = []
        for sb in partir(b):
            r = consulta('%s,%s,%s,%s' % sb)
            if r is None: print('   cuadrante sin respuesta'); continue
            els += r
    print('   elementos:', len(els), flush=True)
    for e in els: todo[(e['type'], e['id'])] = e
out = list(todo.values())
json.dump(out, open('osm_amarres_crudo.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('TOTAL únicos:', len(out))
