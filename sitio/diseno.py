"""Capa de diseño y movimiento de la página: todo con la paleta cerrada de Ysyry (variables --acento, --naranja, --azul-*, --gris-acero, --papel, --linea),
mejora progresiva (sin JavaScript la página se ve igual que antes) y respetando «reducir movimiento» del sistema. Nada acá cambia ni inventa datos: sólo presenta los que ya están en la página.

Contiene: barra de progreso de lectura, río animado en el encabezado, cifras que cuentan hacia arriba, aparición escalonada al hacer scroll, tarjetas interactivas por zona
(armadas a partir de la tabla «Pulso por zona», que queda debajo para quien la quiera) que llevan el mapa a esa zona, y un recorrido guiado por las cinco zonas."""
import json
import re

import pulso as _pulso

CSS = r"""
/* ===== capa de diseño (sitio/diseno.py) ===== */
.progreso{position:fixed;top:0;left:0;height:3px;width:100%;transform-origin:0 50%;transform:scaleX(0);background:var(--acento);z-index:80;pointer-events:none}
.hero{position:relative;isolation:isolate;overflow:hidden}
.hero-rio{position:absolute;right:-4%;top:-10%;width:min(62%,640px);height:130%;z-index:-1;opacity:.55;pointer-events:none}
.hero-rio path{fill:none;stroke:var(--acento);stroke-width:1.6;stroke-linecap:round;opacity:.32}
.hero-rio path.f{stroke-dasharray:3 14;opacity:.55}
.hero h1 .pal{display:inline-block}
.metrica{transition:background .25s ease}
.metrica:hover{background:color-mix(in srgb,var(--acento) 7%,transparent)}
.familia-tab{transition:background .2s ease,border-color .2s ease,color .2s ease,transform .2s ease,box-shadow .2s ease}
.familia-tab:hover{border-color:var(--acento);transform:translateY(-1px)}
.familia-tab.activa{box-shadow:0 4px 14px color-mix(in srgb,var(--acento) 38%,transparent)}
svg.mapa .clicable{transition:filter .15s ease}
svg.mapa .clicable:hover{filter:drop-shadow(0 0 3px var(--naranja))}
.panel{transition:transform .35s cubic-bezier(.2,.8,.2,1),opacity .25s ease}

/* tarjetas por zona */
.zonas-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:14px 0 18px}
.zc{background:var(--papel);border:1px solid var(--linea);border-radius:14px;padding:16px 16px 14px;display:flex;flex-direction:column;gap:6px;position:relative;overflow:hidden;
  cursor:pointer;text-align:left;font-family:inherit;color:var(--fg);transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease}
.zc::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acento);transform:scaleY(0);transform-origin:50% 0;transition:transform .3s ease}
.zc:hover,.zc:focus-visible{transform:translateY(-3px);border-color:var(--acento);box-shadow:0 10px 26px color-mix(in srgb,var(--acento) 18%,transparent);outline:none}
.zc:hover::before,.zc:focus-visible::before{transform:scaleY(1)}
.zc .zn{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--gris-acero);font-weight:700}
.zc .zt{font-size:15px;font-weight:700;line-height:1.25}
.zc .zb{font-size:34px;font-weight:800;line-height:1;color:var(--acento-texto);margin-top:4px;font-variant-numeric:tabular-nums}
.zc .zk{font-size:11.5px;color:var(--gris-acero)}
.zc svg{max-width:100%;height:auto}
.zc .zchips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.zc .zchip{font-size:11.5px;font-weight:700;border-radius:999px;padding:3px 9px;border:1px solid var(--linea);background:var(--bg)}
.zc .zchip.sube{border-color:var(--acento);color:var(--acento-texto)}
.zc .zchip.baja{border-color:var(--naranja)}
.zc .zir{font-size:12px;font-weight:700;color:var(--acento-texto);margin-top:6px;display:flex;align-items:center;gap:6px}
.zc .zir i{display:inline-block;transition:transform .25s ease;font-style:normal}
.zc:hover .zir i{transform:translateX(4px)}
details.tabla-det{margin:6px 0 4px}
details.tabla-det>summary{cursor:pointer;font-weight:700;font-size:13px;color:var(--acento-texto);padding:8px 0;list-style:none}
details.tabla-det>summary::before{content:"▸ ";display:inline-block;transition:transform .2s ease}
details.tabla-det[open]>summary::before{transform:rotate(90deg)}

/* libro de indicios */
.libro{margin:16px 0 8px}
.lib-barra{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;align-items:center}
.lib-f,.lib-ab{font-family:inherit;font-size:12.5px;font-weight:700;border-radius:999px;padding:6px 14px;cursor:pointer;border:1px solid var(--linea);background:var(--papel);color:var(--fg);transition:background .2s ease,border-color .2s ease,transform .2s ease}
.lib-f small{opacity:.7;margin-left:4px}
.lib-f:hover,.lib-ab:hover{border-color:var(--acento);transform:translateY(-1px)}
.lib-f.activa{background:var(--acento);border-color:var(--acento);color:var(--acento-sobre)}
.lib-ab{margin-left:auto;background:transparent;border-color:var(--gris-acero)}
details.lz{border:1px solid var(--linea);border-radius:14px;background:var(--papel);margin-bottom:10px;overflow:hidden;transition:border-color .25s ease,box-shadow .25s ease}
details.lz[open]{border-color:var(--acento);box-shadow:0 8px 24px color-mix(in srgb,var(--acento) 12%,transparent)}
details.lz>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:auto 1fr auto;gap:2px 14px;align-items:center;padding:14px 16px}
details.lz>summary::-webkit-details-marker{display:none}
details.lz>summary::before{content:"";grid-row:1/3;width:9px;height:9px;border-right:2px solid var(--acento);border-bottom:2px solid var(--acento);transform:rotate(-45deg);transition:transform .25s ease;margin-right:2px}
details.lz[open]>summary::before{transform:rotate(45deg)}
.lz-n{font-weight:800;font-size:16px;grid-column:2}
.lz-c{grid-column:3;grid-row:1;font-size:12px;font-weight:700;color:var(--gris-acero);text-align:right}
.lz-d{grid-column:2;grid-row:2;font-size:12px;color:var(--gris-acero)}
.lz-ch{grid-column:3;grid-row:2;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.lz-vacio{padding:0 16px 14px;margin:0}
.lz-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:4px 16px 16px}
.ic{border:1px solid var(--linea);border-left:3px solid var(--linea);border-radius:10px;padding:12px 14px;background:var(--bg);display:flex;flex-direction:column;gap:6px;transition:transform .2s ease,box-shadow .2s ease}
.ic[data-nivel="fuerte"]{border-left-color:var(--azul-profundo)}
.ic[data-nivel="corroborado"]{border-left-color:var(--acento)}
.ic:hover{transform:translateY(-2px);box-shadow:0 6px 18px color-mix(in srgb,var(--acento) 14%,transparent)}
.ic-h{display:flex;justify-content:space-between;gap:8px;align-items:center}
.ic-tipo{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--gris-acero);font-weight:700}
.ic h4{margin:0;font-size:14.5px;line-height:1.3}
.ic-t{margin:0;font-size:13px;line-height:1.5}
.ic-aviso{margin:0;font-size:11.5px;color:var(--gris-acero);font-style:italic}
.ic-d{font-size:12.5px}
.ic-d>summary{cursor:pointer;font-weight:700;color:var(--acento-texto);font-size:12px;padding:4px 0}
.ic-d p{margin:6px 0;line-height:1.5}
.ic-nd{color:var(--gris-acero)}
.ic.oculto,details.lz.oculto{display:none}
@media (max-width:640px){details.lz>summary{grid-template-columns:auto 1fr}.lz-c,.lz-ch{grid-column:2;grid-row:auto;justify-content:flex-start;text-align:left}.lz-grid{grid-template-columns:1fr}.lib-ab{margin-left:0}}

/* barra superior en la línea de FEMÓNOE: una sola fila, nombre en mayúsculas espaciadas con el color de la plataforma, estado a la derecha */
.topbar-in{flex-wrap:nowrap;padding:12px 24px;gap:16px}
.brand{flex:0 1 auto}
.inicio .nombre{text-transform:uppercase;letter-spacing:.14em;font-size:17.3px;color:var(--acento);margin-bottom:3px}
.inicio small{text-transform:none;font-size:11.7px;letter-spacing:.04em;line-height:1.3;white-space:nowrap}
.tema{white-space:nowrap}
.franja-derecha{flex-wrap:nowrap;gap:22px}
.topbar nav{gap:20px}
.topbar nav a{font-size:12.5px;white-space:nowrap}
.estado-top{font-size:13px;color:var(--gris-acero);white-space:nowrap}
.estado-top b{color:var(--fg);font-variant-numeric:tabular-nums}
@media (max-width:1500px){.topbar nav{display:none}}
@media (max-width:1100px){.ultima{display:none}}
@media (max-width:900px){.estado-top{display:none}}
@media (max-width:560px){.inicio small{display:none}.topbar-in{flex-wrap:wrap}}

/* vista Seguridad del mapa */
.fam-grupo{flex-basis:100%;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--gris-acero);font-weight:700;margin:6px 0 -2px}
.fam-grupo:first-child{margin-top:0}
svg.fam-seguridad .solo-fam{display:inline}
svg.fam-seguridad .flujo-g{opacity:.38;transition:opacity .2s ease}
svg.fam-seguridad .flujo-g:hover{opacity:1}
svg.fam-seguridad .dim{opacity:.16!important}
svg.fam-seguridad .esc-g,svg.fam-seguridad .frontera-g{filter:drop-shadow(0 0 4px color-mix(in srgb,var(--naranja) 70%,transparent))}
.seg-hoy{margin:20px 0 4px}
.seg-hoy h2{font-size:15px;letter-spacing:.06em;text-transform:uppercase;margin:0 0 2px;color:var(--gris-acero)}
.seg-hoy .sub{font-size:12.5px;color:var(--gris-acero);margin:0 0 10px;max-width:90ch}
.seg-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:10px}
.sc{font-family:inherit;text-align:left;cursor:pointer;color:var(--fg);background:var(--papel);border:1px solid var(--linea);border-left:3px solid var(--acento);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:2px;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}
.sc:hover,.sc:focus-visible{transform:translateY(-2px);border-color:var(--acento);box-shadow:0 8px 22px color-mix(in srgb,var(--acento) 16%,transparent);outline:none}
.sc.senal{border-left-color:var(--naranja)}
.sc .sn{font-size:28px;font-weight:800;line-height:1.05;font-variant-numeric:tabular-nums}
.sc .sk{font-size:12.5px;font-weight:700;line-height:1.3}
.sc .sv{font-size:11px;color:var(--gris-acero);margin-top:3px}
.lu-box{margin-top:14px;border:1px solid var(--linea);border-radius:14px;background:var(--papel);padding:14px 16px}
.lu-box h3{margin:0;font-size:15px}
.lu-box .sub{font-size:12px;color:var(--gris-acero);margin:2px 0 8px;max-width:90ch}
.lu-lista{list-style:none;margin:0;padding:0}
.lu{width:100%;display:grid;grid-template-columns:46px 118px 1fr auto auto 18px;gap:6px 12px;align-items:center;text-align:left;font-family:inherit;color:var(--fg);background:transparent;border:0;border-top:1px solid var(--linea);padding:9px 4px;cursor:pointer;transition:background .2s ease}
.lu:hover,.lu:focus-visible{background:color-mix(in srgb,var(--acento) 8%,transparent);outline:none}
.lu-f{font-weight:800;font-variant-numeric:tabular-nums;font-size:13px}
.lu-t{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;font-weight:700;color:var(--acento-texto);border:1px solid var(--acento);border-radius:999px;padding:2px 8px;text-align:center;white-space:nowrap}
.lu-x{font-size:13px;line-height:1.35}.lu-x b{font-weight:500}.lu-x{color:var(--fg)}
.lu-l{font-size:12px;color:var(--gris-acero);white-space:nowrap}
.lu-e{font-size:11px;font-weight:700;color:var(--gris-acero);border:1px dashed var(--gris-acero);border-radius:999px;padding:2px 8px;white-space:nowrap}
.lu i{font-style:normal;color:var(--acento);transition:transform .2s ease}.lu:hover i{transform:translateX(3px)}
.lu-mas>summary{cursor:pointer;font-weight:700;font-size:12.5px;color:var(--acento-texto);padding:8px 4px;list-style:none;border-top:1px solid var(--linea)}
@media (max-width:760px){.lu{grid-template-columns:44px 1fr 18px;grid-template-areas:"f t i" "x x x" "l e e"}.lu-f{grid-area:f}.lu-t{grid-area:t;justify-self:start}.lu-x{grid-area:x}.lu-l{grid-area:l}.lu-e{grid-area:e;justify-self:start}.lu i{grid-area:i}}

/* recorrido guiado */
.mapa-cab .tour-btn{width:auto;min-width:0;background:transparent;border:1px solid var(--gris-acero);color:#F9F9F7;border-radius:999px;padding:0 14px;height:32px;font-weight:700;font-size:12px;cursor:pointer;font-family:inherit;margin:0 8px;transition:background .2s ease,border-color .2s ease}
.mapa-cab .tour-btn:hover{border-color:var(--acento);background:color-mix(in srgb,var(--acento) 25%,transparent)}
.tour-card{position:absolute;left:18px;bottom:18px;max-width:min(360px,calc(100% - 36px));background:color-mix(in srgb,var(--azul-profundo) 88%,transparent);color:#F9F9F7;border:1px solid var(--acento);border-radius:14px;
  padding:14px 16px;z-index:5;backdrop-filter:blur(6px);animation:tourIn .4s cubic-bezier(.2,.8,.2,1) both}
.tour-card .tn{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#C6C6C5;font-weight:700}
.tour-card .tt{font-size:17px;font-weight:800;margin:2px 0 4px}
.tour-card p{margin:0 0 8px;font-size:13px;line-height:1.45;color:#C6C6C5}
.tour-card .tb{display:flex;align-items:center;gap:8px}
.tour-card button{font-family:inherit;font-weight:700;font-size:12px;border-radius:999px;padding:6px 12px;cursor:pointer;border:1px solid var(--acento);background:var(--acento);color:var(--acento-sobre)}
.tour-card button.sec{background:transparent;color:#F9F9F7;border-color:var(--gris-acero)}
.tour-card .pts{display:flex;gap:5px;margin-left:auto}
.tour-card .pts i{width:7px;height:7px;border-radius:50%;background:var(--gris-acero);transition:background .3s ease,transform .3s ease}
.tour-card .pts i.on{background:var(--acento);transform:scale(1.35)}
@keyframes tourIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

@media (prefers-reduced-motion:no-preference){
  .rv{opacity:0;transform:translateY(16px);transition:opacity .7s ease,transform .7s cubic-bezier(.2,.8,.2,1);transition-delay:var(--rd,0s)}
  .rv.rv-in{opacity:1;transform:none}
  .hero-rio path.f{animation:rioFluye 9s linear infinite}
  .hero-rio path.f.b{animation-duration:14s}
  .hero h1 .pal{opacity:0;transform:translateY(.5em);animation:palIn .7s cubic-bezier(.2,.8,.2,1) forwards;animation-delay:var(--pd,0s)}
  @keyframes rioFluye{to{stroke-dashoffset:-34}}
  @keyframes palIn{to{opacity:1;transform:none}}
}
@media (prefers-reduced-motion:reduce){.tour-card{animation:none}}
@media print{.rv{opacity:1!important;transform:none!important}.progreso,.hero-rio,.tour-btn,.tour-card{display:none!important}}
@media (max-width:640px){.zc .zb{font-size:28px}.tour-card{left:10px;right:10px;bottom:10px;max-width:none}}
"""

JS = r"""
/* ===== capa de diseño (sitio/diseno.py): mejora progresiva ===== */
(function(){
  const REDUCIDO = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ZT = __ZT__;
  function $(s, r){ return (r||document).querySelector(s); }

  // barra de progreso de lectura
  const barra = document.createElement("div"); barra.className = "progreso"; document.body.appendChild(barra);
  let pend = false;
  function progreso(){ pend = false; const h = document.documentElement.scrollHeight - window.innerHeight; barra.style.transform = "scaleX(" + (h > 0 ? Math.min(1, window.scrollY / h) : 0) + ")"; }
  window.addEventListener("scroll", function(){ if (!pend){ pend = true; requestAnimationFrame(progreso); } }, {passive:true});

  // río animado en el encabezado y titular palabra por palabra
  const hero = $(".hero");
  if (hero){
    const NS = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(NS, "svg"); s.setAttribute("class", "hero-rio"); s.setAttribute("viewBox", "0 0 400 300"); s.setAttribute("preserveAspectRatio", "xMaxYMid slice"); s.setAttribute("aria-hidden", "true");
    [["M-10 40 C 90 10, 130 120, 220 100 S 330 190, 410 150", ""], ["M-10 90 C 80 60, 150 170, 230 150 S 340 240, 410 200", "f"], ["M-10 140 C 100 110, 140 220, 240 200 S 330 280, 410 250", "f b"]].forEach(function(d){
      const p = document.createElementNS(NS, "path"); p.setAttribute("d", d[0]); if (d[1]) p.setAttribute("class", d[1]); s.appendChild(p);
    });
    hero.insertBefore(s, hero.firstChild);
    const h1 = $("h1", hero);
    if (h1 && !REDUCIDO){
      const txt = h1.textContent; h1.setAttribute("aria-label", txt); h1.textContent = "";
      txt.split(" ").forEach(function(w, i){
        const sp = document.createElement("span"); sp.className = "pal"; sp.setAttribute("aria-hidden", "true"); sp.style.setProperty("--pd", (0.08 * i + 0.1) + "s"); sp.textContent = w;
        h1.appendChild(sp); h1.appendChild(document.createTextNode(" "));
      });
    }
  }

  // cifras que cuentan hacia arriba al entrar en pantalla
  function contar(el){
    const m = /^([+\-]?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(.*)$/.exec(el.textContent.trim());
    if (!m || REDUCIDO) return;
    const dec = m[3] ? m[3].length : 0, fin = parseFloat(m[2].replace(/\./g, "") + (m[3] ? "." + m[3] : ""));
    const t0 = performance.now(), D = 1100;
    function fmt(v){ return m[1] + v.toLocaleString("es-AR", {minimumFractionDigits:dec, maximumFractionDigits:dec}) + m[4]; }
    (function paso(t){ const k = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(fin * e); if (k < 1) requestAnimationFrame(paso); else el.textContent = fmt(fin); })(t0);
  }
  if ("IntersectionObserver" in window){
    const io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ contar(e.target); io.unobserve(e.target); } }); }, {threshold:.6});
    document.querySelectorAll(".metrica .n").forEach(function(n){ io.observe(n); });

    // aparición escalonada al hacer scroll (sólo con movimiento permitido)
    if (!REDUCIDO){
      const rv = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("rv-in"); rv.unobserve(e.target); } }); }, {rootMargin:"0px 0px -6% 0px", threshold:0});
      document.querySelectorAll(".pulso, .prospectiva, .metodo, .leyenda, .zc").forEach(function(el, i){
        if (el.getBoundingClientRect().top < window.innerHeight) return;      // lo que ya se ve no se esconde
        el.classList.add("rv"); el.style.setProperty("--rd", ((i % 4) * 0.07) + "s"); rv.observe(el);
      });
    }
  }

  // tarjetas por zona, armadas desde la tabla «Pulso por zona»
  const cont = $("#pulso-zonas"), tabla = cont && $("table", cont);
  function irZona(i){
    const z = ZT[i]; if (!z) return;
    const mapa = $("#mapa"); if (mapa) mapa.scrollIntoView({behavior: REDUCIDO ? "auto" : "smooth", block:"start"});
    if (window.__volar) setTimeout(function(){ window.__volar(z.x, z.y, z.w, REDUCIDO ? 0 : 1600); }, REDUCIDO ? 0 : 450);
  }
  if (tabla){
    const filas = tabla.querySelectorAll("tbody tr"), grid = document.createElement("div"); grid.className = "zonas-cards";
    filas.forEach(function(tr, i){
      const c = tr.children; if (!ZT[i]) return;
      const nombre = ((c[0].querySelector("b, strong") || c[0].firstChild).textContent || "").trim() || ZT[i].nombre;
      if (c.length < 7){      // zona sin datos en esta captura: se muestra igual, rotulada
        const v = document.createElement("button"); v.type = "button"; v.className = "zc"; v.setAttribute("aria-label", "Ver " + nombre + " en el mapa");
        v.innerHTML = '<span class="zn">Zona ' + (i + 1) + '</span><span class="zt"></span><span class="zb">—</span><span class="zk">sin datos en esta captura</span><span class="zchips"><span class="zchip">Sin datos</span></span><span class="zir">Ver en el mapa <i>→</i></span>';
        v.querySelector(".zt").textContent = nombre; v.dataset.b = "—"; v.addEventListener("click", function(){ irZona(i); }); grid.appendChild(v); return;
      }
      const b = document.createElement("button"); b.type = "button"; b.className = "zc"; b.setAttribute("aria-label", "Ver " + nombre + " en el mapa");
      const num = (c[1].textContent.match(/^\s*([\d.,]+)/) || [,"—"])[1], barras = c[1].querySelector("svg");
      const ahora = c[3].textContent.trim().split(" · ")[0].replace(/\s*\(.*?\)\s*/g, " ").trim(), cmp = c[5].textContent.trim(), hechos = c[6].textContent.trim();
      const pct = /([+\-−–]?\d+[\.,]?\d*)\s*%/.exec(cmp), signo = pct ? (/^[\-−–]/.test(pct[1]) ? "baja" : "sube") : "";
      b.innerHTML = '<span class="zn">Zona ' + (i + 1) + '</span><span class="zt"></span><span class="zb"></span><span class="zk">buques por captura (mediana)</span><span class="zbar"></span><span class="zchips"></span><span class="zir">Ver en el mapa <i>→</i></span>';
      b.querySelector(".zt").textContent = nombre; b.querySelector(".zb").textContent = num; b.dataset.b = num;
      if (barras) b.querySelector(".zbar").appendChild(barras.cloneNode(true));
      const chips = b.querySelector(".zchips");
      [[ahora, ""], [pct ? (signo === "baja" ? "▼ " : "▲ ") + pct[0].trim() + " vs. su historia" : "", signo], [/^ninguno/i.test(hechos) ? "" : "Hechos informados", ""]].forEach(function(x){
        if (!x[0]) return; const s = document.createElement("span"); s.className = "zchip " + x[1]; s.textContent = x[0]; chips.appendChild(s);
      });
      b.addEventListener("click", function(){ irZona(i); });
      grid.appendChild(b);
    });
    if (grid.children.length){
      const det = document.createElement("details"); det.className = "tabla-det";
      det.innerHTML = "<summary>Ver la tabla completa con todas las columnas</summary>";
      const caja = tabla.closest(".tabla-pulso") || tabla.parentNode; caja.parentNode.insertBefore(grid, caja); caja.parentNode.insertBefore(det, caja); det.appendChild(caja);
    }
  }

  // libro de indicios: filtro por nivel de evidencia y abrir/cerrar todas las zonas
  const libro = $(".libro");
  if (libro){
    const fs = libro.querySelectorAll(".lib-f");
    fs.forEach(function(b){ b.addEventListener("click", function(){
      fs.forEach(function(x){ x.classList.remove("activa"); }); b.classList.add("activa");
      const f = b.dataset.f;
      libro.querySelectorAll(".ic").forEach(function(c){ c.classList.toggle("oculto", !!f && c.dataset.nivel !== f); });
      libro.querySelectorAll("details.lz").forEach(function(z){
        const hay = z.querySelectorAll(".ic:not(.oculto)").length > 0 || z.querySelector(".lz-vacio");
        z.classList.toggle("oculto", !!f && !hay); if (f && hay && z.querySelector(".ic")) z.open = true;
      });
    }); });
    const ab = $(".lib-ab", libro);
    ab.addEventListener("click", function(){
      const ds = libro.querySelectorAll("details.lz"), abrir = ab.dataset.a === "1";
      ds.forEach(function(d){ d.open = abrir; }); ab.dataset.a = abrir ? "0" : "1"; ab.textContent = abrir ? "Cerrar todas las zonas" : "Abrir todas las zonas";
    });
  }

  // franja «Seguridad hoy»: cada tarjeta lleva a su capa del mapa o a su indicador
  document.querySelectorAll(".sc").forEach(function(c){
    c.addEventListener("click", function(){
      const a = c.dataset.act || "";
      if (a.indexOf("tab:") === 0){ const t = $('.familia-tab[data-familia="' + a.slice(4) + '"]'); if (t) t.click(); const m = $("#mapa"); if (m) m.scrollIntoView({behavior: REDUCIDO ? "auto" : "smooth", block:"start"}); }
      else if (a.indexOf("ancla:") === 0){ const el = $(a.slice(6)); if (el) el.scrollIntoView({behavior: REDUCIDO ? "auto" : "smooth", block:"start"}); }
    });
  });
  // lista «lo último»: lleva el mapa al hecho (si la ubicación es de una región entera, con una vista amplia) y abre su ficha
  document.querySelectorAll(".lu").forEach(function(b){
    b.addEventListener("click", function(){
      const sv = $("#svg-mapa"), el = sv && sv.querySelector('[data-i="' + b.dataset.i + '"]'); if (!el) return;
      const tab = $(".familia-tab.activa"); if (!tab || tab.dataset.familia !== "seguridad"){ const t = $('.familia-tab[data-familia="seguridad"]'); if (t) t.click(); }
      const m = /translate\(([-\d.]+),\s*([-\d.]+)\)/.exec(el.getAttribute("transform") || ""), mp = $("#mapa");
      if (mp) mp.scrollIntoView({behavior: REDUCIDO ? "auto" : "smooth", block:"start"});
      if (m && window.__volar) setTimeout(function(){ window.__volar(+m[1], +m[2], b.dataset.imp === "1" ? 260 : 46, REDUCIDO ? 0 : 1500); }, REDUCIDO ? 0 : 400);
      setTimeout(function(){ el.dispatchEvent(new MouseEvent("click", {bubbles: true})); }, REDUCIDO ? 100 : 2000);
    });
  });
  // el mapa arranca en la vista de seguridad (la prioridad de Ysyry); «Todo el mapa» la deja a un clic
  const t0 = $('.familia-tab[data-familia="seguridad"]'); if (t0) t0.click();

  // recorrido guiado por las cinco zonas
  const cab = $(".mapa-cab .zoom-ctrl"), colmapa = $(".col-mapa");
  if (cab && colmapa){
    const bt = document.createElement("button"); bt.type = "button"; bt.className = "tour-btn"; bt.textContent = "▶ Recorrido"; bt.setAttribute("aria-label", "Recorrido guiado por las cinco zonas");
    cab.parentNode.insertBefore(bt, cab.nextSibling);
    let card = null, i = 0, timer = null, activo = false;
    function parar(){ activo = false; clearTimeout(timer); if (card){ card.remove(); card = null; } bt.textContent = "▶ Recorrido"; }
    function paso(n){
      clearTimeout(timer); i = n;
      if (i >= ZT.length){ parar(); if (window.__volar) window.__volar(null); return; }
      const z = ZT[i];
      if (card) card.remove();
      card = document.createElement("div"); card.className = "tour-card"; card.setAttribute("role", "status");
      const zc = document.querySelectorAll(".zc")[i], b = zc && zc.dataset.b;
      card.innerHTML = '<div class="tn"></div><div class="tt"></div><p></p><div class="tb"><button type="button" class="sig"></button><button type="button" class="sec">Salir</button><span class="pts"></span></div>';
      $(".tn", card).textContent = "Zona " + (i + 1) + " de " + ZT.length + (b ? " · " + b + " buques por captura" : "");
      $(".tt", card).textContent = z.nombre; $("p", card).textContent = z.desc;
      $(".sig", card).textContent = i === ZT.length - 1 ? "Ver todo" : "Siguiente →";
      ZT.forEach(function(_, k){ const d = document.createElement("i"); if (k === i) d.className = "on"; $(".pts", card).appendChild(d); });
      $(".sig", card).addEventListener("click", function(){ paso(i + 1); });
      $(".sec", card).addEventListener("click", parar);
      colmapa.appendChild(card);
      if (window.__volar) window.__volar(z.x, z.y, z.w, REDUCIDO ? 0 : 1800);
      if (!REDUCIDO) timer = setTimeout(function(){ if (activo) paso(i + 1); }, 8000);
    }
    bt.addEventListener("click", function(){
      if (activo){ parar(); return; }
      activo = true; bt.textContent = "■ Detener"; colmapa.scrollIntoView({behavior: REDUCIDO ? "auto" : "smooth", block:"start"});
      setTimeout(function(){ if (activo) paso(0); }, REDUCIDO ? 0 : 400);
    });
    // si la persona toma el control del mapa, el recorrido se detiene
    const sv = $("#svg-mapa"); ["pointerdown", "wheel"].forEach(function(ev){ sv.addEventListener(ev, function(){ if (activo) parar(); }, {passive:true}); });
  }
})();
"""

# vuelo del mapa: se inyecta DENTRO del bloque de zoom (necesita vb, aplicar y las constantes del mapa)
VOLAR = r"""
  // vuelo suave a una región (lo usan las tarjetas por zona y el recorrido guiado); volar(null) vuelve a la vista completa
  let vueloRAF = null;
  window.__volar = function(cx, cy, w, ms){
    cancelAnimationFrame(vueloRAF);
    let t;
    if (cx === null || cx === undefined) t = {x:0, y:0, w:W0, h:H0};
    else { const h = w * H0 / W0; t = {x: Math.max(0, Math.min(W0 - w, cx - w / 2)), y: Math.max(0, Math.min(H0 - h, cy - h / 2)), w: w, h: h}; }
    if (!ms){ vb = t; aplicar(); return; }
    const s = {x:vb.x, y:vb.y, w:vb.w, h:vb.h}, t0 = performance.now();
    (function paso(t1){
      const k = Math.min(1, (t1 - t0) / ms), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      vb = {x: s.x + (t.x - s.x) * e, y: s.y + (t.y - s.y) * e, w: s.w + (t.w - s.w) * e, h: s.h + (t.h - s.h) * e};
      aplicar();
      if (k < 1) vueloRAF = requestAnimationFrame(paso);
    })(t0);
  };
  ["pointerdown", "wheel"].forEach(function(ev){ svg.addEventListener(ev, function(){ cancelAnimationFrame(vueloRAF); }, {passive:true}); });
"""

SEG_TIPOS = [("pirateria", "Piratería"), ("decomiso", "Decomiso"), ("detencion", "Detención"), ("siniestro", "Siniestro"), ("estado", "Fuerza del Estado")]


def _titulo(t):
    t = (t or "").strip()
    letras = [c for c in t if c.isalpha()]
    if letras and sum(1 for c in letras if c.isupper()) / len(letras) > 0.6:      # titulares en MAYÚSCULAS (SENAD): se pasan a oración, conservando las siglas
        t = t.lower().capitalize()
        for a, b in (("Senad", "SENAD"), ("Usd", "USD"), ("Pcc", "PCC"), ("Brasil", "Brasil")):
            t = t.replace(a, b)
    return t if len(t) <= 125 else t[:122].rsplit(" ", 1)[0] + "…"


def lo_ultimo(esc_rec):
    """Lista «lo último»: los hechos de seguridad detectados en los últimos 7 días, del más nuevo al más viejo; cada uno lleva al marcador del escáner en el mapa."""
    import html
    e = html.escape
    if not esc_rec:
        return ""
    claves = sorted({tuple(x["ubicacion"]) for x in esc_rec})
    ids = {k: "ev%d" % i for i, k in enumerate(claves)}
    orden = {t: i for i, (t, _) in enumerate(SEG_TIPOS)}
    rot = dict(SEG_TIPOS)
    filas = []
    for x in sorted(esc_rec, key=lambda x: (x["fecha"], x.get("puntaje", 0)), reverse=True):
        tipos = [t[0] for t in x["tipos"] if t[0] in orden]
        if not tipos:
            continue
        tp = sorted(tipos, key=lambda t: orden[t])[0]
        if tp == "pirateria" and not re.search(r"(barcaza|buque|embarcaci|convoy|pirat|robo de carga|roubo|hidrov|puerto|rio|río)", x["titulo"].lower()):
            continue      # «abordaje» también es «enfoque» de un problema social: sin palabra del río en el titular no se muestra
        n = len({m["dominio"] for m in x["medios"]})
        ofi = any(m.get("clase") == "oficial" for m in x["medios"])
        ev = ("%d medios" % n) if n > 1 else ("Fuente oficial" if ofi else "Fuente única")
        q = x.get("cantidad")
        cant = (" · %s %s" % (("%g" % q["valor"]).replace(".", ","), q["unidad"])) if q else ""
        lug = (x.get("lugares") or ["—"])[0]
        filas.append('<li><button type="button" class="lu" data-i="%s" data-imp="%d"><span class="lu-f">%s/%s</span><span class="lu-t">%s</span><span class="lu-x"><b>%s</b>%s</span><span class="lu-l">%s</span><span class="lu-e">%s</span><i>→</i></button></li>'
                     % (ids[tuple(x["ubicacion"])], 1 if x.get("imprecisa") else 0, e(x["fecha"][8:10]), e(x["fecha"][5:7]), e(rot[tp]), e(_titulo(x["titulo"])), e(cant), e(lug), e(ev)))
    if not filas:
        return ""
    vis, resto = filas[:6], filas[6:12]
    return ('<div class="lu-box"><h3>Lo último</h3><p class="sub">Hechos de seguridad detectados por el escáner en los últimos 7 días. Son titulares de prensa y de organismos, sin verificar: tocá uno para verlo en el mapa.</p>'
            '<ul class="lu-lista">%s</ul>%s</div>'
            % ("".join(vis), ('<details class="lu-mas"><summary>Ver %d más</summary><ul class="lu-lista">%s</ul></details>' % (len(resto), "".join(resto))) if resto else ""))


def tarjetas(flu_extra, n_rutas, n_esc, fron, esc_rec=None):
    """Franja «Seguridad hoy»: cifras que ya están en la página, con su nivel de evidencia, y a dónde lleva cada una."""
    import html
    e = html.escape
    items = {}
    for lst in flu_extra.values():
        for i in lst:
            items.setdefault(i["id"], []).append(i)

    def suma(i, k):
        return sum((x.get("dato") or {}).get(k, 0) or 0 for x in items.get(i, []))

    def nivel(i):
        return items[i][0]["nivel"] if items.get(i) else "sin dato hoy"
    pasos = (fron or {}).get("pasos", [])
    ver = sum(1 for p in pasos if p.get("verificado"))
    c = []
    c.append((str(n_esc), "hechos de seguridad detectados en 7 días", "detección automática, sin verificar", "tab:seguridad", False))
    if items.get("DEC"):
        c.append((str(suma("DEC", "hechos_30")), "decomisos e incautaciones en 30 días", nivel("DEC"), "ancla:#indicios-zonas", False))
    c.append((str(len(pasos)), "pasos de frontera seca marcados", "%d de %d contrastados con una segunda fuente" % (ver, len(pasos)), "tab:fronteras", False))
    c.append((str(n_rutas), "rutas ilícitas de SIWA cerca del río", "capa de terceros (SIWA), calificada por ellos", "tab:flujos", False))
    if items.get("ANI"):
        c.append((str(max((x.get("dato") or {}).get("mmsi_inconsistentes", 0) for x in items["ANI"])), "identidades de AIS inconsistentes", nivel("ANI"), "ancla:#indicios-zonas", False))
    if items.get("SAN"):
        n = suma("SAN", "coincidencias")
        c.append((str(n), "buques con IMO en listas de sanciones", "OFAC, Reino Unido y ONU; " + nivel("SAN").lower(), "ancla:#indicios-zonas", n > 0))
    if items.get("RAS"):
        c.append((str(suma("RAS", "ultimos_90_dias")), "alertas de la UE por alimentos del corredor (90 días)", nivel("RAS"), "ancla:#indicios-zonas", False))
    if items.get("SIN"):
        c.append((str(suma("SIN", "hechos_30")), "siniestros y derrames en 30 días", nivel("SIN"), "ancla:#indicios-zonas", False))
    tj = "".join('<button type="button" class="sc%s" data-act="%s"><span class="sn">%s</span><span class="sk">%s</span><span class="sv">%s</span></button>' % (" senal" if s else "", e(a), e(n), e(k), e(v)) for n, k, v, a, s in c)
    return ('<div class="seg-hoy"><h2>Seguridad hoy</h2><p class="sub">Lo que la página ve sobre crimen organizado, contrabando, sanciones y riesgos para el Estado y las empresas. Son indicios con su nivel de evidencia, no hechos confirmados: tocá una tarjeta para verla en el mapa o en el libro de indicios.</p>'
            '<div class="seg-grid">%s</div>%s</div>' % (tj, lo_ultimo(esc_rec)))


ANCHOS = {"z1": 0.30, "z2": 0.12, "z3": 0.34, "z4": 0.24, "z5": 0.42}


def zonas_tour():
    out = []
    for z, nombre, desc in _pulso.ZONAS:
        la, lo = _pulso.BOYAS[z]
        out.append({"id": z, "nombre": nombre, "desc": desc, "x": round(_pulso.AX * lo + _pulso.BX, 1), "y": round(_pulso.AY * la + _pulso.BY, 1), "w": round(760 * ANCHOS[z], 1)})
    return out


def js():
    return JS.replace("__ZT__", json.dumps(zonas_tour(), ensure_ascii=False))
