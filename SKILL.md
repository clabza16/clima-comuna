---
name: clima-comuna
description: Reporte del clima de MI comuna en Chile para decidir si voy presencial o trabajo desde la casa. Dice si va a llover justo cuando voy o vuelvo, con qué intensidad, si puede granizar, los avisos y alertas oficiales de la DMC, y (en Santiago) si el Metro está fallando ahora. Úsala cuando diga "cómo está el clima", "va a llover hoy", "¿me quedo en casa?", "¿voy presencial?", "va a granizar", "cómo está el metro con la lluvia", "mándame el clima", "reporte del clima", o cuando corra la tarea programada del clima. También para configurarla: "configura la skill del clima para mi comuna".
---

# Clima de tu comuna: ¿presencial o en casa?

**El entregable es un veredicto en la primera línea** ("QUÉDATE EN CASA", "ANDA, PERO CON
PARAGUAS…", "ANDA TRANQUILO") y debajo, la evidencia. Se lee en el teléfono antes de salir: si hay
que bajar para saber qué hacer, falló.

> **La idea:** lo que importa no es "va a llover", es **si llueve fuerte justo cuando vas o
> vuelves**, y si eso complica el trayecto. Por eso el reporte mira **tus horas de ida y vuelta**,
> no el día completo, y cruza tres modelos del clima con la fuente oficial chilena.

## Si todavía no está configurada (no existe `config.json`)

Pregúntale a la persona, en un solo mensaje: **su comuna**, a qué hora sale y vuelve (por defecto
ida 07–10 h y vuelta 17–21 h), si anda en Metro de Santiago y en qué líneas, y si quiere el reporte
por correo (a qué dirección) o en el chat. Después:

1. `python3 scripts/clima.py buscar "<comuna>"` → toma `lat` y `lon` del resultado chileno correcto.
2. `python3 scripts/clima.py listar` → elige:
   - `ciudad_pronostico_dmc`: la ciudad de pronóstico más cercana, escrita **igual** que en la lista.
     En Santiago hay cinco sectores: Oriente (Las Condes, Vitacura, Lo Barnechea, Providencia, Ñuñoa,
     La Reina, Peñalolén, Macul), Centro (Santiago, Independencia, Recoleta, Estación Central, San
     Miguel, San Joaquín), Norte (Quilicura, Huechuraba, Conchalí, Renca), Sur (La Florida, Puente
     Alto, San Bernardo, La Cisterna, El Bosque, La Granja, La Pintana, San Ramón, Lo Espejo, PAC) y
     Poniente (Maipú, Pudahuel, Cerrillos, Lo Prado, Cerro Navia, Quinta Normal). Si la comuna no
     está, elige la más cercana y díselo.
   - `estacion_dmc`: la estación más cercana de la lista (código de 4 letras).
3. `region_dmc`, según la región de la comuna:

   | Región | Código | Región | Código |
   |---|---|---|---|
   | Arica y Parinacota | `01a` | O'Higgins | `06` |
   | Tarapacá | `01b` | Maule | `07` |
   | Antofagasta | `02` | Ñuble | `08a` |
   | Atacama | `03` | Biobío | `08b` |
   | Coquimbo | `04` | La Araucanía | `09` |
   | Valparaíso | `05` | Los Ríos | `10a` |
   | **Metropolitana** | `05m` | Los Lagos | `10b` |
   | | | Aysén | `11` |
   | | | Magallanes | `12` |

   **Y elige `zonas_dmc`**: la DMC emite cada aviso para franjas de la región, no para la región
   entera. Las franjas son `Litoral` (la costa), `Cordillera_Costa`, `Valle_Longitudinal` (el valle
   central, donde está la mayoría de las ciudades), `Precordillera` y `Cordillera`, más algunas
   propias del norte y del sur (`Chiloe`, `Pampa_Patagonica_Norte`…). Pon 1 o 2 franjas donde cae la
   comuna, con el prefijo de la región: Valparaíso → `["05_Litoral"]`, Ñuñoa →
   `["05m_Valle_Longitudinal"]`, Las Condes → `["05m_Valle_Longitudinal", "05m_Precordillera"]`,
   Temuco → `["09_Valle_Longitudinal"]`. Sin `zonas_dmc` se toman los avisos de toda la región: en
   una comuna costera eso trae falsas alarmas de la cordillera. Los avisos que la DMC emite para la
   región completa (código solo, como `09`) se toman siempre.
4. Escribe `config.json` junto a este `SKILL.md`, con la forma de `config.ejemplo.json`. El Metro
   (`metro.activo: true`) solo existe para Santiago; `lineas` en minúscula (`l1`, `l4a`…) y
   `estaciones` con el nombre de la estación (sin la línea: `Ñuñoa`, no `Ñuñoa L3`).
5. Corre el reporte una vez (paso de abajo) y muéstrale el veredicto para que confirme que es su comuna.
6. Ofrécele programarlo de lunes a viernes: una hora antes de que salga (`--turno manana`) y a
   las 14:00 (`--turno tarde`; si vuelve antes de las 17, tres horas antes de la vuelta). Usa la herramienta de tareas programadas que tengas; si no hay, dile cómo
   pedírselo a su app de Claude.

## Cada vez que corre

1. **Fecha real:** `date "+%Y-%m-%d %H:%M %A"`. Antes de las 12 → turno `manana`; después → `tarde`.
2. **Correr el script:**
   ```bash
   python3 scripts/clima.py --turno <manana|tarde>
   ```
   (la ruta es relativa a la carpeta de esta skill). Devuelve JSON por stdout (`asunto`,
   `veredicto`, `tramos`, `alertas_dmc`, `metro`, `errores`, `html_path`, `correo`) y guarda
   `.html` + `.json` en `~/.claude/clima-comuna/`. Exit 3 = alguna fuente falló: el reporte igual
   sale y lo dice en rojo.
3. **Solo si algún tramo sale MEDIO o ALTO** y hay Metro: una búsqueda web (`estado Metro Santiago
   hoy lluvia`) para ver cierres que la API aún no muestre. Si hay algo con fecha de hoy, agrégalo
   como **una línea** al final del HTML, con link.
4. **Entregar:**
   - Si `correo` tiene una dirección **y** tienes una herramienta para mandar correos (por ejemplo
     Gmail), envíalo: asunto = `asunto`, cuerpo HTML = contenido de `html_path`, y en texto plano el
     veredicto y los motivos.
   - Si no hay correo o no tienes cómo enviarlo: muestra el reporte en el chat. **Nunca digas que lo
     enviaste si no lo enviaste.**
5. **En el chat:** el veredicto, el riesgo de cada tramo en una línea, y si se envió o no.

## Cómo decide

- **Intensidad:** débil < 1 mm/h · moderada 1–4 · **fuerte ≥ 4** (con 4 mm/h ya se anegan calles).
- **Riesgo del trayecto = ALTO** si en tu ventana hay: lluvia fuerte, tormenta en 2+ modelos, una
  Alerta o Alarma DMC que cubre esas horas, tus líneas de Metro con problemas ahora, o lluvia fuerte
  observada ahora. **MEDIO** si: lluvia moderada con 2+ modelos de acuerdo, 1 modelo con tormenta,
  rachas ≥ 50 km/h, o problemas en otras líneas. **Es una estimación**, no un dato oficial; el
  reporte lo dice.
- **Granizo:** OBSERVADO (la estación reporta `GR`/`GS`) > probable (un modelo marca granizo, o un
  aviso DMC de granizo con lluvia en tu ventana) > posible (tormenta + CAPE ≥ 500, o aviso DMC sin
  lluvia en los modelos) > bajo.
- **Los avisos DMC cuentan solo en las horas que cubren** ("la tarde del martes 13" = 12–20 h).
- **Veredicto de la mañana:** ida ALTO o granizo probable → CASA · ida MEDIO o vuelta ALTO → ANDA
  CON PARAGUAS · resto → ANDA. **De la tarde:** decide la vuelta de hoy y anticipa la ida de mañana.
- **Corte de luz:** con rachas ≥ 50 km/h o lluvia fuerte, avisa "deja cargado el notebook": quedarse
  en casa también tiene su riesgo.

## Fuentes (todas en vivo, sin API key)

| Fuente | Qué aporta |
|---|---|
| DMC `archivos.meteochile.gob.cl/portaldmc/AAA/datos_AAA.js` | Avisos, alertas y alarmas oficiales de tu región |
| DMC `meteochile/js/pronostico.js` | Pronóstico oficial por tramo del día, de tu ciudad |
| DMC `appdata/condicionactual.js` | Lo que está pasando ahora en la estación más cercana |
| Open-Meteo (ECMWF, GFS, best_match) | Hora a hora: mm/h, probabilidad, tormenta y granizo, rachas |
| Metro `metro.cl/api/estadoRedDetalle.php` | Estado de cada línea y estación ahora (solo Santiago) |

## Si algo falla

- **"Sin avisos" con mal tiempo evidente:** la DMC sirve sus archivos con saltos de línea de Windows;
  el script ya los normaliza. Si vuelve a pasar, revisa eso primero.
- **Si una fuente falla, el reporte lo dice.** Nunca "sin avisos" cuando en realidad no se pudo leer.
- **La tarea programada solo corre con el computador encendido y Claude abierto.** Si a las 08:00
  está apagado, ese reporte no sale.
- **"no apareció la ciudad":** el nombre en `ciudad_pronostico_dmc` tiene que ser idéntico al de
  `clima.py listar` (con tildes).
