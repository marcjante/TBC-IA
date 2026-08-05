# TBC-AI

Chatbot local especializado en tuberculosis, basado en RAG (Retrieval-Augmented Generation), que responde exclusivamente con la documentación científica cargada por el usuario. Ejecución 100% local, sin APIs de pago, sin envío de datos a Internet.

## Estado del proyecto

- [x] Fase 1 — Detección de hardware
- [ ] Fase 2 — Instalación de Ollama
- [ ] Fase 3 — Instalación del modelo
- [ ] Fase 4 — Verificación
- [ ] Fase 5 — Estructura del proyecto
- [ ] Fase 6 — Backend (FastAPI)
- [ ] Fase 7 — Sistema RAG
- [ ] Fase 8 — Interfaz
- [ ] Fase 9 — Pruebas
- [ ] Fase 10 — Optimización

## Requisitos obligatorios

- Todo el procesamiento se ejecuta en local.
- Sin OpenAI, Claude API, Gemini ni ningún servicio de pago.
- No requiere tarjeta bancaria.
- Ningún documento sale del equipo.
- Debe funcionar sin conexión a Internet una vez instalado.
- Software 100% Open Source.

## Arquitectura

### RAG en lugar de fine-tuning o LoRA

El sistema usa RAG: los documentos se indexan en una base vectorial y el modelo recibe solo los fragmentos relevantes para cada pregunta, junto con la instrucción de responder exclusivamente a partir de ese contexto.

Fine-tuning y LoRA reentrenan los pesos del modelo con los datos aportados. Eso hace que el conocimiento quede integrado en el modelo sin trazabilidad de fuente, que actualizar la base de conocimiento implique reentrenar, y que con un volumen de documentos moderado (decenas de guías, no miles) el modelo tienda a sobreajustar o no aprender nada útil. RAG evita estos tres problemas: cada respuesta es trazable al fragmento recuperado, añadir o retirar un documento no toca el modelo, y funciona con corpus pequeños.

### Sin agentes ni MCP

El sistema no necesita decidir entre varias herramientas ni ejecutar acciones externas — solo recuperar fragmentos e generar una respuesta. Un framework de agentes añadiría complejidad sin beneficio en este caso.

### Memoria conversacional

Historial de turnos mantenido en la sesión activa. No se usa memoria vectorial persistente entre sesiones en esta fase.

### Embeddings y base vectorial (elección preliminar, se confirma en Fase 7)

- **Embeddings**: `nomic-embed-text` vía Ollama — mejor relación calidad/coste en local.
- **Base vectorial**: Chroma — más simple de mantener, suficiente para el volumen esperado (guías clínicas de TBC, no un corpus masivo). FAISS queda como alternativa si el volumen de documentos crece mucho.

## Comparativa de modelos

| Modelo | Calidad | Velocidad | RAM mínima | Licencia | Notas |
|---|---|---|---|---|---|
| Llama 3.1 8B | Alta | Media | 8–16 GB | Llama 3.1 (permisiva, con restricciones de uso a gran escala) | Buen equilibrio general, buen soporte en Ollama |
| Qwen2.5 7B/14B | Alta, fuerte en instrucciones y multilingüe | Media | 8–16 GB (7B) / 16–24 GB (14B) | Apache 2.0 | Buen seguimiento de instrucciones tipo "responde solo con el contexto" |
| Mistral 7B | Media-alta | Alta | 8 GB | Apache 2.0 | Rápido, algo menos preciso citando fuentes que Qwen |
| Gemma 2 9B | Media-alta | Media | 8–12 GB | Gemma (permisiva, con cláusulas de uso) | Sólido en QA extractivo |
| Phi-3.5 mini (3.8B) | Media | Muy alta | 4–8 GB | MIT | Mejor opción con RAM limitada |
| DeepSeek-R1 (destilados 7B/8B) | Alta en razonamiento | Media-baja (razona en pasos) | 8–16 GB | MIT | Útil para explicar discrepancias entre guías paso a paso, más lento y verboso |
| Mixtral 8x7B | Alta | Baja (MoE pesado) | 32+ GB | Apache 2.0 | Solo viable con mucha RAM/GPU |
| GPT-OSS (OpenAI, pesos abiertos) | Alta | Media | Variable (20B/120B) | Apache 2.0 | El 20B ya exige 16 GB+ |

Todos se ejecutan en local vía Ollama. El modelo definitivo se fija tras la Fase 1, según el hardware real detectado.

## Estructura del repositorio

```
tbc-ai/
│
├── backend/          # FastAPI: endpoints, lógica RAG, orquestación con Ollama
├── frontend/          # HTML/CSS/JS: interfaz tipo chat
├── documents/         # PDFs/DOCX cargados por el usuario (no versionar en git)
├── vector_db/          # Índice de Chroma/FAISS (no versionar en git)
├── models/             # Referencias/config de modelos Ollama
├── prompts/            # System prompts versionados
├── scripts/            # Scripts de utilidad (detección de hardware, indexación, etc.)
├── tests/              # Pruebas automáticas
├── config/             # Configuración de la app
├── README.md
├── requirements.txt
└── start.sh
```

## Fase 1 — Detección de hardware

Script: `scripts/detect_hardware.py`. Detecta sistema operativo, arquitectura, Apple Silicon/Intel, RAM, GPU, espacio libre en disco, versión de Python, Git y Ollama. Genera una recomendación de modelo según la RAM disponible y guarda un informe en `scripts/hardware_report.txt`.

No requiere dependencias externas (solo librería estándar de Python).

### Ejecución

```bash
cd scripts
python3 detect_hardware.py
```

En Windows: `python detect_hardware.py`.

### Verificación

La ejecución correcta imprime en consola el SO, RAM, GPU, disco libre y una recomendación de modelo, y crea `hardware_report.txt` en la misma carpeta.

### Errores frecuentes

- **Linux sin `lspci`**: la detección de GPU integrada puede fallar; no afecta al resto del informe.
- **macOS, primera ejecución lenta**: `system_profiler` puede tardar varios segundos.
- **Ollama/Git no instalados**: el script lo indica como aviso; no bloquea la ejecución, pero son requisitos para las fases siguientes.

## Privacidad

- Ningún documento ni consulta sale del equipo local.
- No introducir datos identificativos de pacientes en los documentos cargados ni en las conversaciones.
- El historial de conversación debe poder borrarse completamente desde la interfaz (funcionalidad prevista en Fase 8).

## Escalabilidad futura

La arquitectura RAG + FastAPI + Ollama permite migrar sin reescribir el proyecto a: contenedor Docker, servidor Linux, despliegue en la nube, dominio propio, autenticación de usuarios, API REST pública y aplicación móvil.

## Licencia

Por definir.
