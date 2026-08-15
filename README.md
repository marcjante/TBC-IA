# TBC-AI

Sistema local de inteligencia artificial sobre tuberculosis, compuesto por dos aplicaciones servidas desde un único backend FastAPI:

- **TBC-AI (guías clínicas)** — chat RAG para profesionales, responde citando fuente y página de las guías indexadas (OMS, CDC, ECDC).
- **Seguiment TBC · ITL (pacientes)** — chat de seguimiento para pacientes en tratamiento, con detección de urgencias por reglas y respuestas generales por IA en lenguaje sencillo, en castellano, catalán, árabe y urdu.

Todo el procesamiento ocurre en local vía [Ollama](https://ollama.com). Ningún documento ni conversación sale del ordenador donde corre el servidor.

## Qué hace

- Responde preguntas clínicas sobre tuberculosis citando la fuente y página exacta de los documentos indexados.
- Se niega explícitamente a responder cuando no encuentra información suficiente en los documentos, en vez de completar con conocimiento general del modelo.
- Detecta síntomas de urgencia en el chat de pacientes mediante reglas deterministas (no depende del LLM) y muestra un aviso de seguridad fijo, sin pasar por generación de texto.
- Responde en 4 idiomas (castellano, catalán, árabe estándar, urdu) en el chat de pacientes.
- Permite subir nuevos documentos PDF en caliente desde el chat de guías, indexándolos sin reiniciar el servidor.

## Qué NO hace

- No sustituye la valoración de un profesional sanitario — así lo indica explícitamente en cada respuesta del chat de pacientes.
- No tiene validación clínica formal: las respuestas se han evaluado con un banco de 560 preguntas mediante clasificación automática (si la respuesta contiene o no contenido, no si el contenido es clínicamente correcto). Ver [Estado de validación](#estado-de-validación).
- No verifica que la traducción a árabe/urdu sea lingüísticamente correcta — los mensajes fijos de seguridad en esos idiomas están pendientes de revisión por un hablante nativo.
- No tiene reranking de resultados de búsqueda: la recuperación es directa por distancia vectorial.
- No guarda historial de conversación entre sesiones del servidor (memoria solo dentro de la sesión activa del navegador).

## Arquitectura

```
Navegador (frontend_guides/ o frontend_patient/)
        │
        ▼
   FastAPI (backend/main.py)
        │
   ┌────┼──────────────┐
   ▼    ▼               ▼
 RAG   Triaje (JS,    Ollama
(Chroma  reglas,       (llama3.1:8b
+bge-m3) sin LLM)       + bge-m3)
```

Un único proceso Python sirve los dos frontends (archivos estáticos) y expone la API. El triaje de urgencias del chat de pacientes corre enteramente en JavaScript, por expresiones regulares sobre síntomas, y **nunca llega al LLM** cuando detecta una urgencia — es una capa de seguridad determinista, aislada de cualquier fallo de generación del modelo.

### RAG (Retrieval-Augmented Generation)

- **Documentos**: PDF, extraídos con PyMuPDF.
- **Fragmentación**: bloques de 2000 caracteres con solapamiento de 300, descartando fragmentos con menos de 40 caracteres alfanuméricos (ruido de tablas/paginación).
- **Embeddings**: `bge-m3` vía Ollama, con el prefijo `"Tuberculosis: "` antepuesto a cada pregunta antes de generar su vector de búsqueda.
- **Base vectorial**: ChromaDB persistente en `vector_db/` (no versionado en git, se reconstruye desde `documents/`).
- **Filtro de relevancia**: doble umbral de distancia según si la pregunta contiene una palabra clave relacionada con tuberculosis (umbral permisivo) o no (umbral estricto).
- **Sin reranking**: los fragmentos se usan en el orden que devuelve la búsqueda vectorial directa.

### Guardrails contra alucinaciones

- El prompt de sistema prohíbe explícitamente completar información ausente con conocimiento general del modelo.
- Una capa adicional en código detecta frases delatoras de que el modelo está "rellenando" (p. ej. "sin embargo, puedo ofrecerte...") y sustituye la respuesta completa por el mensaje fijo de "no encuentro esta información", descartando lo generado.
- **Limitación conocida**: durante las pruebas se detectó que aumentar el número de fragmentos recuperados (`top_k`) mejora la cobertura de respuestas pero incrementa el riesgo de que el modelo genere una respuesta plausible sin respaldo real en las fuentes citadas. El sistema usa deliberadamente un valor conservador (8 fragmentos) por este motivo.

## Requisitos

- Python 3.11+
- [Ollama](https://ollama.com) instalado y corriendo
- Modelos descargados en Ollama: `llama3.1:8b` (chat) y `bge-m3` (embeddings)
- 8-16 GB de RAM recomendados

## Instalación

```bash
git clone <url-del-repositorio>
cd tbc-ai
python3 -m venv venv
source venv/bin/activate          # En Windows: venv\Scripts\activate
pip install -r requirements.txt

ollama pull llama3.1:8b
ollama pull bge-m3
```

## Incorporación de documentos

Coloca los PDF que quieras indexar en `documents/<categoria>/`, por ejemplo:

```
documents/
├── 01_WHO/
├── 02_CDC/
└── 03_ECDC/
```

Luego indexa con:

```bash
python3 scripts/index_documents.py
```

También se pueden subir documentos individuales en caliente desde la interfaz de guías clínicas (botón de carga), que los indexa sin reiniciar el servidor.

## Ejecución

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Abre en el navegador:

- `http://127.0.0.1:8000/` — panel de entrada con acceso a ambas aplicaciones
- `http://127.0.0.1:8000/guides/` — chat de guías clínicas
- `http://127.0.0.1:8000/patient/` — chat y panel de pacientes

## Evaluación

Se ha procesado un banco de 560 preguntas de pacientes (200 en categorías clínicas + 360 en lenguaje coloquial) directamente contra el sistema real. Los resultados están en `FAQ_pacientes_tuberculosis.md` y `Banco_360_respuestas.md`. La clasificación "con respuesta / sin cobertura" es automática (si la respuesta generada coincide con el mensaje fijo de ausencia de información o no) — **no implica verificación clínica humana de que cada respuesta sea correcta**.

## Estructura del repositorio

```
tbc-ai/
├── backend/
│   └── main.py            # Backend unico: endpoints, RAG, guardrails, triaje-servidor
├── frontend_guides/        # Chat de guias clinicas (self-contained)
├── frontend_patient/        # Chat y panel de pacientes
├── documents/               # PDFs indexados (no versionado)
├── vector_db/                # Indice ChromaDB (no versionado, se regenera)
├── scripts/                  # Scripts de indexacion, generacion de FAQ, y utilidades
│   ├── index_documents.py    # Indexacion completa desde documents/
│   ├── generate_faq.py       # Genera respuestas para el banco de 200 preguntas
│   └── generate_faq_bank.py  # Genera respuestas para el banco de 360 preguntas
├── FAQ_pacientes_tuberculosis.md
├── Banco_360_respuestas.md
├── requirements.txt
└── README.md
```

## Privacidad

- Todo el procesamiento ocurre en el ordenador donde corre el servidor; no hay llamadas a APIs externas de pago ni de terceros.
- No introduzcas datos identificativos reales de pacientes en los documentos indexados ni en las conversaciones — la aplicación no está diseñada como historia clínica ni sistema de registro sanitario.
- El chat de pacientes guarda el historial de conversación en `localStorage` del navegador (local, no compartido), salvo que se configure Firebase manualmente para sincronización entre dispositivos (desactivado por defecto).

## Limitaciones conocidas

- Sin validación clínica formal (ver Estado de validación).
- Las traducciones a árabe y urdu no han sido revisadas por un hablante nativo.
- El modelo (`llama3.1:8b`) puede, en casos límite, generar respuestas plausibles pero sin respaldo real en el contexto recuperado; los guardrails reducen pero no eliminan este riesgo.
- No hay reranking de los resultados de búsqueda vectorial.
- El servidor no está pensado para exponerse fuera de `127.0.0.1` sin revisar antes la configuración de CORS (actualmente abierta a cualquier origen).

## Estado de validación

| Elemento | Estado |
|---|---|
| Funcionamiento técnico | Verificado (checklist automatizado) |
| Cobertura del banco de 560 preguntas | Medida automáticamente (~61% con respuesta) |
| Corrección clínica de las respuestas | **No verificada por un profesional sanitario** |
| Traducciones a árabe/urdu | **No revisadas por hablante nativo** |
| Idoneidad para uso clínico real | No evaluada — este es un prototipo de investigación |

## Licencia

Por definir.
