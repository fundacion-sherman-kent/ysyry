"""Se corre desde sitio/datos/. Procesa osm_amarres_crudo.json: clasifica, descarta lo que está lejos del corredor y lo ya cubierto por los puertos principales."""
import json, math, re, datetime
d = json.load(open('mapa_v10.json', encoding='utf-8')); P = json.load(open('proyeccion.json'))
els = json.load(open('osm_amarres_crudo.json', encoding='utf-8'))
def poli(path):
    n = [float(x) for x in re.findall(r'-?\d+\.?\d*', path)]; return list(zip(n[0::2], n[1::2]))
rios = [poli(d['rio_parana']), poli(d['rio_paraguay'])]
def dist_seg(px, py, a, b):
    (x1, y1), (x2, y2) = a, b; dx, dy = x2 - x1, y2 - y1
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
def dist_rio(x, y): return min(dist_seg(x, y, r[i], r[i + 1]) for r in rios for i in range(len(r) - 1))
KM_UNIDAD = 2.57  # km por unidad del mapa (43,25 unidades por grado de latitud)
# el trazado del río sólo cubre el cauce principal: el Delta y el Río de la Plata interior se aceptan por recuadro
def en_delta(lon, lat): return -60.1 <= lon <= -57.4 and -34.95 <= lat <= -33.4
def tipo(t):
    if t.get('landuse') == 'port' or t.get('industrial') == 'port': return 'area_portuaria'
    if t.get('harbour') or str(t.get('seamark:type', '')).startswith('harbour'): return 'puerto'
    if t.get('amenity') == 'ferry_terminal': return 'ferry'
    if t.get('leisure') == 'marina': return 'marina'
    if t.get('waterway') in ('dock', 'boatyard'): return 'darsena'
    if t.get('man_made') == 'quay': return 'atracadero'
    if t.get('leisure') == 'slipway': return 'rampa'
    if t.get('man_made') == 'pier': return 'muelle'
    if t.get('mooring') or 'mooring' in str(t.get('seamark:type', '')) or 'berth' in str(t.get('seamark:type', '')): return 'amarradero'
    return 'otro'
puertos_principales = [(q['nombre'], q['x'], q['y']) for q in d['poi'] if q['clase'] == 'puerto']
sal, desc_lejos, desc_dup, desc_otro = [], 0, 0, 0
for e in els:
    t = e.get('tags', {}); k = tipo(t)
    if k == 'otro': desc_otro += 1; continue
    lon = e.get('lon', e.get('center', {}).get('lon')); lat = e.get('lat', e.get('center', {}).get('lat'))
    if lon is None: continue
    x, y = P['ax'] * lon + P['bx'], P['ay'] * lat + P['by']
    if dist_rio(x, y) * KM_UNIDAD > 8 and not en_delta(lon, lat): desc_lejos += 1; continue
    nombre = (t.get('name') or '').strip()
    if nombre and any(math.hypot(x - px, y - py) * KM_UNIDAD < 0.6 for _, px, py in puertos_principales): desc_dup += 1; continue
    extra = {k2: t[k2] for k2 in ('operator', 'access', 'ref', 'name:es', 'website') if t.get(k2)}
    sal.append({'lon': round(lon, 5), 'lat': round(lat, 5), 't': k, 'n': nombre, 'x': extra})
import collections
c = collections.Counter(s['t'] for s in sal); cn = collections.Counter(s['t'] for s in sal if s['n'])
print('descartados: lejos del corredor', desc_lejos, '| ya cubiertos por los puertos principales', desc_dup, '| otros', desc_otro)
print('quedan', len(sal))
for k, v in c.most_common(): print('  %-16s %5d (con nombre %d)' % (k, v, cn[k]))
cal = [s['n'] for s in sal if re.search(r'caleta|embarcadero|amarradero|fondeadero|atracadero|varadero', s['n'], re.I)]
print('nombres tipo caleta/embarcadero/amarradero/…:', len(cal), cal[:12])
json.dump({'fecha': datetime.date.today().isoformat(), 'fuente': 'OpenStreetMap (© colaboradores, ODbL), consulta de Overpass', 'items': sal},
          open('amarres_osm.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
import os; print('tamaño KB:', os.path.getsize('amarres_osm.json') // 1024)
