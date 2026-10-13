# clima-comuna

Una skill para Claude que te dice, antes de salir, **si te conviene ir presencial o trabajar desde
la casa**. Mira el clima de tu comuna justo en tus horas de ida y vuelta, los avisos oficiales de la
Dirección Meteorológica de Chile y, si vives en Santiago, si el Metro está fallando ahora.

Nació un día de tormenta con granizo en Santiago en que llegué empapado a la casa.

## Qué te entrega

Un reporte con el veredicto en la primera línea:

- **QUÉDATE EN CASA**
- **ANDA, PERO CON PARAGUAS Y OJO CON LA VUELTA**
- **ANDA TRANQUILO**

Y debajo, por qué: cuánta lluvia y a qué hora, si puede granizar, los avisos y alertas de la DMC,
qué está pasando ahora en la estación más cercana y el estado del Metro.

## Requisitos

- **Claude Code** (la app de escritorio de Claude, pestaña Code, o la terminal).
- Python 3 (viene en Mac y Linux). No necesita llaves ni cuentas: todas las fuentes son públicas.
- Opcional: Gmail conectado a Claude, si quieres el reporte por correo. Si no, te lo muestra en el chat.

## Instalación (la forma fácil)

Pégale esto a Claude Code, cambiando tu comuna:

> Instala la skill de https://github.com/clabza16/clima-comuna en ~/.claude/skills/clima-comuna y
> configúrala para la comuna de **Ñuñoa**.

Claude la descarga, te pregunta a qué hora sales y vuelves, busca tu estación y tu pronóstico
oficial, y te muestra el primer reporte.

## Instalación a mano

```bash
git clone https://github.com/clabza16/clima-comuna ~/.claude/skills/clima-comuna
cd ~/.claude/skills/clima-comuna
cp config.ejemplo.json config.json
python3 scripts/clima.py buscar "Tu Comuna"   # coordenadas
python3 scripts/clima.py listar               # ciudades de pronóstico y estaciones de la DMC
```

Edita `config.json` con lo que encontraste (la tabla de regiones está en `SKILL.md`) y prueba:

```bash
python3 scripts/clima.py --turno manana
```

## Que llegue solo todos los días

Dile a Claude:

> Programa la skill del clima de lunes a viernes a las 8:00 y a las 14:00.

A las 8 decide la ida de hoy; a las 14, la vuelta de hoy y la ida de mañana. Ojo: las tareas
programadas corren solo con el computador encendido y Claude abierto.

## Lo que no hace

- No es un pronóstico oficial: la decisión es una **estimación** con datos oficiales y modelos.
- El estado del Metro solo existe para Santiago. En otras ciudades mira solo el clima y los avisos.

## Guía paso a paso

https://www.consultoria-info.cl/guia-clima

---

Hecha por [Claudio Albornoz](https://www.instagram.com/calbornoz.ia/) · ConsultorIA. Licencia MIT.
