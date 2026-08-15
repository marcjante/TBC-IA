import re
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import ollama
import chromadb
import os
import hashlib
import shutil
import fitz
from dotenv import load_dotenv

load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

app = FastAPI(title="TBC-AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAT_MODEL = os.environ.get("TBC_CHAT_MODEL", "llama3.1:8b")
EMBED_MODEL = os.environ.get("TBC_EMBED_MODEL", "bge-m3")
COLLECTION_NAME = "tbc_docs"
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "vector_db")
DOCUMENTS_DIR = os.path.join(PROJECT_ROOT, "documents")
GUIDES_DIR = os.path.join(PROJECT_ROOT, "frontend_guides")
PATIENT_DIR = os.path.join(PROJECT_ROOT, "frontend_patient")

chroma_client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

TB_KEYWORDS = [
    "tubercul", "tbc", "tb ", "bacilo", "mycobacterium", "koch",
    "contagi", "contagio", "transmit", "transmis",
    "tos", "esput", "sangre al toser", "hemoptisis",
    "fiebre", "sudor", "sudo", "peso", "cansancio", "fatiga",
    "pulmon", "pulmonar", "respirat", "torax", "torácico",
    "diagnost", "baciloscopia", "cultivo", "genexpert", "pcr",
    "radiografia", "tac ", "mantoux", "tuberculina", "igra", "ppd",
    "latente", "itl", "infeccion tuberculosa",
    "tratamiento", "medicamento", "pastilla", "dosis", "farmaco",
    "isoniazida", "rifampicina", "pirazinamida", "etambutol",
    "rifapentina", "bedaquilina", "linezolid", "pretomanid",
    "efecto secundario", "efectos adversos", "higado", "hepat",
    "vista", "ojo", "orina", "sarpullido", "erupcion",
    "alcohol", "dieta", "alimentacion", "vitamina", "b6",
    "paracetamol", "ibuprofeno", "antibiotico", "anticoncept",
    "anticoagulant", "vih", "antidepresiv",
    "embaraz", "lactancia", "bebe", "pecho",
    "trabajo", "baja laboral", "colegio", "escuela", "nino",
    "viaj", "avion",
    "seguimiento", "analisis", "control",
    "resistente", "mdr", "xdr",
    "diabetes", "corticoide", "biologico", "inmunodeprimid",
    "vacuna", "bcg",
    "contacto", "familia", "familiar", "mascarilla",
    "ejercicio", "conducir", "relaciones sexuales", "dormir",
    "cocinar", "cuidar", "ventana",
    "curacion", "secuela", "recaida", "reinfect",
    "aislamiento", "aislar",
    "baar", "sensible", "resistencia",
    "alergi", "reaccion alergica",
    "miedo",
    "ansiedad",
    "estigma",
    "verguenza",
    "agobio",
    "agobiad",
    "psicolog",
    "apoyo emocional",
    "grupo de apoyo",
    "ansios",
    "abrazo",
    "abrazar",
    "beso",
    "besar",
    "dar la mano",
    "aire acondicionado",
    "mascota",
    "perro",
    "gato",
    "animal",
    "gimnasio",
    "deporte",
    "fumar",
    "tabaco",
    "cigarrillo",
    "vapear",
    "vapeo",
    "sexo",
    "pareja",
    "empresa",
    "jefe",
    "recursos humanos",
    "compañero",
    "compañeros",
    "guarderia",
    "pasaporte",
    "informe medico",
    "aeropuerto",
    "recien nacido",
    "nieto",
    "nieta",
    "abuela",
    "abuelo",
    "hijo",
    "hijos",
    "triturar",
    "conservar",
    "nevera",
    "caduca",
    "caducidad",
    "recaer",
    "curado",
    "grave",
    "gravedad",
    "morir",
    "muerte",
    "dolor",
    "vomit",
    "nausea",
    "pica",
    "borros",
    "visita",
    "analitica",
    "termin",
    "resultado",
    "mayor",
    "defensas",
    "interaccion",
    "cura",
    "curar",
    "parto",
    "aisla",
    "apoyo",
    "despid",
    "confidencial",
    "rechaz",
    "pronostico",
    "ropa",
    "bano",
    "compartir",
    "visitar",
    "riesgo",
    "urgencia",
    "amarill",
    "sangre",
    "especialista",
    "revision",
    "alta",
    "horario",
    "estomago",
    "ayunas",
    "manchas",
    "lagrimas",
    "desinfectar",
    "lejia",
    "veterinario",
    "cafe",
    "suplemento",
    "proteccion",
    "muestra",
    "azucar",
    "muscular",
    "analgesic",
    "ginecolog",
    "neumolog",
]

# Patrones que indican que el modelo esta "rellenando" con conocimiento
# general en vez de limitarse al contexto recuperado (fuga de conocimiento).
# Union de los patrones detectados historicamente en ambos endpoints de chat;
# compartida para que un patron nuevo anadido aqui proteja a los dos a la vez.
LEAK_PATTERNS = [
    "no contiene informacion especifica",
    "sin embargo, puedo ofrecerte",
    "puedo ofrecerte informacion general",
    "puedo ofrecerte",
    "puedo darte informacion general",
    "informacion general sobre",
    "de manera general,",
    "por lo general,",
    "segun mi conocimiento",
    "el texto proporcionado no",
    "el contexto no contiene",
    "no se menciona explicitamente",
]


def normalize_accents(text):
    t = text.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u")]:
        t = t.replace(a, b)
    return t


def detect_generic_knowledge_leak(response_text):
    normalized = normalize_accents(response_text)
    return any(normalize_accents(pat) in normalized for pat in LEAK_PATTERNS)


def is_tb_related(text):
    normalized = text.lower()
    normalized = normalized.replace("?", " ").replace("!", " ").replace(".", " ").replace(",", " ")
    normalized = " " + normalized + " "
    return any((" " + kw if not kw.endswith(" ") else kw) in normalized for kw in TB_KEYWORDS) or any(kw.strip() in normalized for kw in TB_KEYWORDS)


SYSTEM_PROMPT = """Eres un asistente clinico especializado en tuberculosis (TBC).

REGLAS OBLIGATORIAS:
0. Responde SIEMPRE en español, incluso si los documentos fuente estan en ingles u otro idioma. Traduce terminologia tecnica al espanol cuando exista un termino equivalente reconocido.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo. Tienes PROHIBIDO usar tu conocimiento general o entrenamiento previo para completar, ampliar o sustituir informacion que falte en el contexto, incluso si tu conocimiento general es correcto. Esto aplica siempre, sin excepcion, incluso cuando el contexto sea parcial, ambiguo o este relacionado solo indirectamente con la pregunta.
2. Si el contexto no contiene informacion suficiente para responder, tu respuesta COMPLETA debe ser, palabra por palabra y sin nada mas antes ni despues: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, cifras, ni recomendaciones que no esten en el contexto. Si detectas que el contexto no cubre la pregunta, NUNCA ofrezcas "informacion general" como alternativa: usa directamente la frase fija de la regla 2.
4. Cita siempre la fuente y pagina de cada afirmacion, usando el formato: (Fuente: {source}, p.{page}). No cites una fuente para respaldar una afirmacion que esa fuente no contiene realmente.
5. Si distintas fuentes del contexto se contradicen entre si, indicalo explicitamente y explica la discrepancia en vez de elegir una sin mas.
6. Separa claramente los datos/evidencia de tu interpretacion cuando la haya.
7. La frase "No encuentro esta informacion en los documentos disponibles." es una respuesta binaria: o es tu ÚNICA respuesta completa, o no aparece en absoluto. Nunca la combines con explicaciones, disculpas, conocimiento general, ni frases como "sin embargo puedo ofrecerte..." Si dudas entre responder con el contexto o rellenar con lo que sabes, elige SIEMPRE la frase fija.
"""


class ChatRequest(BaseModel):
    message: str
    top_k: int = 8
    debug: bool = False


MIN_ALNUM_CHARS = 40


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            alnum_count = sum(1 for c in chunk if c.isalnum())
            if alnum_count >= MIN_ALNUM_CHARS:
                chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def chunk_id(source_file, page_num, chunk_index):
    raw = f"{source_file}|{page_num}|{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def index_single_pdf(pdf_path, category, fname):
    doc = fitz.open(pdf_path)
    total_chunks = 0

    for i, page in enumerate(doc):
        page_num = i + 1
        text = page.get_text().strip()
        if not text:
            continue

        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            cid = chunk_id(f"{category}/{fname}", page_num, idx)
            embedding = ollama.embeddings(model=EMBED_MODEL, prompt=chunk)["embedding"]

            collection.upsert(
                ids=[cid],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": fname,
                    "category": category,
                    "page": page_num,
                }],
            )
            total_chunks += 1

    doc.close()
    return total_chunks


@app.get("/api/health")
def health():
    try:
        ollama.list()
        doc_count = collection.count()
        return {"status": "ok", "model": CHAT_MODEL, "documentos_indexados": doc_count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/chat")
def chat(request: ChatRequest):
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + request.message)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    has_keyword = is_tb_related(request.message)

    if not fragments or not distances:
        return {
            "response": "No encuentro esta informacion en los documentos disponibles.",
            "sources": [],
        }

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {
                "response": "No encuentro esta informacion en los documentos disponibles.",
                "sources": [],
            }

    context_parts = []
    sources_used = []
    for frag, meta in zip(fragments, metadatas):
        context_parts.append(
            "[Fuente: " + meta["source"] + ", categoria: " + meta["category"] + ", pagina: " + str(meta["page"]) + "]\n" + frag
        )
        sources_used.append({
            "source": meta["source"],
            "category": meta["category"],
            "page": meta["page"],
        })

    context_text = "\n\n---\n\n".join(context_parts)
    user_prompt = "CONTEXTO:\n" + context_text + "\n\nPREGUNTA DEL USUARIO:\n" + request.message

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0.1,
            "top_p": 0.9,
        },
    )

    final_response = response["message"]["content"]
    no_info_phrase = "No encuentro esta informaci"
    CANNED_NO_INFO = "No encuentro esta informacion en los documentos disponibles."

    leaked = detect_generic_knowledge_leak(final_response)

    # Se busca la frase fija en cualquier parte de la respuesta, no solo al
    # principio: el modelo a veces la antepone con texto propio (ej. "La
    # respuesta es: No encuentro..."), lo que antes hacia que no se vaciaran
    # las fuentes aunque el propio modelo diga que no sabe la respuesta.
    if no_info_phrase in final_response:
        final_response = CANNED_NO_INFO
        sources_used = []
    elif leaked:
        final_response = CANNED_NO_INFO
        sources_used = []

    result = {
        "response": final_response,
        "sources": sources_used,
    }
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": request.top_k,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
            "fragments_retrieved": len(fragments),
        }
    return result


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), category: str = Form("sin_categoria")):
    if not file.filename.lower().endswith(".pdf"):
        return {"status": "error", "detail": "Solo se aceptan archivos PDF por ahora."}

    category_dir = os.path.join(DOCUMENTS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    dest_path = os.path.join(category_dir, file.filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks_created = index_single_pdf(dest_path, category, file.filename)
    except Exception as e:
        return {"status": "error", "detail": f"Archivo guardado pero fallo la indexacion: {str(e)}"}

    return {
        "status": "ok",
        "filename": file.filename,
        "category": category,
        "chunks_indexed": chunks_created,
        "total_documentos_indexados": collection.count(),
    }


PATIENT_SYSTEM_PROMPT = """Eres un asistente que ayuda a pacientes en tratamiento de tuberculosis a entender su enfermedad.
Hablas con el propio paciente, no con un profesional sanitario.

REGLAS OBLIGATORIAS:
0. Responde en el idioma indicado (variable de idioma), con frases cortas y palabras sencillas, como hablarias con alguien sin conocimientos medicos. Evita jerga clinica; si usas un termino tecnico, explicalo en la misma frase con palabras normales.
1. Responde EXCLUSIVAMENTE usando la informacion contenida en el CONTEXTO proporcionado abajo. Tienes PROHIBIDO usar conocimiento general o entrenamiento previo para completar lo que falte en el contexto, incluso si ese conocimiento es correcto.
2. Si el contexto no contiene informacion suficiente para responder, tu respuesta COMPLETA debe ser, sin nada mas antes ni despues: "No encuentro esta informacion en los documentos disponibles."
3. No inventes datos, dosis, ni recomendaciones que no esten en el contexto. Nunca ofrezcas informacion general como alternativa: usa la frase fija de la regla 2.
4. No des consejos que sustituyan a un profesional sanitario. Si la pregunta suena a sintoma, urgencia o duda sobre su propia medicacion, recuerda amablemente que consulte a su equipo de TBC ademas de responder lo que digan los documentos.
5. Tono calido y cercano, nunca alarmista. No repitas la pregunta del paciente.
6. No cites nombres de archivos PDF ni paginas al paciente: eso es para profesionales. Si necesitas referenciar el origen, di simplemente "segun las guias clinicas".
"""


class PatientChatRequest(BaseModel):
    message: str
    lang: str = "es"
    debug: bool = False


@app.post("/api/patient-chat")
def patient_chat(request: PatientChatRequest):
    # Nombres de idioma y mensaje fijo de "sin informacion" en cada idioma,
    # definidos al principio de la funcion para poder usarlos en cualquier
    # punto (incluidos los retornos tempranos del filtro de relevancia).
    LANG_NAMES = {
        "ca": "catalan",
        "es": "castellano",
        "ar": "arabe (fusha / arabe estandar, para que lo entienda tambien un hablante de darija marroqui)",
        "ur": "urdu",
    }
    lang_name = LANG_NAMES.get(request.lang, "castellano")

    CANNED_NO_INFO_BY_LANG = {
        "es": "No encuentro esta informacion en los documentos disponibles.",
        "ca": "No trobo aquesta informacio en els documents disponibles.",
        "ar": "\u0644\u0627 \u0623\u062c\u062f \u0647\u0630\u0647 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0629 \u0641\u064a \u0627\u0644\u0648\u062b\u0627\u0626\u0642 \u0627\u0644\u0645\u062a\u0627\u062d\u0629.",
        "ur": "\u0645\u062c\u06be\u06d2 \u062f\u0633\u062a\u06cc\u0627\u0628 \u062f\u0633\u062a\u0627\u0648\u06cc\u0632\u0627\u062a \u0645\u06cc\u06ba \u06cc\u06c1 \u0645\u0639\u0644\u0648\u0645\u0627\u062a \u0646\u06c1\u06cc\u06ba \u0645\u0644\u06cc\u06ba\u06d4",
    }
    canned_no_info = CANNED_NO_INFO_BY_LANG.get(request.lang, CANNED_NO_INFO_BY_LANG["es"])

    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt="Tuberculosis: " + request.message)["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=8,
    )

    fragments = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    STRICT_DISTANCE_THRESHOLD = 480
    LOOSE_DISTANCE_THRESHOLD = 750

    # La lista TB_KEYWORDS solo cubre espanol: en arabe/urdu nunca habria
    # coincidencia, lo que forzaria siempre el umbral estricto (480) aunque
    # la pregunta sea legitima. Como esta app esta dedicada integramente a
    # tuberculosis, tratamos estos dos idiomas como "dentro de dominio" por
    # defecto y usamos el umbral permisivo (750).
    has_keyword = is_tb_related(request.message) or request.lang in ("ar", "ur")

    if not fragments or not distances:
        return {"response": canned_no_info}

    if has_keyword:
        if distances[0] > LOOSE_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}
    else:
        if distances[0] > STRICT_DISTANCE_THRESHOLD:
            return {"response": canned_no_info}

    context_parts = [frag for frag in fragments]
    context_text = "\n\n---\n\n".join(context_parts)

    user_prompt = f"IDIOMA DE RESPUESTA: {lang_name}\n\nCONTEXTO:\n{context_text}\n\nPREGUNTA DEL PACIENTE:\n{request.message}"

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": PATIENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.1, "top_p": 0.9},
    )

    final_response = response["message"]["content"]
    normalized_check = final_response.lower()
    for a, b in [("\u00e1", "a"), ("\u00e9", "e"), ("\u00ed", "i"), ("\u00f3", "o"), ("\u00fa", "u")]:
        normalized_check = normalized_check.replace(a, b)

    CANNED_NO_INFO_PATIENT = "No encuentro esta informacion en los documentos disponibles."

    # Si el modelo expresa "no lo se" con sus propias palabras (con o sin
    # rodeos tipo "lo siento"), lo normalizamos a la frase fija, en vez de
    # dejar pasar variantes que no coinciden exactamente y contaminan las
    # estadisticas de "con respuesta / sin cobertura".
    no_info_variants = [
        "no encuentro esta informacion", "no encuentro informacion",
        "no tengo esta informacion", "no tengo informacion",
        "no dispongo de esta informacion", "no dispongo de informacion",
        "no cuento con esta informacion", "no cuento con informacion",
    ]
    said_no_info = any(v in normalized_check for v in no_info_variants)

    leaked = detect_generic_knowledge_leak(final_response)

    if said_no_info or leaked:
        final_response = CANNED_NO_INFO_PATIENT

    # Elimina menciones a nombres de archivo, URLs o citas de fuente que el
    # modelo pueda colar pese a la instruccion del prompt de no mencionarlas
    # al paciente (regla 6 del PATIENT_SYSTEM_PROMPT).
    final_response = re.sub(r"\(Fuente:.*?\)", "", final_response, flags=re.IGNORECASE | re.DOTALL)
    final_response = re.sub(r"https?://\S+", "", final_response)
    final_response = re.sub(r"\S+\.pdf", "", final_response, flags=re.IGNORECASE)
    final_response = re.sub(r"\s{2,}", " ", final_response).strip()

    result = {"response": final_response}
    if request.debug:
        result["debug_info"] = {
            "model": CHAT_MODEL,
            "top_k": 8,
            "top1_distance": distances[0] if distances else None,
            "has_keyword": has_keyword,
        }
    return result


@app.get("/", response_class=HTMLResponse)
def home():
    html = """
<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TBC · Panell local</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%231F4B4C'/%3E%3Cpath d='M10,50 L35,50 L42,30 L50,70 L58,50 L90,50' stroke='%233E8E89' stroke-width='7' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --paper: #F5F1E8;
    --ink: #1C2420;
    --ink-soft: #5B6560;
    --teal: #1F4B4C;
    --teal-bright: #3E8E89;
    --rust: #A8502E;
    --line: #DEDACB;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 64px 24px 40px;
  }
  .eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--teal-bright);
    margin-bottom: 14px;
  }
  h1 {
    font-family: 'Fraunces', serif;
    font-optical-sizing: auto;
    font-weight: 600;
    font-size: clamp(36px, 6vw, 56px);
    margin: 0;
    color: var(--ink);
    text-align: center;
  }
  .sub {
    color: var(--ink-soft);
    font-size: 15px;
    max-width: 440px;
    text-align: center;
    margin: 14px 0 0;
    line-height: 1.5;
  }
  .wave {
    width: 100%;
    max-width: 560px;
    height: 40px;
    margin: 40px 0 44px;
  }
  .wave path {
    fill: none;
    stroke: var(--teal-bright);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-dasharray: 600;
    stroke-dashoffset: 600;
    animation: draw 3.2s ease-in-out infinite alternate;
    opacity: 0.55;
  }
  @keyframes draw {
    to { stroke-dashoffset: 0; }
  }
  .cards {
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 880px;
    width: 100%;
  }
  .card {
    flex: 1 1 320px;
    max-width: 380px;
    background: #FFFEFA;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 30px 28px 26px;
    text-decoration: none;
    color: inherit;
    position: relative;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  }
  .card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(28,36,32,0.09);
    border-color: var(--teal-bright);
  }
  .tag {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    padding: 4px 10px;
    border-radius: 3px;
    margin-bottom: 16px;
  }
  .tag.patient { background: rgba(31,75,76,0.1); color: var(--teal); }
  .tag.clinic { background: rgba(168,80,46,0.1); color: var(--rust); }
  .card h2 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 23px;
    margin: 0 0 10px;
  }
  .card p {
    font-size: 13.5px;
    color: var(--ink-soft);
    line-height: 1.55;
    margin: 0 0 20px;
  }
  .status {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--ink-soft);
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--teal-bright);
    flex-shrink: 0;
  }
  footer {
    margin-top: 56px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--ink-soft);
    text-align: center;
    letter-spacing: 0.02em;
  }
  @media (max-width: 480px) {
    body { padding: 44px 18px 32px; }
  }
</style>
</head>
<body>
  <div class="eyebrow">Panell local · Tuberculosi</div>
  <h1>Consulta &amp; guies</h1>
  <p class="sub">Dues eines, un sol servidor. Tot funciona al teu ordinador, sense connexio a internet ni dades que en surtin.</p>

  <svg class="wave" viewBox="0 0 560 40" xmlns="http://www.w3.org/2000/svg">
    <path d="M0,20 L120,20 L136,6 L152,34 L168,20 L200,20 L216,12 L232,28 L248,20 L560,20" />
  </svg>

  <div class="cards">
    <a class="card" href="/patient/">
      <span class="tag patient">Pacients</span>
      <h2>Seguiment TBC · ITL</h2>
      <p>Xat de triatge amb pacients en tractament, historial de missatges i panell professional de seguiment.</p>
      <div class="status"><span class="dot"></span>Firestore · en linia</div>
    </a>
    <a class="card" href="/guides/">
      <span class="tag clinic">Clinic</span>
      <h2>TBC-AI</h2>
      <p>Assistent sobre guies cliniques de l'OMS, CDC i ECDC, amb cita de font i pagina en cada resposta.</p>
      <div class="status"><span class="dot"></span>Ollama · {CHAT_MODEL_PLACEHOLDER}</div>
    </a>
  </div>

  <footer>servidor local actiu — cap document ni conversa surt d'aquest ordinador</footer>
</body>
</html>
"""
    return html.replace("{CHAT_MODEL_PLACEHOLDER}", CHAT_MODEL)


app.mount("/guides", StaticFiles(directory=GUIDES_DIR, html=True), name="guides")
app.mount("/patient", StaticFiles(directory=PATIENT_DIR, html=True), name="patient")
