He revisado el backend con el subagente `healthcare-reviewer`. No he modificado ningún archivo. Por mi cuenta he comprobado algunos hallazgos directamente en el código: el CORS `*`, el endpoint de subida, el `debug_info` que se envía siempre, la clave por defecto, la consulta enviada en la URL y el mensaje fijo en castellano. Todos coinciden. El resto de los hallazgos vienen de la lectura del agente.

**Veredicto: no debería usarse con pacientes reales hasta corregir los puntos Crítico y Alto.**

Hay que tener en cuenta algo importante: el backend no contiene ninguna dosis ni pauta escrita en el código. Todo el contenido clínico sale del RAG y del LLM. Por eso las pautas (2HRZE/4HR, 3HP, BPaLM…) no se pueden comprobar en `backend/`. Hay que auditarlas en `documents/` y `vector_db/`.

## Crítico

| # | Archivo:línea | Problema | Por qué importa clínicamente | Arreglo |
|---|---|---|---|---|
| C1 | `backend/main.py:733-755`, `:40` | `/api/upload` no pide autenticación y tiene *path traversal* (usa `category` y `filename` sin limpiar). El PDF se indexa al momento en la colección que usan los dos chats. Con CORS `*` y multipart, cualquier web que visite el usuario puede subir un PDF. | Un PDF con "isoniazida 30 mg/kg" pasaría a ser una "fuente" citada, y el verificador la daría por válida. | Sacar la ingesta del servidor y dejarla solo en el script de indexación, o protegerla con un token de administrador. Usar `basename` y comprobar con `realpath`, validar la cabecera `%PDF`, limitar el tamaño y restringir CORS. Indexar en una colección "pendiente de revisión". |
| C2 | `backend/main.py:339-369` (llamado en 522-562, 727) | `/api/chat` guarda el texto completo de la pregunta en `usage_patterns.jsonl`, también en los casos de autolesión y alertas rojas, sin anonimizar ni fijar plazo de conservación. Si falla la escritura, se ignora con `except: pass`. | Son datos de salud de categoría especial (art. 9 RGPD), guardados sin base jurídica ni EIPD. | No guardar nunca `question`, y menos en `red_flag_*`, `urgencia_*` o `riesgo_autolesion`. Si hace falta el texto, seudonimizarlo, conservarlo como mucho 30 días y registrar los fallos de escritura con `logging`. |
| C3 | `backend/rag.py:265`, `:449`; `main.py:1416,1429,1442`; `main.py:174,271` | La pregunta del paciente viaja en la URL (`params={"query":…}`) hacia el motor SOTA y en los GET de traducción y búsqueda. Termina en los access logs de `~/tbc_stack_logs/`. Además, con `print` se vuelca la salida del verificador. | Hay datos de salud en logs persistentes que nadie controla. | Pasar a POST con cuerpo JSON, arrancar uvicorn con `--no-access-log` (o con un filtro) y cambiar los `print` por `logging` en nivel DEBUG. |
| C4 | `backend/safety.py:161-174, 187-200, 234-244`; `main.py:874, 920-925` | Los detectores de salida (filtración de conocimiento general, negativas, "no lo sé") solo reconocen frases en castellano. En catalán, árabe y urdu la respuesta sale sin filtrar. Además, en ar/ur se aplica directamente el umbral de relevancia más permisivo. | Los pacientes con barrera idiomática, los más vulnerables, son justo los que reciben menos protección. | Generar y verificar siempre en castellano y traducir después. Mientras tanto, quitar el umbral permisivo por defecto en ar/ur y clasificar la pregunta sobre su traducción. |

## Alto

| # | Archivo:línea | Problema | Por qué importa | Arreglo |
|---|---|---|---|---|
| A1 | `main.py:128-179, 682-710, 966-980` | El verificador de afirmaciones solo informa. Si detecta dosis o duraciones sin respaldo, la respuesta se envía igualmente con una nota genérica. Si el verificador falla (devuelve `None`), con cobertura alta o media la respuesta sale **sin aviso**. Además solo ve 6000 caracteres del contexto. | Una dosis inventada y detectada llega igualmente al paciente. | Si alguna afirmación sin respaldo contiene cifras, unidades o fármacos, bloquear o regenerar la respuesta. Tratar `None` como riesgo (fallar cerrado). Verificar con el mismo contexto completo que vio el generador. |
| A2 | `main.py:692, 722, 970, 987` | `debug_info` se añade sin mirar `request.debug`. Así, `/api/patient-chat` devuelve siempre la respuesta completa de Mistral (`response_b`), que no pasa por ningún guardarraíl. | Llega al cliente contenido clínico sin filtrar. | Añadir `debug_info` solo `if request.debug`, y en el endpoint de pacientes solo con un token de desarrollador. |
| A3 | `main.py:546-555, 877-883`; `rag.py:248-272` | Las alertas del motor SOTA (p. ej. toxicidad ocular por etambutol) solo se consultan si el RAG local falla. Si el motor no responde en 8 s, la alerta se pierde sin dejar rastro. En pacientes, la alerta no se traduce. | Se pierden avisos de toxicidad en el caso más habitual, que es cuando el RAG sí encuentra fuentes. | Hacer una llamada de alertas independiente que se ejecute siempre, antes de generar. Validar el tipo de `alerts`, usar plantillas traducidas y, si el motor falla, añadir una nota de derivación. |
| A4 | `main.py:434-450, 453-515` | Si el clasificador de intención falla, todo se trata como una consulta normal (falla abierto). Las reglas deterministas no cubren disnea, dolor torácico, fiebre persistente, exantema (SJS/DRESS), vómitos o dolor abdominal, confusión ni convulsiones. La alerta visual exige que se escriba "etambutol". Todo está solo en castellano y sin normalizar tildes. | Síntomas de alarma reales no generan derivación. | Si el clasificador falla, añadir siempre una línea de derivación. Ampliar los síntomas, normalizar acentos, quitar el requisito del nombre del fármaco y añadir listas en ca/ar/ur revisadas por hablantes nativos. |
| A5 | (ausencia); `safety.py:34-35`; `rag.py:597` | No hay ninguna regla sobre interacciones de rifampicina o rifapentina con antirretrovirales, anticonceptivos, anticoagulantes, metadona o azoles, ni sobre la piridoxina con isoniazida. `get_drug_safety_info` existe, pero los chats no la usan. | Riesgo de fallo anticonceptivo, INR fuera de rango, abstinencia a metadona o fracaso del tratamiento antirretroviral. | Crear una tabla determinista y versionada de interacciones, validada con farmacia y con CIMA, que añada un aviso fijo diga lo que diga el LLM. |
| A6 | `main.py:910`; `prompts.py:29`; `main.py:1442-1457`; `languages.py:9-11` | La traducción la hace el LLM y nada comprueba que cifras y unidades se mantengan. Las plantillas en ar/ur están "pendientes de revisión por un hablante nativo". | Una dosis o una duración pueden cambiar al traducirse. | Extraer por regex números y unidades del original y de la traducción y compararlos. Si no coinciden, enviar la versión en castellano más un aviso. Hacer revisar las plantillas por nativos. |
| A7 | `main.py:588-614` | Al generador solo le llegan `context_parts[:7]`, pero se muestran como fuentes todas, hasta 10, y el verificador también las recibe todas. No se comprueba que las citas `(Fuente: X, p.N)` existan de verdad. | Atribuciones falsas, y la verificación da por buenas afirmaciones contra textos que el generador nunca vio. | Usar los mismos 7 elementos para fuentes, generación y verificación, y validar las citas con regex. |
| A8 | `backend/config.py:36` | La clave tiene un valor por defecto escrito en el código: `"tbc_ia_secret_v7"`. | Cualquiera con el repositorio conoce la clave del motor SOTA. | Usar `os.environ[...]` sin valor por defecto, para que falle al arrancar si falta, y **rotarla** porque ya está en el historial de git. |
| A9 | `main.py:518, 839, 282` | Ningún endpoint tiene autenticación. Un paciente puede usar el modo profesional, que además guarda las preguntas (C2). `top_k` no tiene límite. | Exposición de datos y posible denegación de servicio. | Token por perfil, CORS restringido y `top_k` limitado entre 1 y 10. |

## Medio

- **M1, `main.py:914,925`**: en el chat de pacientes, el mensaje de "sin información" sale siempre en castellano aunque ya existe la versión traducida (`canned_no_info`, línea 842). Hay que usar la versión traducida.
- **M2, `main.py:564,623,891`; `languages.py:21-26`**: el mensaje de "sin información" no indica a quién acudir. Añadir "Consulta a tu equipo de TB o a tu centro de salud".
- **M3, `safety.py:247-251`**: el filtro de palabras clave busca subcadenas, así que "tos" coincide con "da**tos**" y "alta" con "f**alta**n". En la práctica casi siempre se aplica el umbral permisivo de 750. Buscar por palabra completa con `\b` y calibrar los umbrales con el banco de 560 preguntas.
- **M4, `prompts.py:22`**: la regla 8 deja que el LLM deduzca la duración de una pauta a partir del contexto. Puede aplicar 6 meses a una TB meníngea u osteoarticular, a TB-RR o a niños. Exigir que la respuesta diga a qué población se refiere y añadir un aviso automático si la pregunta menciona meníngea, ósea, embarazo, niño, VIH o resistencias.
- **M5, `main.py:275-277, 323-336`**: el historial lo manda el cliente con `role` libre, así que se pueden colar "respuestas previas" falsas. Validar `role` con `Literal` y, en pacientes, incluir solo los turnos del usuario.
- **M6, `main.py:588-604`**: los resúmenes de PubMed se mezclan con las guías en el mismo contexto. Etiquetarlos como "evidencia de investigación, no recomendación" o mostrarlos aparte.
- **M7, `main.py:924-980`**: se verifica el propio mensaje de "sin información" y se le puede añadir la nota de riesgo, lo que da un mensaje contradictorio. Saltarse la verificación cuando la respuesta es ese mensaje.
- **M8, `llm.py:25-36`**: `ollama.chat` no tiene timeout. Si falla, el usuario recibe un error 500 sin ningún mensaje de derivación. Usar `Client(timeout=…)` y devolver el mensaje de "sin información" con derivación.

## Bajo

- **B1, `main.py:520-527`**: en el modo profesional, una pregunta docente sobre síntomas de alarma recibe el mensaje fijo del 112. Conviene una plantilla propia para profesionales.
- **B2, `main.py:300-301`**: `/api/health` devuelve al cliente el texto de la excepción (`str(e)`).
- **B3, `main.py:414,434`**: hay parámetros `timeout` que no se usan.
- **B4, `main.py:654-665` y `rag.py:239`**: la cobertura usa `distances[0]` y la relevancia usa `min(distances)`. Es incoherente, aunque conservador.
- **B5, `main.py:1429-1439`**: la búsqueda en vivo envía el texto a NCBI sin avisar y sin filtrar artículos retractados. Avisar en la interfaz de que no se metan datos de pacientes.
- **B6**: `main.py` tiene 1474 líneas (el límite del proyecto es 800), con unas 370 de HTML dentro del código.

## Lo que está bien resuelto

- El router de seguridad se ejecuta antes del RAG y de la generación, y las plantillas de 112 y 024 existen en 4 idiomas.
- Los prompts obligan a responder solo con el contexto recuperado.
- Si el motor SOTA falla, no se genera nada sin contexto.
- La bibliografía retractada se descarta.
- `/api/document` está protegido contra *path traversal*.
- El servidor escucha solo en 127.0.0.1.
- `/api/patient-chat` no guarda la pregunta.

## Lo que no se ha revisado

- Las guías indexadas en `documents/` y `vector_db/`: si conviven versiones obsoletas, por ejemplo de antes de la OMS 2022 (BPaLM, pauta de 4 meses).
- El código del motor SOTA (`tbc-ia-sota-engine/app/main.py`): sus logs y el formato de `alerts`.
- Los frontends: si muestran `debug_info` o guardan datos de pacientes en localStorage.
- Si el banco de 560 preguntas cubre síntomas de alarma, interacciones y otros idiomas.
- La calibración real de los umbrales.

Mi recomendación es empezar por **C1, C2, A2 y A8**: son arreglos acotados y cierran el envenenamiento de fuentes, la fuga de datos y la salida sin filtrar. Después, **A1, A4 y C4**, que son los guardarraíles que hoy dejan pasar la respuesta cuando fallan.
