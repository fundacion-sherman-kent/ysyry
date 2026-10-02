import json,sys,time,urllib.request,urllib.parse,os
EP=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter']
Q='[out:json][timeout:90];(way["waterway"="riverbank"]({bb});way["natural"="water"]["water"~"river|canal"]({bb});relation["natural"="water"]["water"~"river|canal"]({bb}););out geom qt;'
S,N,W,E=-35.2,-31.2,-60.95,-57.2
tiles=[]
s=S
while s<N:
    w=W
    while w<E:
        tiles.append((s,w,min(s+1.0,N),min(w+1.0,E))); w+=1.0
    s+=1.0
print(len(tiles),'cuadros',flush=True)
for i,(s,w,n,e) in enumerate(tiles):
    f='t_%d.json'%i
    if os.path.exists(f): continue
    bb='%.2f,%.2f,%.2f,%.2f'%(s,w,n,e); ok=False
    for ep in EP:
        try:
            d=urllib.parse.urlencode({'data':Q.format(bb=bb)}).encode()
            raw=urllib.request.urlopen(urllib.request.Request(ep,data=d,headers={'User-Agent':'YsyryFUSK/1.0'}),timeout=100).read()
            open(f,'wb').write(raw); print(i,bb,len(raw)//1024,'KB',flush=True); ok=True; break
        except Exception as ex: print(i,'fallo',str(ex)[:50],flush=True); time.sleep(6)
    if not ok: open(f,'w').write('{"elements":[],"fallo":true}')
    time.sleep(3)
print('LISTO',flush=True)
