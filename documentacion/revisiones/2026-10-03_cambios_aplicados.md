# Cambios aplicados tras las revisiones del 3 de octubre de 2026

Informes de origen: `2026-10-03_revision_seguridad_clinica.md` (healthcare-reviewer)
y `2026-10-03_revision_seguridad_api.md` (security-reviewer).

## Seguridad de la API y del sistema

| Hallazgo | Cambio |
|---|---|
| C1 / Crítico: `/api/upload` sin autenticación y con path traversal | Token de administrador (`TBC_ADMIN_TOKEN`), categoría y nombre validados, `realpath`, firma `%PDF-`, límite de 25 MB. Sin token configurado, la subida queda desactivada. |
| A8 / Alto: clave `tbc_ia_secret_v7` en el código | Eliminada y rotada. Una sola variable `TBC_API_KEY` en `.env` (no versionado); sin ella los servicios no arrancan. Comparación con `secrets.compare_digest`. |
| CORS `*` en 8001, 8002 y 8003 | 8001: solo 127.0.0.1/localhost:8001 y :8090. 8002 y 8003: sin CORS. `TrustedHostMiddleware` en los tres (DNS rebinding). |
| n8n escuchando en todas las interfaces | `N8N_LISTEN_ADDRESS=127.0.0.1`. Todos los servicios escuchan solo en 127.0.0.1 (comprobado con `lsof`). |
| C3: la pregunta viajaba en la URL y acababa en logs | Motor SOTA, bibliografía y traducción por POST con cuerpo JSON; `--no-access-log` / `access_log=False`; `print` sustituidos por `logging` sin contenido clínico; `~/tbc_stack_logs` con permisos 700. |
| Límites de entrada | Longitud de mensaje, historial, `top_k`, `limit`, idioma y roles validados con Pydantic. |
| XSS en la portada y en el frontend de pacientes | Datos de PubMed/CIMA y nombres de pacientes escapados; DOI validado. |
| Errores con `str(e)` | Mensajes genéricos al cliente. |
| XML de PubMed | `defusedxml`. |
| Dependencias vulnerables y Python 3.9 sin soporte | Los cuatro servicios migrados a Python 3.12 con dependencias actualizadas (transformers 5.x en el motor SOTA, con resultados idénticos comprobados). Entornos antiguos en `venv-py39-respaldo/` (no versionados). |
| Código sin uso que enviaba texto a un traductor externo (MyMemory) | Eliminado del frontend de pacientes. |

Queda sin actualizar **chromadb 0.5.20**: sus vulnerabilidades afectan al modo servidor HTTP, que TBC no usa (cliente integrado `PersistentClient`). Actualizarlo podría migrar o romper la base vectorial.

## Seguridad clínica

| Hallazgo | Cambio |
|---|---|
| C2: preguntas guardadas en `usage_patterns.jsonl` | Nunca se guarda el texto de la pregunta. Fallos de escritura registrados. **Pendiente de decisión**: el archivo existente conserva 61 preguntas antiguas (permisos 600). |
| C4: filtros solo en castellano | Las preguntas en ca/ar/ur se traducen al castellano antes del triaje, la búsqueda y la generación; la respuesta se verifica en castellano y se traduce al final. Se elimina el umbral permisivo por defecto en ar/ur. |
| A1: el verificador solo informaba | Afirmaciones no respaldadas con dosis/duraciones/pautas cuyas cifras no aparecen en las fuentes → la respuesta no se muestra. Verificador caído → nota de riesgo (falla cerrado). El verificador ve el mismo contexto que el generador. |
| A2: `debug_info` y respuesta cruda de Mistral siempre al paciente | Solo con `debug` y `TBC_DEV_MODE=1`. Mistral solo se ejecuta en modo debug. |
| A3: alertas del motor SOTA solo si el RAG fallaba | Nueva ruta `/v1/alerts` consultada siempre antes de generar; plantillas traducidas; motor caído → nota de riesgo. |
| A4: signos de alarma incompletos y clasificador que fallaba abierto | Nuevas reglas (disnea, dolor torácico, reacciones cutáneas graves, vómitos persistentes, confusión/convulsiones, fiebre alta persistente), normalización de tildes, alerta visual sin exigir "etambutol", términos básicos en catalán. Clasificador caído → línea de derivación. Chat profesional: aviso de urgencia antepuesto en vez de cortar la respuesta (B1). |
| A5: sin reglas de interacciones | Avisos fijos: rifamicinas con anticonceptivos, anticoagulantes, metadona/buprenorfina, antirretrovirales y azoles; antiepilépticos; piridoxina con isoniazida en grupos de riesgo. |
| A6: traducción sin comprobar cifras | La traducción se descarta si cambia alguna cifra; se muestra el castellano con un aviso. |
| A7: fuentes distintas para generar, citar y verificar | Las mismas 7 fuentes en los tres pasos; citas `(Fuente: X, p.N)` validadas. |
| M1–M8 | Mensaje "sin información" en el idioma del paciente y con derivación; filtro de palabras clave por inicio de palabra ("tos" ya no coincide con "datos"); aviso de poblaciones especiales y regla en los prompts; roles de historial validados y solo turnos del usuario en pacientes; PubMed etiquetado como evidencia de investigación; no se verifica el mensaje fijo; timeout del LLM con respuesta segura. |

Ajuste tras las pruebas en vivo: el verificador marcaba "3 meses" como no respaldado aunque la fuente decía "Three months of rifapentine and isoniazid". Antes de bloquear se comprueba de forma determinista si las cifras aparecen en las fuentes (como número o en palabras en inglés o castellano).

## Pruebas

- 107 tests (41 previos + 66 nuevos): `tests/test_clinical_rules.py`, `tests/test_api_security.py`.
- Ataques simulados contra los servicios reales: subida sin token (401), `Host` falso (400 en 8001/8002/8003), CORS externo (sin cabecera), clave antigua (401), traducción por GET (405).
- Preguntas reales con el modelo: urgencia → 112; `debug` no expone datos; interacción con anticonceptivos derivada; motor SOTA nuevo con resultados idénticos al anterior.

## Pendiente de validación humana

1. **Farmacia**: textos de interacciones en `backend/clinical_rules.py` (`INTERACTION_RULES`, `PYRIDOXINE_WARNING`).
2. **Hablantes nativos**: textos nuevos en árabe y urdu de `backend/languages.py`.
3. **Equipo clínico**: lista de signos de alarma y poblaciones especiales; contenido de `documents/` y `vector_db/` (versiones obsoletas de guías, p. ej. anteriores a OMS 2022).
4. Calibrar los umbrales de relevancia con el banco de 560 preguntas tras el cambio del filtro de palabras clave.
