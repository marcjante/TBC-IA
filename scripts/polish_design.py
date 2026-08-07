import re

# ============ 1. FAVICON coherente en las tres paginas ============
# Un favicon SVG inline con la linea de pulso, sin necesidad de archivo .ico
FAVICON_SVG = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='20' fill='%231F4B4C'/%3E"
    "%3Cpath d='M10,50 L35,50 L42,30 L50,70 L58,50 L90,50' "
    "stroke='%233E8E89' stroke-width='7' fill='none' stroke-linecap='round'/%3E"
    "%3C/svg%3E"
)
favicon_tag = f'<link rel="icon" href="{FAVICON_SVG}">\n'

# --- Aplicar a frontend_guides/index.html ---
with open("frontend_guides/index.html", encoding="utf-8") as f:
    guides = f.read()

if 'rel="icon"' not in guides:
    guides = guides.replace(
        '<title>TBC-AI</title>',
        '<title>TBC-AI</title>\n' + favicon_tag.rstrip()
    )

# ============ 2. Enlace "Tornar al panell" en frontend_guides ============
old_header = """<header>
  <div>
    <h1>TBC-AI</h1>
    <div class="status" id="status">Conectando...</div>
  </div>
  <div class="header-actions">
    <button class="icon-btn" onclick="exportChat()">Exportar</button>
    <button class="icon-btn" onclick="clearChat()">Limpiar chat</button>
  </div>
</header>"""

new_header = """<header>
  <div>
    <a href="/" class="back-link">&larr; Tornar al panell</a>
    <h1>TBC-AI</h1>
    <div class="status" id="status">Conectando...</div>
  </div>
  <div class="header-actions">
    <button class="icon-btn" onclick="exportChat()">Exportar</button>
    <button class="icon-btn" onclick="clearChat()">Limpiar chat</button>
  </div>
</header>"""

assert old_header in guides, "No se encontro el header exacto en frontend_guides"
guides = guides.replace(old_header, new_header)

# CSS para el enlace de vuelta + mejoras de foco/scroll
extra_css = """
  .back-link {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--text-dim);
    text-decoration: none;
    margin-bottom: 6px;
    transition: color 0.15s ease;
  }
  .back-link:hover { color: var(--accent); }

  /* Foco de teclado visible */
  button:focus-visible, a:focus-visible, textarea:focus-visible, input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* Scrollbar mas discreto */
  #chat::-webkit-scrollbar { width: 8px; }
  #chat::-webkit-scrollbar-track { background: transparent; }
  #chat::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
  #chat::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
"""
guides = guides.replace("</style>", extra_css + "</style>")

with open("frontend_guides/index.html", "w", encoding="utf-8") as f:
    f.write(guides)

print("frontend_guides/index.html: favicon + back-link + foco/scroll aplicados")

# ============ 3. frontend_patient: favicon + enlace de vuelta ============
with open("frontend_patient/index.html", encoding="utf-8") as f:
    patient = f.read()

# Favicon (buscamos el <head> generico, insertamos tras el primer <meta charset)
if 'rel="icon"' not in patient:
    patient = re.sub(
        r'(<meta charset="UTF-8">)',
        r'\1\n' + favicon_tag.rstrip(),
        patient,
        count=1,
    )

old_patient_header = """  <header class="top">
    <div class="top-head">
      <h1>Seguiment TBC · ITL</h1>
      <span class="badge" id="modeBadge">···</span>
    </div>
    <p>Consulta d'infermeria — triatge de missatges i programació de visites</p>
  </header>"""

new_patient_header = """  <header class="top">
    <a href="/" class="back-link">&larr; Tornar al panell</a>
    <div class="top-head">
      <h1>Seguiment TBC · ITL</h1>
      <span class="badge" id="modeBadge">···</span>
    </div>
    <p>Consulta d'infermeria — triatge de missatges i programació de visites</p>
  </header>"""

assert old_patient_header in patient, "No se encontro el header exacto en frontend_patient"
patient = patient.replace(old_patient_header, new_patient_header)

# Insertamos CSS del back-link antes del cierre </style> (si existe estilo inline)
# Si el CSS esta en style.css externo, lo añadimos ahi en su lugar (ver mas abajo)
with open("frontend_patient/index.html", "w", encoding="utf-8") as f:
    f.write(patient)

print("frontend_patient/index.html: favicon + back-link insertados")

# ============ CSS del back-link + foco/scroll en style.css externo ============
with open("frontend_patient/style.css", encoding="utf-8") as f:
    style = f.read()

extra_patient_css = """

/* --- Mejoras de integracion con el panell local --- */
.back-link {
  display: inline-block;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: #5B6560;
  text-decoration: none;
  margin-bottom: 8px;
  transition: color 0.15s ease;
}
.back-link:hover { color: #1F4B4C; }

button:focus-visible, a:focus-visible, textarea:focus-visible, input:focus-visible, select:focus-visible {
  outline: 2px solid #1F4B4C;
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
"""
style += extra_patient_css

with open("frontend_patient/style.css", "w", encoding="utf-8") as f:
    f.write(style)

print("frontend_patient/style.css: back-link + foco/reduced-motion añadidos")
print("\nTodo aplicado correctamente.")
