#!/usr/bin/env python3
"""Reporte de clima para tu comuna: ¿voy presencial o trabajo desde la casa?

Junta fuentes vivas de Chile, sin API key:
  1. DMC (Dirección Meteorológica de Chile): avisos, alertas y alarmas oficiales de tu región
  2. DMC: pronóstico oficial de la ciudad más cercana
  3. DMC: observación de ahora en la estación más cercana
  4. Open-Meteo: hora a hora con 3 modelos (best_match, ECMWF, GFS)
  5. Metro de Santiago: estado de la red ahora (solo si lo activas)

Uso:
  python3 clima.py buscar "Ñuñoa"     -> coordenadas candidatas de la comuna
  python3 clima.py listar             -> ciudades de pronóstico y estaciones de la DMC
  python3 clima.py [--turno manana|tarde] [--out DIR]   -> el reporte

La configuración vive en config.json, junto a SKILL.md (ver config.ejemplo.json).
Sale: JSON por stdout + escribe <DIR>/<fecha-hora>.html y .json con el correo listo.
Solo librería estándar.
"""
import argparse, html, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "..", "config.json")
UA = {"User-Agent": "Mozilla/5.0 clima-comuna/1.0"}
MODELOS = ["best_match", "ecmwf_ifs025", "gfs_seamless"]
DMC = "https://archivos.meteochile.gob.cl/portaldmc"
# Estaciones de la DMC con observación en vivo (aeródromos, código OACI)
ESTACIONES = {
    "SCAR": "Arica", "SCDA": "Iquique", "SCCF": "Calama", "SCFA": "Antofagasta",
    "SCAT": "Copiapó / Caldera", "SCSE": "La Serena", "SCVM": "Viña del Mar", "SCRD": "Viña del Mar (Rodelillo)",
    "SCSN": "Santo Domingo", "SCEL": "Santiago (Pudahuel)", "SCTB": "Santiago oriente (Tobalaba)",
    "SCQN": "Santiago centro (Quinta Normal)", "SCRG": "Rancagua", "SCIC": "Curicó", "SCCH": "Chillán",
    "SCIE": "Concepción", "SCGE": "Los Ángeles", "SCQP": "Temuco", "SCVD": "Valdivia", "SCJO": "Osorno",
    "SCTE": "Puerto Montt", "SCCY": "Coyhaique", "SCBA": "Balmaceda", "SCNT": "Puerto Natales",
    "SCCI": "Punta Arenas", "SCFM": "Porvenir", "SCGZ": "Puerto Williams", "SCIP": "Isla de Pascua",
    "SCON": "Quellón", "SCTN": "Chaitén", "SCFT": "Futaleufú", "SCMK": "Melinka", "SCAS": "Puerto Aysén",
    "SCCC": "Chile Chico", "SCHR": "Cochrane", "SCIR": "Juan Fernández", "SCRM": "Antártica (Base Frei)",
}
# Códigos WMO: 95 tormenta, 96/99 tormenta con granizo
TORMENTA, GRANIZO = {95, 96, 99}, {96, 99}


def get(url, enc="utf-8"):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode(enc, errors="replace")


def limpio(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def cargar_config():
    if not os.path.exists(CONFIG):
        sys.exit("Falta config.json. Copia config.ejemplo.json como config.json y pon tu comuna "
                 "(o pídele a Claude: «configura la skill del clima para mi comuna»).")
    c = json.load(open(CONFIG))
    falta = [k for k in ("comuna", "lat", "lon", "region_dmc") if c.get(k) in (None, "")]
    if falta:
        sys.exit(f"config.json incompleto: falta {', '.join(falta)} (mira config.ejemplo.json).")
    c.setdefault("ida", [7, 10]); c.setdefault("vuelta", [17, 21])
    for k in ("ida", "vuelta"):
        a, b = c[k]
        if not (0 <= a < b <= 24):
            sys.exit(f"config.json: '{k}' tiene que ser [desde, hasta] dentro del mismo día (0–24 h), y vino {c[k]}.")
    c.setdefault("metro", {"activo": False})
    return c


# ---------- configuración asistida ----------
def buscar(nombre):
    url = ("https://geocoding-api.open-meteo.com/v1/search?count=5&language=es&country_code=CL&name="
           + urllib.parse.quote(nombre))
    d = json.loads(get(url))
    for r in d.get("results", []):
        print(f"{r['name']} · {r.get('admin1', '')} · {r.get('admin2', '')} · lat {r['latitude']} lon {r['longitude']}")
    if not d.get("results"):
        print("Sin resultados. Prueba con otro nombre o pon las coordenadas a mano.")


def listar():
    t = get(f"{DMC}/meteochile/js/pronostico.js", "latin-1")
    print("CIUDADES DE PRONÓSTICO DMC (va en ciudad_pronostico_dmc):")
    print("  " + " · ".join(limpio(c) for c in re.findall(r'ciudad : "([^"]*)"', t)))
    t = get(f"{DMC}/appdata/condicionactual.js", "latin-1")
    print("\nESTACIONES CON OBSERVACIÓN AHORA (va en estacion_dmc; son aeródromos, código OACI):")
    for cod, val in re.findall(r"\['(\w+)'\] = '([^']*)'", t):
        p = val.split("|")
        print(f"  {cod} · {ESTACIONES.get(cod, '(sin nombre en la tabla)')} · ahora: {limpio(p[10]) if len(p) > 10 else ''}")
    t = get(f"{DMC}/AAA/datos_AAA.js", "latin-1")
    zonas = sorted({z for b in re.findall(r'dataZonaAfecta\s*:\s*"([^"]*)"', t) for z in b.split(",")})
    print("\nZONAS CON AVISOS VIGENTES HOY (el prefijo es la región: va en region_dmc):")
    print("  " + (" · ".join(zonas) or "ninguna"))


# ---------- fuentes ----------
def dmc_alertas(cfg, errores):
    try:
        t = get(f"{DMC}/AAA/datos_AAA.js", "latin-1").replace("\r\n", "\n")  # viene con CRLF
    except Exception as e:
        errores.append(f"DMC alertas: {e}"); return None
    act = re.search(r"fecha_actualizacion = '([^']+)'", t)
    pref = cfg["region_dmc"] + "_"
    zonas_cfg = cfg.get("zonas_dmc") or []
    out = []
    for b in t.split("AAA.push(")[1:]:
        campo = lambda k: (re.search(rf'{k}\s*:\s*"(.*?)",?\n', b, re.S) or [None, ""])[1]
        zonas = [z.strip() for z in campo("dataZonaAfecta").split(",")]
        region_entera = cfg["region_dmc"] in zonas      # a veces la DMC pone solo "09,10a"
        if zonas_cfg:
            if not region_entera and not any(z in zonas_cfg for z in zonas):
                continue
        elif not region_entera and not any(z.startswith(pref) for z in zonas):
            continue
        out.append({k: limpio(campo(k)) for k in
                    ("tipo", "fenomeno", "desde", "hasta", "observacion", "emision", "codigoMeteo")})
    orden = {"Alarma": 0, "Alerta": 1, "Aviso": 2}
    out.sort(key=lambda a: orden.get(a["tipo"], 9))
    return {"actualizado": act[1] if act else "", "vigentes": out}


def dmc_pronostico(cfg, errores):
    ciudad = cfg.get("ciudad_pronostico_dmc")
    if not ciudad:
        return None
    try:
        t = get(f"{DMC}/meteochile/js/pronostico.js", "latin-1").replace("\r\n", "\n")
    except Exception as e:
        errores.append(f"DMC pronóstico: {e}"); return None
    for b in t.split("Pronostico.push(")[1:]:
        m = re.search(r'ciudad : "([^"]*)"', b)
        if not m or limpio(m[1]) != ciudad:
            continue
        fechas = [limpio(x) for x in re.findall(r'"([^"]*)"', re.search(r"fecha : \[(.*?)\]", b).group(1))]
        temps = re.findall(r'"([^"]*)"', re.search(r"temperatura : \[(.*?)\]", b).group(1))
        tbloq = re.search(r"texto : \[(.*?)\]\],\s*\n\s*redaccion", b, re.S).group(1)
        textos = [[limpio(x) for x in re.findall(r'"([^"]*)"', fila)] for fila in re.findall(r"\[(.*?)\]", tbloq)]
        dias = []
        for i in range(2):  # hoy y mañana; tramos: madrugada, mañana, tarde, noche
            tr = textos[i] if i < len(textos) else []
            dias.append({"dia": fechas[i], "temp": temps[i] if i < len(temps) else "",
                         "madrugada": tr[0] if len(tr) > 0 else "", "manana": tr[1] if len(tr) > 1 else "",
                         "tarde": tr[2] if len(tr) > 2 else "", "noche": tr[3] if len(tr) > 3 else ""})
        return {"ciudad": ciudad, "dias": dias}
    errores.append(f"DMC pronóstico: no apareció '{ciudad}' (corre `clima.py listar`)"); return None


def dmc_ahora(cfg, errores):
    cod = cfg.get("estacion_dmc")
    if not cod:
        return None
    try:
        t = get(f"{DMC}/appdata/condicionactual.js", "latin-1")
    except Exception as e:
        errores.append(f"DMC observación: {e}"); return None
    m = re.search(rf"\['{cod}'\] = '([^']*)'", t)
    if not m:
        errores.append(f"DMC observación: sin dato de la estación {cod}"); return None
    p = m[1].split("|")
    fen = p[5]
    return {"estacion": ESTACIONES.get(cod, cod), "hora": p[1],
            "viento_kmh": p[3], "visibilidad_m": p[4], "fenomeno_metar": fen,
            "temp": p[6], "humedad": p[9], "texto": limpio(p[10]),
            "lloviendo": "RA" in fen or "SH" in fen or "DZ" in fen,
            "tormenta": "TS" in fen, "granizo": "GR" in fen or "GS" in fen,
            "fuerte": fen.startswith("+")}


def open_meteo(cfg, errores):
    vars_h = "precipitation,precipitation_probability,weather_code,cape,wind_gusts_10m,freezing_level_height"
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={cfg['lat']}&longitude={cfg['lon']}"
           f"&hourly={vars_h}&models={','.join(MODELOS)}&timezone=America/Santiago&forecast_days=2")
    try:
        return json.loads(get(url))
    except Exception as e:
        errores.append(f"Open-Meteo: {e}"); return None


def metro(cfg, errores):
    m = cfg.get("metro") or {}
    if not m.get("activo"):
        return None
    try:
        d = json.loads(get("https://www.metro.cl/api/estadoRedDetalle.php"))
    except Exception as e:
        errores.append(f"Metro: {e}"); return None
    mis_lineas = [x.lower() for x in m.get("lineas", [])]
    base = lambda n: re.sub(r"\s+L\d+[A-Za-z]?$", "", n).strip().lower()  # "Ñuñoa L3" -> "ñuñoa"
    mis_est = {base(e) for e in m.get("estaciones", [])}
    problemas, mios = [], []
    for linea, v in d.items():
        nombre = linea.upper()
        mia = linea.lower() in mis_lineas
        if str(v.get("estado")) != "1":
            txt = f"{nombre}: {v.get('mensaje_app') or v.get('mensaje') or 'no opera normal'}"
            problemas.append(txt)
            if mia: mios.append(txt)
        for e in v.get("estaciones", []):
            if str(e.get("estado")) != "1":
                txt = f"{nombre} {e['nombre']}: {e.get('descripcion_app') or e.get('descripcion')} {e.get('mensaje', '')}".strip()
                problemas.append(txt)
                if mia or base(e["nombre"]) in mis_est: mios.append(txt)
    otros = [p for p in problemas if p not in mios]
    return {"mis_lineas_ok": not mios, "mis_problemas": mios, "problemas": problemas,
            "otros_problemas": otros, "filtra_lineas": bool(mis_lineas or mis_est)}


# ---------- análisis ----------
def ventana(om, dia, h0, h1):
    """Resumen de una ventana horaria [h0, h1) de `dia` (date) combinando los 3 modelos."""
    H = om["hourly"]
    idx = [i for i, t in enumerate(H["time"])
           if datetime.fromisoformat(t).date() == dia and h0 <= datetime.fromisoformat(t).hour < h1]
    if not idx:
        return None
    r = {"mm_h_max": 0.0, "mm_total": [], "prob_max": 0, "tormenta": 0, "granizo": 0,
         "cape_max": 0, "racha_max": 0, "iso0_min": None, "modelos_con_lluvia": 0, "horas_lluvia": set()}
    for m in MODELOS:
        pr = [H.get(f"precipitation_{m}", [None] * len(H["time"]))[i] or 0 for i in idx]
        wc = [H.get(f"weather_code_{m}", [None] * len(H["time"]))[i] or 0 for i in idx]
        pp = [H.get(f"precipitation_probability_{m}", [None] * len(H["time"]))[i] or 0 for i in idx]
        cp = [H.get(f"cape_{m}", [None] * len(H["time"]))[i] or 0 for i in idx]
        gu = [H.get(f"wind_gusts_10m_{m}", [None] * len(H["time"]))[i] or 0 for i in idx]
        fz = [x for x in (H.get(f"freezing_level_height_{m}", [None] * len(H["time"]))[i] for i in idx) if x]
        r["mm_h_max"] = max(r["mm_h_max"], max(pr))
        r["mm_total"].append(round(sum(pr), 1))
        r["prob_max"] = max(r["prob_max"], max(pp))
        r["cape_max"] = max(r["cape_max"], max(cp))
        r["racha_max"] = max(r["racha_max"], max(gu))
        if fz:
            r["iso0_min"] = min(fz) if r["iso0_min"] is None else min(r["iso0_min"], min(fz))
        if any(c in TORMENTA for c in wc): r["tormenta"] += 1
        if any(c in GRANIZO for c in wc): r["granizo"] += 1
        if sum(pr) >= 0.5: r["modelos_con_lluvia"] += 1
        for i, x in zip(idx, pr):
            if x >= 0.3: r["horas_lluvia"].add(datetime.fromisoformat(H["time"][i]).hour)
    r["horas_lluvia"] = sorted(r["horas_lluvia"])
    r["mm_total_rango"] = f"{min(r['mm_total'])}–{max(r['mm_total'])}" if r["mm_total"] else "0"
    return r


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
PARTE_DIA = {"madrugada": (0, 6), "mañana": (6, 12), "tarde": (12, 20), "noche": (20, 24)}


def _momento(txt, fin):
    """'la tarde del martes 13 de octubre del 2026' -> datetime (inicio o fin de ese tramo)."""
    m = re.search(r"(madrugada|mañana|tarde|noche) del \w+ (\d+) de (\w+) del (\d{4})", txt.lower())
    if not m or m[3] not in MESES:
        return None
    h0, h1 = PARTE_DIA[m[1]]
    base = datetime(int(m[4]), MESES.index(m[3]) + 1, int(m[2]))
    return base + timedelta(hours=h1 if fin else h0)


def cubre(a, dia, h0, h1):
    """¿El aviso DMC `a` se superpone con la ventana [h0, h1) de `dia`? Si no se puede leer, se asume que sí."""
    d, h = _momento(a["desde"], False), _momento(a["hasta"], True)
    if d is None or h is None:
        return True
    w0 = datetime(dia.year, dia.month, dia.day, h0)
    return d < w0 + timedelta(hours=h1 - h0) and h > w0


def intensidad(mmh):
    if mmh < 0.3: return "sin lluvia"
    if mmh < 1: return "débil"
    if mmh < 4: return "moderada"
    return "fuerte"


def riesgo_granizo(v, alertas, ahora):
    if ahora and ahora["granizo"]: return "OBSERVADO AHORA"
    txt = " ".join((a["fenomeno"] + " " + a["observacion"]).lower() for a in alertas)
    if v["granizo"] >= 1: return "probable"
    if "granizo" in txt:
        return "probable (aviso DMC)" if v["modelos_con_lluvia"] >= 1 else "posible (aviso DMC; los modelos no ven lluvia en este tramo)"
    if v["tormenta"] >= 1 and v["cape_max"] >= 500: return "posible"
    return "bajo"


def riesgo_trayecto(v, alertas, met, ahora_aplica, ahora):
    """Estimación (no medición) de que el trayecto se complique. Devuelve (nivel, motivos)."""
    mot = []
    fuerte_dmc = [a for a in alertas if a["tipo"] in ("Alerta", "Alarma")]
    if met and not met["mis_lineas_ok"]: mot.append("tu Metro con problemas AHORA (" + "; ".join(met["mis_problemas"][:3]) + ")")
    if v["mm_h_max"] >= 4: mot.append(f"lluvia fuerte en el trayecto (hasta {v['mm_h_max']:.1f} mm/h)")
    if v["tormenta"] >= 2: mot.append("tormenta eléctrica en 2+ modelos")
    if fuerte_dmc: mot.append(f"{fuerte_dmc[0]['tipo']} DMC vigente: {fuerte_dmc[0]['fenomeno']}")
    if ahora_aplica and ahora and ahora["fuerte"] and ahora["lloviendo"]: mot.append(f"lluvia fuerte observada ahora en {ahora['estacion']}")
    if mot: return "ALTO", mot
    if v["mm_h_max"] >= 1 and v["modelos_con_lluvia"] >= 2: mot.append(f"lluvia moderada en el trayecto con {v['modelos_con_lluvia']}/3 modelos de acuerdo")
    if v["tormenta"] == 1: mot.append("1 modelo marca tormenta")
    if v["racha_max"] >= 50: mot.append(f"rachas de {v['racha_max']:.0f} km/h")
    if met and met["otros_problemas"] and not met["filtra_lineas"]:
        mot.append("incidencias en el Metro: " + "; ".join(met["otros_problemas"][:3]))
    if mot: return "MEDIO", mot
    return "BAJO", ["sin lluvia relevante en el trayecto"]


def veredicto(nivel_ida, granizo_ida, nivel_vuelta, turno):
    if turno == "manana":
        if nivel_ida == "ALTO" or str(granizo_ida).startswith(("probable", "OBSERVADO")):
            return "QUÉDATE EN CASA", "#b42318"
        if nivel_ida == "MEDIO" or nivel_vuelta == "ALTO":
            return "ANDA, PERO CON PARAGUAS Y OJO CON LA VUELTA", "#b54708"
        return "ANDA TRANQUILO", "#067647"
    # tarde: la decisión es la vuelta de hoy y la ida de mañana
    if nivel_vuelta == "ALTO":
        return "SAL ANTES O QUÉDATE: LA VUELTA SE COMPLICA", "#b42318"
    if nivel_vuelta == "MEDIO":
        return "VUELTA CON PARAGUAS", "#b54708"
    return "VUELTA SIN PROBLEMAS", "#067647"


# ---------- correo ----------
def fila(lbl, val):
    return f"<tr><td style='padding:4px 8px 4px 0;color:#667085;white-space:nowrap;vertical-align:top'>{lbl}</td><td style='padding:4px 0'>{val}</td></tr>"


def bloque_ventana(titulo, v, nivel, motivos, granizo):
    if v is None:
        return f"<p><b>{titulo}</b>: sin datos.</p>"
    horas = ", ".join(f"{h}h" for h in v["horas_lluvia"]) or "ninguna"
    color = {"ALTO": "#b42318", "MEDIO": "#b54708", "BAJO": "#067647"}[nivel]
    iso = f"{v['iso0_min']:.0f} m" if v["iso0_min"] else "s/d"
    return (f"<h3 style='margin:18px 0 6px;font-size:15px'>{titulo}</h3><table style='font-size:14px;border-collapse:collapse'>"
            + fila("Lluvia", f"{intensidad(v['mm_h_max'])} · máx {v['mm_h_max']:.1f} mm/h · total {v['mm_total_rango']} mm")
            + fila("Probabilidad", f"{v['prob_max']}% · {v['modelos_con_lluvia']}/3 modelos con lluvia")
            + fila("Horas con lluvia", horas)
            + fila("Tormenta", f"{v['tormenta']}/3 modelos")
            + fila("Granizo", granizo)
            + fila("Rachas", f"{v['racha_max']:.0f} km/h")
            + fila("Isoterma 0°", iso)
            + fila("Riesgo del trayecto", f"<b style='color:{color}'>{nivel}</b> — " + "; ".join(motivos))
            + "</table>")


def armar(cfg, turno, out_dir):
    errores = []
    ahora_dt = datetime.now()
    hoy, manana = ahora_dt.date(), ahora_dt.date() + timedelta(days=1)
    al, pro, obs = dmc_alertas(cfg, errores), dmc_pronostico(cfg, errores), dmc_ahora(cfg, errores)
    om, met = open_meteo(cfg, errores), metro(cfg, errores)
    alertas = al["vigentes"] if al else []
    (i0, i1), (v0, v1) = cfg["ida"], cfg["vuelta"]

    if turno == "manana":
        tramos = [(f"Ida hoy ({i0:02d}–{i1:02d} h)", hoy, i0, i1, True), (f"Vuelta hoy ({v0}–{v1} h)", hoy, v0, v1, False)]
    else:
        tramos = [(f"Vuelta hoy ({v0}–{v1} h)", hoy, v0, v1, True), (f"Ida mañana ({i0:02d}–{i1:02d} h)", manana, i0, i1, False)]
    res = []
    for nombre, d, h0, h1, aplica_ahora in tramos:
        v = ventana(om, d, h0, h1) if om else None
        al_tramo = [a for a in alertas if cubre(a, d, h0, h1)]
        if v:
            g = riesgo_granizo(v, al_tramo, obs if aplica_ahora else None)
            n, mot = riesgo_trayecto(v, al_tramo, met if aplica_ahora else None, aplica_ahora, obs)
        else:
            g, n, mot = "s/d", "MEDIO", ["sin datos del modelo: no se puede descartar"]
        res.append({"tramo": nombre, "ventana": v, "granizo": g, "riesgo": n, "motivos": mot})

    if turno == "manana":
        ver, col = veredicto(res[0]["riesgo"], res[0]["granizo"], res[1]["riesgo"], turno)
    else:
        ver, col = veredicto(None, None, res[0]["riesgo"], turno)
    dia_om = ventana(om, hoy, 0, 24) if om else None
    comuna = cfg["comuna"]

    # --- HTML ---
    h = [f"<div style='font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:640px;color:#101828;font-size:14px;line-height:1.45'>",
         f"<div style='background:{col};color:#fff;padding:14px 16px;border-radius:8px;font-size:18px;font-weight:700'>{ver}"
         + (f"<div style='font-size:14px;font-weight:400;margin-top:4px'>Mañana temprano: riesgo {res[1]['riesgo']}</div>" if turno == "tarde" else "")
         + "</div>"]
    if alertas:
        h.append("<h3 style='margin:18px 0 6px;font-size:15px'>Avisos oficiales DMC para tu región</h3><ul style='padding-left:18px;margin:0'>")
        for a in alertas:
            h.append(f"<li><b>{a['tipo']}: {a['fenomeno']}</b> — desde {a['desde']} hasta {a['hasta']}. {a['observacion']}</li>")
        h.append("</ul>")
    elif al is not None:
        h.append("<p style='margin:14px 0 0'>Sin avisos, alertas ni alarmas de la DMC para tu región.</p>")
    else:
        h.append("<p style='margin:14px 0 0;color:#b42318'>No se pudo leer el sistema de avisos de la DMC: revisa meteochile.gob.cl antes de decidir.</p>")
    if obs:
        h.append(f"<p style='margin:12px 0 0'><b>Ahora en {obs['estacion']} ({obs['hora']}):</b> {obs['texto']}, {obs['temp']}°C, viento {obs['viento_kmh']} km/h"
                 + (f", visibilidad {obs['visibilidad_m']} m" if obs['visibilidad_m'] not in ('', '9999') else "")
                 + (f" <span style='color:#b42318'>(METAR {obs['fenomeno_metar']})</span>" if obs['fenomeno_metar'] else "") + ".</p>")
    for r in res:
        h.append(bloque_ventana(r["tramo"], r["ventana"], r["riesgo"], r["motivos"], r["granizo"]))
    if dia_om:
        h.append(f"<p style='margin:14px 0 0'><b>Día completo hoy:</b> {dia_om['mm_total_rango']} mm según modelo; máx {dia_om['mm_h_max']:.1f} mm/h; rachas hasta {dia_om['racha_max']:.0f} km/h.")
        if dia_om["racha_max"] >= 50 or dia_om["mm_h_max"] >= 4:
            h.append(" <b>Riesgo de corte de luz:</b> si te quedas en casa, deja cargado el notebook y el teléfono.")
        h.append("</p>")
    if pro:
        h.append(f"<h3 style='margin:18px 0 6px;font-size:15px'>Pronóstico oficial DMC · {pro['ciudad']}</h3><table style='font-size:14px;border-collapse:collapse'>")
        for d in pro["dias"]:
            partes = [f"{k}: {d[k]}" for k in ("manana", "tarde", "noche") if d[k]]
            h.append(fila(f"{d['dia']} ({d['temp']}°)", " · ".join(partes).replace("manana:", "mañana:")))
        h.append("</table>")
    if met is not None:
        met_txt = "Red operando normal." if not met["problemas"] else "; ".join(met["problemas"])
        h.append(f"<p style='margin:14px 0 0'><b>Metro ahora:</b> {met_txt}</p>")
    if errores:
        h.append(f"<p style='color:#b42318;margin:12px 0 0'><b>Fuentes que fallaron:</b> {'; '.join(errores)}</p>")
    h.append("<p style='color:#98a2b3;font-size:12px;margin:18px 0 0'>Fuentes: DMC meteochile.gob.cl (avisos, pronóstico, estación) · "
             "Open-Meteo con ECMWF, GFS y best_match" + (" · metro.cl/api" if met is not None else "")
             + ". El riesgo del trayecto es una estimación por lluvia y avisos, no un dato oficial. "
             f"Generado {ahora_dt:%d-%m-%Y %H:%M}.</p></div>")

    hora_turno = "mañana" if turno == "manana" else "tarde"
    asunto = f"Clima {comuna} ({hora_turno}) — {ver.capitalize()} ({ahora_dt.day} de {MESES[ahora_dt.month-1]})"
    data = {"generado": ahora_dt.isoformat(timespec="minutes"), "turno": turno, "comuna": comuna,
            "correo": cfg.get("correo", ""), "asunto": asunto, "veredicto": ver,
            "tramos": [{**r, "ventana": {k: v for k, v in (r["ventana"] or {}).items() if k != "mm_total"}} for r in res],
            "alertas_dmc": alertas, "dmc_actualizado": al["actualizado"] if al else None,
            "observacion": obs, "metro": met, "pronostico_dmc": pro, "errores": errores}
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{ahora_dt:%Y-%m-%d-%H%M}")
    open(base + ".html", "w").write("".join(h))
    json.dump(data, open(base + ".json", "w"), ensure_ascii=False, indent=1)
    data["html_path"] = base + ".html"
    return data


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "buscar":
        buscar(" ".join(sys.argv[2:])); sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "listar":
        listar(); sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("--turno", choices=["manana", "tarde"],
                    default="manana" if datetime.now().hour < 12 else "tarde")
    ap.add_argument("--out", default=os.path.expanduser("~/.claude/clima-comuna"))
    a = ap.parse_args()
    d = armar(cargar_config(), a.turno, a.out)
    print(json.dumps(d, ensure_ascii=False, indent=1))
    sys.exit(0 if not d["errores"] else 3)
