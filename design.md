# Sistema de diseño — TBC-IA

Sistema visual único aplicado a las cinco superficies web del proyecto:

| Superficie | Archivo | Sirve en |
|---|---|---|
| Panel de inicio | `backend/main.py` (`home()`) | `http://127.0.0.1:8001/` |
| Chat de guías clínicas | `frontend_guides/index.html` | `/guides/` |
| Chat + panel de pacientes | `frontend_patient/index.html`, `style.css`, `script.js` | `/patient/` |
| Buscador de la base de conocimiento (ES/CA) | `frontend_patient/buscador.html`, `frontend_patient/kb/buscador.html` | páginas independientes (ver hallazgos) |
| Panel de estado de servicios | `dashboard/dashboard_service.py` (`DASHBOARD_HTML`) | `http://127.0.0.1:8090/` |

Antes de este trabajo, cada superficie tenía su propia paleta (crema/terracota en inicio y guías, verde-azulado en pacientes, tema oscuro estilo "devops" en el panel de servicios, gris plano en el buscador). Se ha extraído la paleta ya existente en `frontend_patient/style.css` — la más próxima a un estándar clínico — y se ha propagado al resto, en vez de inventar valores nuevos.

## Paleta

| Uso | Color | Hex |
|---|---|---|
| Primario (acciones, enlaces, foco) | Teal | `#1F6F72` |
| Primario oscuro (hover, texto sobre teal claro) | Teal oscuro | `#123F42` |
| Fondo de página | Verde-gris muy claro | `#EEF3F0` |
| Superficie (tarjetas, cabeceras, inputs) | Blanco | `#FFFFFF` |
| Texto principal | Verde-negro | `#152623` |
| Texto secundario | Verde-gris | `#4A5B57` |
| Bordes / líneas | Gris verdoso claro | `#D7E0DB` |
| Semántico — urgente / error | Coral | `#B8433A` sobre fondo `#FBEAE8` |
| Semántico — atención / pendiente | Ámbar | `#B4791E` sobre fondo `#FBF1DE` |
| Semántico — correcto / verificado | Salvia | `#4F8562` sobre fondo `#E9F2EA` |
| Etiqueta ITL / info secundaria | Teal claro | `#123F42` sobre fondo `#E4F1F1` |

Paleta deliberadamente sobria (verdes y azulados desaturados, sin colores saturados tipo "startup"), reservando coral/ámbar/salvia en exclusiva para estado clínico (urgente / pendiente / correcto) — nunca para decoración.

## Tipografía

- **Fraunces** (serif, 500/600/700) — títulos (`h1`, cabeceras de tarjeta, nombre de sección). Aporta el matiz "editorial/clínico" que distingue el proyecto de una interfaz genérica de SaaS.
- **Inter** (sans, 400/500/600/700) — cuerpo de texto, controles, botones.
- **IBM Plex Mono** (400/500) — datos técnicos: badges de estado, marcas de tiempo, puertos, enlaces de retorno (`back-link`).

Escala tipográfica (aprox., ya usada de forma consistente):
- h1 principal: 26–28px (Fraunces 600)
- h1 secundario / cabecera de sección: 19–23px (Fraunces 600)
- cuerpo: 14px (Inter 400)
- texto secundario / metadatos: 12–13px (Inter 400/500)
- mono (badges, timestamps): 10.5–12px (IBM Plex Mono 500/600)

Las tres familias se cargan desde Google Fonts con el mismo `<link>` en las cinco superficies (antes el panel de servicios y el buscador usaban la fuente del sistema).

## Espaciado

- Unidad base: 8px (con 4px como subdivisión para ajustes finos de UI compacta: badges, iconos, chat).
- Escala objetivo: `4 / 8 / 12 / 16 / 20 / 24 / 32 / 40`.
- Radio de borde estándar: `8px` en controles, `10px` en tarjetas/burbujas de chat, `20px` en badges tipo píldora.
- El chat de pacientes (el componente más denso del sitio) usa algunos valores intermedios heredados (p. ej. `13px`, `10.5px`) para ajuste óptico en listas compactas de pacientes; se mantienen como excepción deliberada y no se han reescrito para no arriesgar regresiones visuales en un componente ya maduro.

## Componentes

- **Botones**: primario = fondo `--teal`, texto blanco, hover `--teal-dark`, radio 8px. Acciones destructivas/parar usan borde y texto `--coral` sobre fondo blanco (nunca relleno rojo sólido, para no competir visualmente con las alertas clínicas urgentes). Botón "ghost" = borde `--line`, fondo transparente.
- **Tarjetas**: fondo `--surface` blanco, borde 1px `--line`, radio 10px, sin sombra decorativa (solo `box-shadow` sutil en hover de las tarjetas de navegación de inicio, para indicar interactividad, no decoración).
- **Badges de estado**: forma píldora, fuente IBM Plex Mono, un color semántico por estado (`ok`→salvia, `down`/`urgente`→coral, `pendiente`→ámbar, `info`→teal claro). El mismo lenguaje de color se usa en el panel de servicios, el chat de pacientes y el chat de guías (antes cada uno usaba una paleta distinta: verde neón/rojo neón en el panel, verde/ámbar sin relación en guías).
- **Burbujas de chat**: mensaje propio = fondo `--teal`, texto blanco, alineado a la derecha; mensaje del asistente = fondo gris muy claro (`#F1F4F2`), alineado a la izquierda. Mismo patrón en `/guides/` y `/patient/`.
- **Formularios**: inputs con borde 1px `--line`, fondo `#fcfdfc`, radio 8px, foco visible (`outline: 2px solid var(--teal-dark)`) en todos los controles interactivos de las cinco superficies.
- **Iconografía**: sin iconos de stock; solo el logotipo SVG lineal (trazo tipo electrocardiograma) inline como favicon, ahora presente también en el panel de servicios (antes no tenía favicon).

## Hallazgos de la auditoría (antes de esta implementación)

Ver informe completo en el mensaje de cierre de la tarea. Resumen:
- Paleta inconsistente entre las 5 superficies (corregido).
- Panel de servicios sin favicon ni fuentes del sistema tipográfico del proyecto (corregido).
- `frontend_patient/buscador.html` referencia `buscador.js`, que no existe en ese directorio (solo en `frontend_patient/kb/`) — recurso roto, **no corregido** por ser un problema de estructura de archivos/JS, no de HTML/CSS visual.
- `buscador.html` y `kb/buscador.html` no están enlazados desde ninguna navegación activa (páginas huérfanas) — se han restyleado por consistencia pero no se ha añadido navegación nueva, para no alterar el comportamiento existente.
