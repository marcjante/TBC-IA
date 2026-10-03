El subagente security-reviewer ha hecho la revisión en modo solo lectura y no ha cambiado ningún archivo. He vuelto a comprobar las líneas de los hallazgos principales (clave por defecto, CORS, upload y n8n) y coinciden con el código.

**Lo que no se pudo comprobar:**
- No se ejecutaron `pip-audit` ni `npm audit`, así que los CVE de dependencias están sin confirmar.
- Los permisos bloquearon `git log -p`, así que no se recorrió el historial buscando secretos.
- Sí se confirmó que ningún `.env` real se ha versionado nunca.

## 🔴 Crítico

**1. `/api/upload` acepta escritura de PDFs en cualquier ruta, sin autenticación** (`backend/main.py:732-755`, con CORS `*` en `backend/main.py:40`)
- **Problema:** `category` y `file.filename` se meten en `os.path.join` sin limpiar (`backend/main.py:737`, `:740`). Solo se comprueba que el nombre acabe en `.pdf`, y no hay límite de tamaño. Después el PDF se indexa en ChromaDB.
- **Cómo se explotaría:** basta con que tengas abierta en el Mac cualquier web maliciosa. Esa web puede enviar un `fetch` con `FormData` a `127.0.0.1:8001/api/upload`, y el navegador lo deja pasar sin preflight porque es una "simple request". Con `category=../../..` puede escribir PDFs en cualquier carpeta en la que tengas permisos o sobrescribir guías clínicas. Lo peor es que puede **meter en la base vectorial dosis o pautas falsas, y el chat clínico las citaría como fuente**.
- **Arreglo:**
  - Comprobar `category` con la regex `^[A-Za-z0-9_\-]{1,64}$`.
  - Pasar el nombre por `os.path.basename`, validarlo con regex y exigir la firma `%PDF-` al inicio.
  - Comprobar con `realpath` y un prefijo que el destino queda dentro de la carpeta de documentos. `/api/document/...` en `backend/main.py:787-799` ya lo hace bien.
  - Limitar el tamaño (unos 25 MB) y pedir una clave de API para subir.

## 🟠 Alto

**1. Clave por defecto `tbc_ia_secret_v7` escrita en el código** (`tbc-ia-sota-engine/app/main.py:59`, `backend/config.py:36`)
- **Problema:** si la variable de entorno no está definida, el servicio queda "protegido" con una clave que ya es pública porque está en git. Además, cada servicio la busca con un nombre distinto (`TBC_API_KEY` frente a `SOTA_ENGINE_API_KEY`), y la comparación con `!=` no es de tiempo constante (`tbc-ia-sota-engine/app/main.py:406-407`).
- **Cómo se explotaría:** con esa clave se puede exportar el corpus por `/v1/admin/export/ris` y cargar la CPU con el NLI.
- **Arreglo:**
  - Leerla con `os.environ["TBC_API_KEY"]` para que el servicio no arranque si falta.
  - Usar el mismo nombre de variable en los dos servicios y comparar con `secrets.compare_digest`.
  - **Rotarla:** generar una nueva con `openssl rand -hex 32`.

**2. El backend 8001 no tiene autenticación y su CORS es `*`** (`backend/main.py:38-43`)
- **Problema:** cualquier web puede leer las respuestas del chat clínico y usar tu LLM local.
- **Cómo se explotaría:** con DNS rebinding, el ataque llega a los servicios aunque no tengan CORS, porque no se valida la cabecera `Host`.
- **Arreglo:**
  - Restringir `allow_origins` a `127.0.0.1:8001` y `localhost:8001`.
  - Añadir `TrustedHostMiddleware` con `["127.0.0.1", "localhost"]`.
  - Pedir clave en las rutas que escriben.

**3. CORS `*` con `allow_credentials=True` en el motor SOTA** (`tbc-ia-sota-engine/app/main.py:404`)
- **Arreglo:** quitar `allow_credentials` y restringir el origen. El backend llama al motor de servidor a servidor, así que no necesita CORS.

**4. n8n arranca con todos los nodos habilitados** (`arrancar TBC/start_tbc_stack.sh:110`)
- **Problema:** `NODES_EXCLUDE="[]"` activa "Execute Command". El script no fija ninguna dirección de escucha, y n8n puede escuchar en todas las interfaces según la versión (hay que confirmarlo).
- **Cómo se explotaría:** alguien en la misma Wi-Fi del hospital o la universidad podría llegar a ejecutar comandos en el Mac.
- **Arreglo:**
  - Arrancar con `N8N_HOST=127.0.0.1 N8N_LISTEN_ADDRESS=127.0.0.1`.
  - Excluir `executeCommand` si el backup puede hacerse con otro nodo.
  - Comprobar con `lsof -iTCP -sTCP:LISTEN -nP` que nada escucha en `*`.

## 🟡 Medio

1. **Fugas en errores y logs.**
   - Se devuelve `str(e)` al cliente en `backend/main.py:301` y `:747`.
   - Se imprimen el contexto y la salida cruda del verificador en `backend/main.py:165-174` y `:267-271`.
   - Las preguntas de los profesionales se guardan en claro en `usage_patterns.jsonl` (`backend/main.py:366`, `:522`). Pueden incluir datos de pacientes escritos sin querer.
   - Los logs van a `~/tbc_stack_logs` sin rotación ni permisos restringidos.
   - **Arreglo:** devolver un error genérico, quitar los `print` de depuración y aplicar `chmod 700` a la carpeta de logs.
2. **No hay límites en la entrada.** `message`, `history` y `top_k` no tienen tope (`backend/main.py:275-291`), y tampoco `sources` en `tbc-ia-sota-engine/app/main.py:525-528`. El verificador hace un NLI por cada par frase × fuente, así que una web puede provocar una denegación de servicio local.
   - **Arreglo:** usar `Field(max_length=…, le=…)`, `Query(max_length=300)` y limitar peticiones con `slowapi`.
3. **XSS por `innerHTML` con datos de PubMed y CIMA** (`backend/main.py:1284-1306`, `:1384-1389`). El campo `r.doi` va dentro de un `href` sin escapar. Es poco probable en la práctica.
   - **Arreglo:** escapar con la `escapeHtml` que ya existe en `frontend_guides/index.html:273` y validar el DOI con regex.
4. **XSS almacenado en el frontend de pacientes** (`frontend_patient/script.js:847`). `patients[id].name` y `patients[id].type` se insertan sin escapar. Ahora mismo solo afectaría a quien lo escribe, pero sería real si se activa Firestore.
   - Antes de activar Firestore hay que poner reglas con autenticación y revisar RGPD y consentimiento.
5. **Dependencias.**
   - `fastapi==0.115.0` y `python-multipart==0.0.12` pueden estar afectadas por fallos de DoS en el parseo multipart (CVE-2024-53981, CVE-2024-47874). Hay que confirmarlo con `pip-audit`.
   - El motor SOTA declara sus dependencias con `>=` sin tope, y algunos paquetes del backend no tienen versión fijada.
   - El entorno usa Python 3.9, que ya no recibe parches.
6. **Exposición de red: hoy está bien, pero depende de valores por defecto.** No hay ningún `0.0.0.0` en el código propio. Pero el script lanza el backend y Llamafile sin `--host` explícito (`start_tbc_stack.sh:75`, `:93`).
   - **Arreglo:** añadir `--host 127.0.0.1` de forma explícita.

## 🟢 Bajo

1. Ningún servicio tiene `TrustedHost` ni cabeceras de seguridad. `bibliography_api.py:35` también usa CORS `*`, aunque sus datos son públicos y de solo lectura.
2. `/docs` y `/openapi.json` están expuestos en todos los servicios.
3. `limit` no tiene tope en `bibliography_api.py:47`. La consulta FTS5 sí está parametrizada, así que no hay inyección SQL.
4. El XML de PubMed se parsea con `xml.etree` (`backend/rag.py:396`). `defusedxml` cerraría el riesgo.
5. Hay copias obsoletas de `dashboard_service.py` (en la raíz y un `.bak`).
6. `GET /api/translate` mete el texto del usuario en el prompt. El riesgo de inyección de prompt es bajo porque la salida solo se muestra al usuario. Conviene pasarlo a POST y limitar la longitud.

**Descartado tras revisarlo:**
- No hay SSRF: todas las URLs salientes son fijas.
- No hay inyección SQL ni de comandos: no aparecen `subprocess`, `eval` ni `pickle`.
- La descarga de documentos valida bien la ruta.
- `firebase-config.js` tiene el `apiKey` vacío.

## Acciones prioritarias

1. Asegurar `/api/upload`: limpiar `category` y nombre, limitar tamaño, exigir la firma `%PDF-` y pedir clave.
2. Quitar del código y rotar `tbc_ia_secret_v7`, unificar el nombre de la variable y comparar con `compare_digest`.
3. Restringir CORS y añadir `TrustedHostMiddleware` en los puertos 8001, 8002 y 8003.
4. Hacer que n8n escuche solo en 127.0.0.1, quitar Execute Command y comprobar con `lsof`.
5. Pasar `pip-audit`, actualizar FastAPI, `python-multipart` y Python, y añadir límites de longitud y de peticiones.

Si quieres, empiezo por el punto 1 y el 2.
