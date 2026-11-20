"""Gráficos de nivel del río y calados (aprobados como prototipo el 20/11/2026). Generado a partir de proto_nivel.py; la prioridad de Ysyry es la seguridad, así que esta sección va después del libro de indicios.
Lee los datos abiertos que ya baja el robot de nivel (Prefectura Naval Argentina vía INA, Dirección de Meteorología e Hidrología de Paraguay) y la tabla curada de calados. El nivel de una escala NO es el calado navegable."""
import json
import re
from collections import defaultdict
from pathlib import Path

import calados as _cal

CSS = r"""#nivel-rio .nv{margin:26px 0 10px}
#nivel-rio .nv h2{font-size:24px;margin:0 0 4px}
#nivel-rio .nv .sub{color:var(--gris-acero);font-size:14px;max-width:78ch;margin:0 0 16px}
#nivel-rio .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:16px}
#nivel-rio .kpi{background:var(--papel);border:1px solid var(--linea);border-radius:14px;padding:14px 16px}
#nivel-rio .kpi .n{font-size:30px;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
#nivel-rio .kpi .k{font-size:12px;color:var(--gris-acero);margin-top:6px}
#nivel-rio .kpi.senal{border-color:var(--naranja)}
#nivel-rio .panelg{background:var(--azul-noche);color:#F9F9F7;border-radius:14px;padding:16px;margin-bottom:14px}
:root[data-theme="dark"] #nivel-rio .panelg{background:var(--papel);border:1px solid var(--linea)}
#nivel-rio .panelg h3{margin:0 0 2px;font-size:15px}
#nivel-rio .panelg .nota{font-size:12px;color:#C6C6C5;margin:0 0 10px}
#nivel-rio .panelg svg{width:100%;height:auto;display:block;overflow:visible}
#nivel-rio .ejes text{font-size:10.5px;fill:#C6C6C5}
#nivel-rio .ejes line,#nivel-rio .grid line{stroke:var(--gris-acero);stroke-width:.6;opacity:.35}
#nivel-rio .umb-alerta{stroke:var(--naranja);stroke-width:1.2;stroke-dasharray:5 4}
#nivel-rio .umb-evac{stroke:var(--naranja);stroke-width:1.6}
#nivel-rio .umb-bajas{stroke:#C6C6C5;stroke-width:1;stroke-dasharray:2 4;opacity:.8}
#nivel-rio .umb-t{font-size:10px;fill:#F9F9F7}
#nivel-rio .umb-t.s{fill:var(--naranja);font-weight:700}
#nivel-rio .linea{fill:none;stroke:var(--acento);stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}
:root:not([data-theme="dark"]) #nivel-rio .linea{stroke:#518FB8}
#nivel-rio .area{fill:url(#nv-gr)}
#nivel-rio .pto{fill:#F9F9F7;stroke:var(--acento);stroke-width:2}
#nivel-rio .cruz{stroke:#F9F9F7;stroke-width:.8;opacity:.6}
#nivel-rio .barra{fill:#518FB8;transition:opacity .2s ease,fill .2s ease}
#nivel-rio .barra.alta{fill:var(--naranja)}
#nivel-rio .barra.sel{stroke:#F9F9F7;stroke-width:1.4}
#nivel-rio .bg:hover .barra{opacity:.8}
#nivel-rio .bg{cursor:pointer}
#nivel-rio .tip{position:absolute;pointer-events:none;background:var(--azul-profundo);color:#F9F9F7;border:1px solid var(--acento);border-radius:10px;padding:7px 10px;font-size:12px;line-height:1.35;z-index:20;opacity:0;transition:opacity .12s ease;white-space:nowrap}
#nivel-rio .rel{position:relative}
#nivel-rio .ctrl{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
#nivel-rio .ctrl select{font-family:inherit;font-weight:700;font-size:13px;padding:8px 12px;border-radius:10px;border:1px solid var(--gris-acero);background:var(--azul-profundo);color:#F9F9F7}
#nivel-rio .seg{display:inline-flex;border:1px solid var(--gris-acero);border-radius:999px;overflow:hidden}
#nivel-rio .seg button{font-family:inherit;font-weight:700;font-size:12px;padding:7px 13px;border:0;background:transparent;color:#F9F9F7;cursor:pointer;transition:background .2s ease}
#nivel-rio .seg button.activa{background:var(--acento);color:var(--acento-sobre)}
#nivel-rio .cab-est{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;margin-bottom:6px}
#nivel-rio .cab-est .big{font-size:36px;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
#nivel-rio .cab-est .u{font-size:14px;color:#C6C6C5;margin-left:3px}
#nivel-rio .chip{display:inline-block;font-size:11.5px;font-weight:700;border-radius:999px;padding:3px 10px;border:1px solid var(--gris-acero);color:#F9F9F7}
#nivel-rio .chip.senal{border-color:var(--naranja);color:var(--naranja)}
#nivel-rio .term{margin:12px 0 4px}
#nivel-rio .term .t-barra{position:relative;height:12px;border-radius:999px;overflow:hidden;background:color-mix(in srgb,#C6C6C5 20%,transparent);display:flex}
#nivel-rio .term .t-barra i{display:block;height:100%}
#nivel-rio .term .t-mar{position:absolute;top:-4px;width:3px;height:20px;background:#F9F9F7;border-radius:2px;box-shadow:0 0 0 2px var(--azul-noche);transition:left .6s cubic-bezier(.2,.8,.2,1)}
#nivel-rio .term .t-ley{display:flex;justify-content:space-between;font-size:11px;color:#C6C6C5;margin-top:6px;gap:8px}
#nivel-rio .gcal{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:6px}
#nivel-rio .cal{background:var(--papel);border:1px solid var(--linea);border-radius:14px;padding:14px 16px;display:flex;flex-direction:column;gap:6px}
#nivel-rio .cal .ct{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--gris-acero);font-weight:700}
#nivel-rio .cal h4{margin:0;font-size:15px}
#nivel-rio .cal .cv{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums}
#nivel-rio .cal .cv small{font-size:13px;font-weight:700;color:var(--gris-acero)}
#nivel-rio .cal .cp{font-size:12px;color:var(--gris-acero);margin:0}
#nivel-rio .cal button{align-self:flex-start;font-family:inherit;font-weight:700;font-size:12px;border-radius:999px;padding:6px 12px;border:1px solid var(--acento);background:transparent;color:var(--acento-texto);cursor:pointer;transition:background .2s ease}
#nivel-rio .cal button:hover{background:color-mix(in srgb,var(--acento) 14%,transparent)}
#nivel-rio .pv{display:inline-block;font-size:10.5px;font-weight:700;border:1px dashed var(--naranja);color:var(--fg);border-radius:999px;padding:2px 8px}
#nivel-rio .leyenda-g{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#C6C6C5;margin-top:8px}
#nivel-rio .leyenda-g span{display:inline-flex;align-items:center;gap:6px}
#nivel-rio .leyenda-g i{display:inline-block;width:18px;height:0;border-top:2px solid #518FB8}
#nivel-rio .leyenda-g i.a{border-top:2px dashed var(--naranja)}
#nivel-rio .leyenda-g i.e{border-top:2px solid var(--naranja)}
#nivel-rio .leyenda-g i.b{border-top:2px dotted #C6C6C5}
#nivel-rio .cbar{margin-top:6px}
#nivel-rio .proto-nota{font-size:12.5px;color:var(--gris-acero);margin:14px 0 40px;max-width:80ch}
@media (prefers-reduced-motion:no-preference){#nivel-rio .linea{stroke-dasharray:var(--len,2000);stroke-dashoffset:var(--len,2000);animation:nvdib 1.3s ease forwards}
@keyframes nvdib{to{stroke-dashoffset:0}}
#nivel-rio .barra{transform-origin:50% 100%;transform-box:fill-box;animation:nvcrece .8s cubic-bezier(.2,.8,.2,1) both}
@keyframes nvcrece{from{transform:scaleY(0)}}}"""

HTML = r"""

<div class="nv">
  <h2>Nivel del río</h2>
  <p class="sub">Lecturas de las escalas de la Prefectura Naval Argentina (vía INA) y de la Dirección de Meteorología e Hidrología de Paraguay. Elegí una escala para ver su serie, sus cotas oficiales o su rango histórico. El nivel es un dato de la escala, no el calado navegable.</p>
  <div class="kpis" id="nv-kpis"></div>

  <div class="panelg rel">
    <h3>Perfil del Paraná: nivel de cada escala frente a su cota de alerta</h3>
    <p class="nota">De aguas arriba (Posadas) a aguas abajo (Ibicuy). La línea punteada es la cota de alerta (100 %); la sólida, la de evacuación. Barras en naranja: ya superaron la alerta. Tocá una barra para ver la serie.</p>
    <div id="nv-perfil"></div>
    <div class="tip" id="nv-tip1"></div>
  </div>

  <div class="panelg rel">
    <div class="ctrl">
      <label for="sel" style="font-weight:700;font-size:13px">Escala</label>
      <select id="nv-sel"></select>
      <div class="seg" id="nv-rango" role="group" aria-label="Período"><button data-d="14">14 días</button><button data-d="30">30 días</button><button data-d="0" class="activa">Todo</button></div>
    </div>
    <div class="cab-est" id="nv-cab"></div>
    <div id="nv-term" class="term"></div>
    <div id="nv-serie"></div>
    <div class="leyenda-g" id="nv-ley"></div>
    <div class="tip" id="nv-tip2"></div>
  </div>
</div>

<div class="nv">
  <h2>Calados</h2>
  <p class="sub">Restricciones de calado que citan las normas de cada país, por tramo. <b>Ninguna está verificada contra la norma original</b>: salen de notas de prensa y no sirven para planificar una navegación. Las barras rayadas significan «por verificar».</p>
  <div class="panelg">
    <h3>Calado máximo declarado por tramo (metros)</h3>
    <p class="nota">Los pies se convirtieron a metros (1 pie = 0,3048 m). Los tramos son de ríos distintos: no se comparan entre sí, sólo muestran el orden de magnitud.</p>
    <div id="nv-calbar"></div>
  </div>
  <div class="gcal" id="nv-gcal"></div>
  <p class="proto-nota">Qué mide y qué no: el nivel de una escala no dice el calado disponible en el canal, y el calado de una norma no dice el nivel de hoy. Esta página los pone lado a lado para que se vea la relación, sin inferir un valor que la norma no da.</p>
</div>"""

JS = r"""(function(){

const D = __DATOS__;
const E = D.est, byId = {}; E.forEach(e => byId[e.id] = e);
const fmt = (v, d = 2) => v == null ? "—" : v.toLocaleString("es-AR", {minimumFractionDigits: d, maximumFractionDigits: d});
const NS = "http://www.w3.org/2000/svg";
const $ = s => document.querySelector(s);
const fd = s => s ? s.slice(8, 10) + "/" + s.slice(5, 7) : "";
let sel = "ar14", rango = 0;
const PAR = E.filter(e => e.grupo === "parana" && e.alerta && !/Formosa|Concordia|Buenos Aires|Palmira/.test(e.nombre));

/* KPIs */
(function(){
  const ar = E.filter(e => e.grupo === "parana" && e.alerta);
  const sobreA = ar.filter(e => e.nivel >= e.alerta), sobreE = ar.filter(e => e.evac && e.nivel >= e.evac), bajas = ar.filter(e => e.bajas && e.nivel <= e.bajas);
  const py = E.filter(e => e.grupo === "paraguay" && e.max != null && e.min != null && e.nivel != null);
  const pct = py.map(e => (e.nivel - e.min) / (e.max - e.min)).sort((a, b) => a - b);
  const med = pct.length ? pct[Math.floor(pct.length / 2)] : null;
  const k = [[sobreA.length + " de " + ar.length, "escalas del Paraná sobre su cota de alerta", sobreA.length ? "senal" : ""], [String(sobreE.length), "escalas sobre su cota de evacuación", sobreE.length ? "senal" : ""],
             [String(bajas.length), "escalas en aguas bajas", ""], [med == null ? "—" : Math.round(med * 100) + " %", "posición mediana de las estaciones de Paraguay dentro de su rango histórico (0 % = mínimo, 100 % = máximo)", ""]];
  $("#nv-kpis").innerHTML = k.map(x => '<div class="kpi ' + x[2] + '"><div class="n">' + x[0] + '</div><div class="k">' + x[1] + '</div></div>').join("");
})();

/* tooltip */
function tip(el, caja, html, ev){
  const r = caja.getBoundingClientRect();
  el.innerHTML = html; el.style.opacity = 1;
  let x = ev.clientX - r.left + 14, y = ev.clientY - r.top - 10;
  if (x > r.width - 190) x -= 210;
  el.style.left = x + "px"; el.style.top = y + "px";
}

/* perfil del Paraná */
function perfil(){
  const W = 900, H = 300, L = 42, Rr = 12, T = 14, B = 74, n = PAR.length, bw = (W - L - Rr) / n;
  const ratio = e => e.nivel / e.alerta, ymax = 1.3;
  const y = v => T + (H - T - B) * (1 - Math.min(v, ymax) / ymax);
  let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Nivel de cada escala del Paraná como porcentaje de su cota de alerta"><g class="grid ejes">';
  [0, .25, .5, .75, 1, 1.25].forEach(v => { s += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + y(v) + '" y2="' + y(v) + '"/><text x="' + (L - 6) + '" y="' + (y(v) + 3) + '" text-anchor="end">' + Math.round(v * 100) + ' %</text>'; });
  s += '</g><line class="umb-alerta" x1="' + L + '" x2="' + (W - Rr) + '" y1="' + y(1) + '" y2="' + y(1) + '"/><text class="umb-t s" x="' + (W - Rr) + '" y="' + (y(1) - 5) + '" text-anchor="end">alerta</text>';
  PAR.forEach((e, i) => {
    const x = L + i * bw + bw * .14, w = bw * .72, r = ratio(e), top = y(r), alta = r >= 1;
    s += '<g class="bg" data-i="' + e.id + '"><rect x="' + (L + i * bw) + '" y="' + T + '" width="' + bw + '" height="' + (H - T - B) + '" fill="transparent"/><rect class="barra' + (alta ? " alta" : "") + (e.id === sel ? " sel" : "") + '" style="animation-delay:' + (i * 0.025) + 's" x="' + x + '" y="' + top + '" width="' + w + '" height="' + (y(0) - top) + '" rx="2"/>';
    if (e.evac) s += '<line class="umb-evac" x1="' + x + '" x2="' + (x + w) + '" y1="' + y(e.evac / e.alerta) + '" y2="' + y(e.evac / e.alerta) + '"/>';
    s += '<text transform="translate(' + (x + w / 2 + 3) + ',' + (H - B + 10) + ') rotate(60)" font-size="10" fill="#C6C6C5">' + e.nombre.replace(/ \(San Martín\)/, "") + '</text></g>';
  });
  s += '</svg>';
  $("#nv-perfil").innerHTML = s;
  $("#nv-perfil").querySelectorAll(".bg").forEach(g => {
    const e = byId[g.dataset.i];
    g.addEventListener("mousemove", ev => tip($("#nv-tip1"), $("#nv-perfil").parentNode, "<b>" + e.nombre + "</b><br>" + fmt(e.nivel) + " m · " + Math.round(ratio(e) * 100) + " % de la alerta<br>alerta " + fmt(e.alerta) + " m · evacuación " + fmt(e.evac) + " m", ev));
    g.addEventListener("mouseleave", () => $("#nv-tip1").style.opacity = 0);
    g.addEventListener("click", () => elegir(e.id, true));
  });
}

/* detalle de una escala */
function serie(){
  const e = byId[sel]; let pts = e.serie.slice();
  if (rango) pts = pts.slice(-rango);
  const W = 900, H = 330, L = 48, Rr = 16, T = 14, B = 30;
  const vals = pts.map(p => p[1]); let lo = Math.min(...vals), hi = Math.max(...vals);
  const ums = [];
  if (e.grupo === "parana"){ if (e.bajas != null) ums.push(["bajas", e.bajas, "aguas bajas"]); if (e.alerta != null) ums.push(["alerta", e.alerta, "alerta"]); if (e.evac != null) ums.push(["evac", e.evac, "evacuación"]); }
  else { if (e.min != null) ums.push(["bajas", e.min, "mínimo histórico"]); if (e.max != null) ums.push(["evac", e.max, "máximo histórico"]); }
  ums.forEach(u => { lo = Math.min(lo, u[1]); hi = Math.max(hi, u[1]); });
  const pad = (hi - lo) * .08 || .5; lo -= pad; hi += pad;
  const t0 = new Date(pts[0][0]).getTime(), t1 = new Date(pts[pts.length - 1][0]).getTime() || t0 + 1;
  const x = d => L + (new Date(d).getTime() - t0) / ((t1 - t0) || 1) * (W - L - Rr), yy = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Serie de nivel de ' + e.nombre + '"><defs><linearGradient id="nv-gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#518FB8" stop-opacity=".35"/><stop offset="1" stop-color="#518FB8" stop-opacity="0"/></linearGradient></defs><g class="grid ejes">';
  for (let k = 0; k <= 4; k++){ const v = lo + (hi - lo) * k / 4; s += '<line x1="' + L + '" x2="' + (W - Rr) + '" y1="' + yy(v) + '" y2="' + yy(v) + '"/><text x="' + (L - 6) + '" y="' + (yy(v) + 3) + '" text-anchor="end">' + fmt(v, 1) + '</text>'; }
  const nt = Math.min(6, pts.length - 1);
  for (let k = 0; k <= nt; k++){ const p = pts[Math.round((pts.length - 1) * k / (nt || 1))]; s += '<text x="' + x(p[0]) + '" y="' + (H - 8) + '" text-anchor="middle">' + fd(p[0]) + '</text>'; }
  s += '</g>';
  ums.forEach(u => { const cl = u[0] === "alerta" ? "umb-alerta" : u[0] === "evac" ? "umb-evac" : "umb-bajas"; s += '<line class="' + cl + '" x1="' + L + '" x2="' + (W - Rr) + '" y1="' + yy(u[1]) + '" y2="' + yy(u[1]) + '"/><text class="umb-t' + (u[0] !== "bajas" ? " s" : "") + '" x="' + (W - Rr - 2) + '" y="' + (yy(u[1]) - 4) + '" text-anchor="end">' + u[2] + ' ' + fmt(u[1]) + ' m</text>'; });
  const d = pts.map((p, i) => (i ? "L" : "M") + x(p[0]).toFixed(1) + "," + yy(p[1]).toFixed(1)).join(" ");
  s += '<path class="area" d="' + d + ' L' + x(pts[pts.length - 1][0]) + ',' + yy(lo) + ' L' + x(pts[0][0]) + ',' + yy(lo) + ' Z"/><path class="linea" id="nv-ln" d="' + d + '"/>';
  const last = pts[pts.length - 1];
  s += '<circle class="pto" cx="' + x(last[0]) + '" cy="' + yy(last[1]) + '" r="4.5"/><g id="nv-hov" style="display:none"><line class="cruz" id="nv-cx" y1="' + T + '" y2="' + (H - B) + '"/><circle class="pto" id="nv-cp" r="4"/></g><rect id="nv-cap" x="' + L + '" y="' + T + '" width="' + (W - L - Rr) + '" height="' + (H - T - B) + '" fill="transparent"/></svg>';
  $("#nv-serie").innerHTML = s;
  const ln = $("#nv-ln"); ln.style.setProperty("--len", Math.ceil(ln.getTotalLength()) + 2);
  const cap = $("#nv-cap"), svg = $("#serie svg");
  cap.addEventListener("mousemove", ev => {
    const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.getScreenCTM().inverse());
    let best = pts[0], bd = 1e18; pts.forEach(p => { const dd = Math.abs(x(p[0]) - pt.x); if (dd < bd){ bd = dd; best = p; } });
    $("#nv-hov").style.display = ""; $("#nv-cx").setAttribute("x1", x(best[0])); $("#nv-cx").setAttribute("x2", x(best[0])); $("#nv-cp").setAttribute("cx", x(best[0])); $("#nv-cp").setAttribute("cy", yy(best[1]));
    tip($("#nv-tip2"), $("#nv-serie").parentNode, "<b>" + fmt(best[1]) + " m</b><br>" + best[0].split("-").reverse().join("/"), ev);
  });
  cap.addEventListener("mouseleave", () => { $("#nv-hov").style.display = "none"; $("#nv-tip2").style.opacity = 0; });
  $("#nv-ley").innerHTML = '<span><i></i>nivel diario</span>' + (e.grupo === "parana" ? '<span><i class="b"></i>aguas bajas</span><span><i class="a"></i>alerta</span><span><i class="e"></i>evacuación</span>' : '<span><i class="b"></i>mínimo histórico</span><span><i class="e"></i>máximo histórico</span>') + '<span>Fuente: ' + (e.grupo === "parana" ? "Prefectura Naval Argentina vía INA" : "Dirección de Meteorología e Hidrología de Paraguay") + ' · última lectura ' + (e.fecha || "").split("-").reverse().join("/") + '</span>';
}

function cabecera(){
  const e = byId[sel]; let chip = "", term = "";
  if (e.grupo === "parana" && e.alerta != null){
    const est = e.evac != null && e.nivel >= e.evac ? ["Sobre la cota de evacuación", 1] : e.nivel >= e.alerta ? ["Sobre la cota de alerta", 1] : (e.bajas != null && e.nivel <= e.bajas) ? ["En aguas bajas", 0] : ["Dentro de lo habitual", 0];
    chip = '<span class="chip ' + (est[1] ? "senal" : "") + '">' + est[0] + '</span>';
    const a = e.bajas != null ? e.bajas : Math.min(e.nivel, e.alerta) * .6, b = e.alerta, c = e.evac != null ? e.evac : e.alerta * 1.1, mx = Math.max(c * 1.08, e.nivel * 1.05), p = v => Math.max(0, Math.min(100, (v - 0) / mx * 100));
    term = '<div class="t-barra"><i style="width:' + p(a) + '%;background:color-mix(in srgb,#C6C6C5 35%,transparent)"></i><i style="width:' + (p(b) - p(a)) + '%;background:#518FB8"></i><i style="width:' + (p(c) - p(b)) + '%;background:color-mix(in srgb,var(--naranja) 55%,transparent)"></i><i style="width:' + (100 - p(c)) + '%;background:var(--naranja)"></i><span class="t-mar" style="left:calc(' + p(e.nivel) + '% - 1.5px)"></span></div><div class="t-ley"><span>0 m</span><span>aguas bajas ' + fmt(e.bajas) + '</span><span>alerta ' + fmt(e.alerta) + '</span><span>evacuación ' + fmt(e.evac) + '</span></div>';
  } else if (e.max != null && e.min != null){
    const p = (e.nivel - e.min) / (e.max - e.min) * 100;
    chip = '<span class="chip ' + (p >= 90 || p <= 5 ? "senal" : "") + '">' + Math.round(p) + ' % de su rango histórico</span>';
    term = '<div class="t-barra"><i style="width:100%;background:linear-gradient(90deg,color-mix(in srgb,#C6C6C5 35%,transparent),#518FB8)"></i><span class="t-mar" style="left:calc(' + Math.max(0, Math.min(100, p)) + '% - 1.5px)"></span></div><div class="t-ley"><span>mínimo ' + fmt(e.min) + ' m (' + (e.fmin || "").split("-").reverse().join("/") + ')</span><span>máximo ' + fmt(e.max) + ' m (' + (e.fmax || "").split("-").reverse().join("/") + ')</span></div>';
  }
  const v = e.var;
  $("#nv-cab").innerHTML = '<div><span class="big">' + fmt(e.nivel) + '</span><span class="u">m</span></div><div style="font-weight:800;font-size:18px">' + e.nombre + '</div>' + chip + (v != null ? '<span class="chip">' + (v > 0 ? "▲ +" : v < 0 ? "▼ " : "= ") + fmt(v, 0) + ' cm en 24 h</span>' : "");
  $("#nv-term").innerHTML = term;
}

function elegir(id, sube){
  sel = id; $("#nv-sel").value = id; cabecera(); serie(); perfil();
  if (sube) $("#nv-cab").scrollIntoView({behavior: "smooth", block: "center"});
}

/* selector y rango */
(function(){
  let h = ""; [["parana", "Paraná y afluentes (Prefectura Naval Argentina)"], ["paraguay", "Río Paraguay (Paraguay y Brasil)"]].forEach(g => {
    h += '<optgroup label="' + g[1] + '">' + E.filter(e => e.grupo === g[0]).map(e => '<option value="' + e.id + '">' + e.nombre + '</option>').join("") + '</optgroup>';
  });
  $("#nv-sel").innerHTML = h; $("#nv-sel").addEventListener("change", e => elegir(e.target.value));
  document.querySelectorAll("#rango button").forEach(b => b.addEventListener("click", () => { document.querySelectorAll("#rango button").forEach(x => x.classList.remove("activa")); b.classList.add("activa"); rango = +b.dataset.d; serie(); }));
})();

/* calados */
const PIES = 0.3048;
function metros(c){
  const t = c.calado; let m;
  if ((m = /([\d,]+)\s*pies/.exec(t))) return parseFloat(m[1].replace(",", ".")) * PIES;
  if ((m = /([\d,]+)\s*m/.exec(t))) return parseFloat(m[1].replace(",", "."));
  return null;
}
const REL = {"PY-54-2025": "py", "PY-NORTE-2026": "py", "BR-PORTARIA-19": "py", "AR-VNT-8-88": "ar"};
const ESC = {"PY-54-2025": "Vallemí", "PY-NORTE-2026": "Asunción", "BR-PORTARIA-19": "Ladario", "AR-VNT-8-88": "Rosario"};
function ladario(){
  const e = E.find(x => x.nombre.indexOf("Ladario") >= 0); if (!e || e.nivel == null) return "";
  const W = 420, H = 84, L = 14, Rr = 14, mx = 2.6, x = v => L + (W - L - Rr) * v / mx;
  const pts = [[1.85, "2,90 m", "end", -4], [2.15, "3,20 m", "start", 4]];
  let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto" role="img" aria-label="Régua de Ladário hoy frente a los dos valores de la nota"><line x1="' + L + '" x2="' + (W - Rr) + '" y1="46" y2="46" stroke="var(--gris-acero)" stroke-width="3" stroke-linecap="round" opacity=".45"/>';
  for (let v = 0; v <= 2.5; v += .5) s += '<line x1="' + x(v) + '" x2="' + x(v) + '" y1="42" y2="50" stroke="var(--gris-acero)" opacity=".6"/><text x="' + x(v) + '" y="64" text-anchor="middle" font-size="10" fill="var(--gris-acero)">' + fmt(v, 1) + '</text>';
  pts.forEach(p => { s += '<circle cx="' + x(p[0]) + '" cy="46" r="5" fill="none" stroke="var(--naranja)" stroke-width="2" stroke-dasharray="3 2"/><text x="' + (x(p[0]) + p[3]) + '" y="34" text-anchor="' + p[2] + '" font-size="10.5" font-weight="700" fill="var(--fg)">' + fmt(p[0]) + ' m → ' + p[1] + '</text>'; });
  s += '<path d="M' + x(e.nivel) + ',40 l-6,-12 h12 z" fill="var(--acento)"/><text x="' + x(e.nivel) + '" y="22" text-anchor="middle" font-size="11" font-weight="800" fill="var(--fg)">hoy ' + fmt(e.nivel) + ' m</text><text x="' + (W / 2) + '" y="80" text-anchor="middle" font-size="10" fill="var(--gris-acero)">régua de Ladário (m)</text></svg>';
  return '<div class="cbar">' + s + '</div><p class="cp">La nota da dos pares (régua → calado). Hoy la régua marca menos que los dos: no se calcula aquí un calado, la norma no lo da.</p>';
}
function calados(){
  const C = D.calados, vals = C.map(metros), mx = Math.max(...vals.filter(v => v != null)) * 1.15;
  const W = 900, rh = 52, H = C.length * rh + 22, L = 250;
  let s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Calado máximo declarado por tramo"><defs><pattern id="nv-pv" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="9" height="9" fill="#518FB8" fill-opacity=".10"/><line x1="0" y1="0" x2="0" y2="9" stroke="#518FB8" stroke-width="2"/></pattern></defs>';
  C.forEach((c, i) => {
    const v = vals[i], y = i * rh + 8, w = v == null ? 0 : (W - L - 150) * v / mx;
    s += '<text x="' + (L - 12) + '" y="' + (y + 15) + '" text-anchor="end" font-size="12.5" font-weight="700" fill="#F9F9F7">' + c.rio.replace("Río Paraná (Vía Navegable Troncal)", "Paraná (VNT)") + '</text><text x="' + (L - 12) + '" y="' + (y + 30) + '" text-anchor="end" font-size="10.5" fill="#C6C6C5">' + c.pais + '</text>';
    s += '<rect class="barra" style="animation-delay:' + (i * .12) + 's;transform-origin:0 50%" x="' + L + '" y="' + y + '" width="' + w + '" height="30" rx="4" fill="url(#nv-pv)" stroke="#518FB8" stroke-width="1.4" stroke-dasharray="5 3"/>';
    s += '<text x="' + (L + w + 10) + '" y="' + (y + 20) + '" font-size="13" font-weight="800" fill="#F9F9F7">' + (v == null ? "—" : "≈ " + fmt(v, 2) + " m") + '</text><text x="' + (L + w + 10) + '" y="' + (y + 34) + '" font-size="10.5" fill="#C6C6C5">por verificar</text>';
  });
  $("#nv-calbar").innerHTML = s + '</svg>';
  $("#nv-gcal").innerHTML = C.map((c, i) => '<div class="cal"><span class="ct">' + c.rio + ' · ' + c.pais + '</span><h4>' + c.tramo + '</h4><div class="cv">' + c.calado.split(" (")[0] + (metros(c) != null && /pies/.test(c.calado) ? ' <small>≈ ' + fmt(metros(c), 2) + ' m</small>' : '') + '</div>' + (c.id === "BR-PORTARIA-19" ? ladario() : '') +
    '<p class="cp">' + c.organismo + (c.norma ? " · " + c.norma : "") + (c.fecha_fuente ? " · " + c.fecha_fuente.split("-").reverse().join("/") : "") + '</p><p class="cp"><span class="pv">por verificar</span> Fuente: ' + c.fuente_nombre + '</p>' +
    '<button type="button" data-i="' + i + '">Ver el nivel de ' + ESC[c.id] + ' →</button></div>').join("");
  document.querySelectorAll("#gcal button").forEach(b => b.addEventListener("click", () => { const c = C[+b.dataset.i], nom = ESC[c.id]; const e = E.find(x => x.nombre.indexOf(nom) >= 0); if (e) elegir(e.id); $("#nv-sel").scrollIntoView({behavior: "smooth", block: "center"}); }));
}

elegir(E.find(e => e.nombre === "Rosario").id); calados();

})();"""


def _num(t):
    m = re.search(r"-?\d+(?:[.,]\d+)?", t or "")
    return float(m.group(0).replace(",", ".")) if m else None


def _fechapy(t):
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", t or "")
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None


def datos(pub, ruta_calados):
    pub = Path(pub)
    ar = json.load(open(pub / "nivel-rio-ar.json", encoding="utf-8"))
    hist_ar = defaultdict(list)
    if (pub / "nivel-rio-ar-historial.jsonl").exists():
        for l in open(pub / "nivel-rio-ar-historial.jsonl", encoding="utf-8"):
            d = json.loads(l)
            hist_ar[d["id"]].append((d["fecha"], d["nivel_m"]))
    est = []
    for e in ar["estaciones"]:
        serie = sorted(set(hist_ar.get(e["id"], [])) | {(x[0], x[1]) for x in e.get("serie", [])})
        est.append({"id": "ar%d" % e["id"], "nombre": e["nombre"], "grupo": "parana", "rio": e["rio"], "nivel": e["nivel_m"], "var": e.get("var_cm"), "fecha": e["fecha"],
                    "bajas": e.get("nivel_aguas_bajas"), "alerta": e.get("nivel_alerta"), "evac": e.get("nivel_evacuacion"), "serie": [[a, b] for a, b in serie if b is not None]})
    py = json.load(open(pub / "nivel-rio-py.json", encoding="utf-8"))
    hist_py = defaultdict(dict)
    if (pub / "nivel-rio-py-historial.jsonl").exists():
        for l in open(pub / "nivel-rio-py-historial.jsonl", encoding="utf-8"):
            d = json.loads(l)
            dd, mm, aa = d["lectura"].split("-")
            hist_py[d["estacion"]]["%s-%s-%s" % (aa, mm, dd)] = d["nivel_m"]
    for k, e in enumerate(py["estaciones"]):
        nm = e["estacion"]
        if nm not in hist_py:
            continue
        est.append({"id": "py%d" % k, "nombre": nm.replace(" - Brasil", " (Brasil)"), "grupo": "paraguay", "rio": "Río Paraguay", "nivel": _num(e["nivel"]), "var": _num(e["variacion_24h"]),
                    "fecha": _fechapy(e["fecha_lectura"]), "max": _num(e["maximo_historico"]), "min": _num(e["minimo_historico"]), "fmax": _fechapy(e["maximo_historico"]), "fmin": _fechapy(e["minimo_historico"]),
                    "serie": [[a, b] for a, b in sorted(hist_py[nm].items())]})
    cal = json.load(open(ruta_calados, encoding="utf-8"))
    return {"est": est, "calados": [{k: v for k, v in c.items() if k in ("id", "pais", "rio", "tramo", "calado", "organismo", "norma", "fecha_fuente", "fuente_nombre", "fuente_url", "estado")} for c in cal["entradas"]],
            "obtenido_ar": ar["obtenido"], "obtenido_py": py["obtenido"]}


def bloque_html(pub, ruta_calados):
    """Sección «Nivel del río y calados»; si faltan los datos devuelve sólo la tabla curada de calados de antes."""
    try:
        d = datos(pub, ruta_calados)
        assert len(d["est"]) > 10
    except Exception as e:
        print("aviso: nivel del río sin gráficos:", str(e)[:80])
        return _cal.bloque_html(ruta_calados)
    tabla = _cal.bloque_html(ruta_calados).replace('<div class="pulso" id="calados">', '<div id="calados">', 1)
    return ('<div class="pulso" id="nivel-rio"><style>%s</style>%s'
            '<details class="tabla-det"><summary>Ver la tabla curada de calados con su estado de verificación</summary>%s</details>'
            '<script>%s</script></div>' % (CSS, HTML, tabla, JS.replace("__DATOS__", json.dumps(d, ensure_ascii=False, separators=(",", ":")))))
