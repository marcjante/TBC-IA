#!/bin/bash
# start_tbc_stack.sh
#
# Arranca los siete servicios necesarios para probar TBC-AI con el motor
# complementario, el motor de consenso, la bibliografia verificada, las
# automatizaciones y el panel de estado, cada uno en segundo plano con su
# propio log:
#   1. Ollama              (puerto 11434)
#   2. Motor complementario / tbc-ia-sota-engine (puerto 8000)
#   3. TBC-AI backend      (puerto 8001)
#   4. Llamafile / Mistral (puerto 8081) — usado por dual_model_check.py
#   5. n8n                 (puerto 5678) — copias de seguridad automáticas
#   6. Bibliografia TBC     (puerto 8002) — tbc_master.db (PubMed+EuropePMC+
#                            PubTator3+CrossRef)
#   7. Panel TBC-IA         (puerto 8090) — vista unica de los seis servicios
#
# Cada proceso se lanza con nohup + disown, para que sobreviva aunque
# cierres la ventana de Terminal donde lo arrancaste (nohup por si solo no
# siempre basta en macOS si se cierra la ventana entera).
#
# AJUSTA estas rutas si tus proyectos no están donde se indica:
SOTA_ENGINE_DIR="$HOME/Desktop/TBC IA/tbc-ia-sota-engine"
TBC_AI_DIR="$HOME/Desktop/TBC IA"
LLAMAFILE_DIR="$HOME/Desktop/TBC IA/llamafile-test"
LLAMAFILE_BIN="mistral.llamafile"
BIBLIOGRAPHY_DIR="$HOME/Desktop/TBC IA/tbc-master-database"
DASHBOARD_DIR="$HOME/Desktop/TBC IA/dashboard"

LOG_DIR="$HOME/tbc_stack_logs"
mkdir -p "$LOG_DIR"

echo "Logs en: $LOG_DIR"
echo ""

# --- 1. Ollama ---
if curl -s http://127.0.0.1:11434 > /dev/null 2>&1; then
    echo "[1/7] Ollama ya está corriendo, no se toca."
else
    echo "[1/7] Arrancando Ollama..."
    nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    echo $! > "$LOG_DIR/ollama.pid"
    disown
    sleep 2
    if curl -s http://127.0.0.1:11434 > /dev/null 2>&1; then
        echo "      OK (PID $(cat "$LOG_DIR/ollama.pid"))"
    else
        echo "      AVISO: no responde todavía tras 2s, revisa $LOG_DIR/ollama.log"
    fi
fi

# --- 2. Motor complementario (tbc-ia-sota-engine, puerto 8000) ---
if curl -s http://127.0.0.1:8000 > /dev/null 2>&1; then
    echo "[2/7] Motor complementario ya está corriendo, no se toca."
else
    echo "[2/7] Arrancando motor complementario (tarda ~10-15s en cargar modelos)..."
    (
        cd "$SOTA_ENGINE_DIR" || exit 1
        source venv/bin/activate
        nohup python app/main.py > "$LOG_DIR/sota_engine.log" 2>&1 &
        echo $! > "$LOG_DIR/sota_engine.pid"
        disown
    )
    echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/sota_engine.pid" 2>/dev/null))."
    echo "      Comprueba con: tail -f $LOG_DIR/sota_engine.log"
fi

# --- 3. TBC-AI backend (puerto 8001) ---
if curl -s http://127.0.0.1:8001 > /dev/null 2>&1; then
    echo "[3/7] TBC-AI ya está corriendo, no se toca."
else
    echo "[3/7] Arrancando TBC-AI..."
    (
        cd "$TBC_AI_DIR" || exit 1
        source venv/bin/activate
        nohup uvicorn backend.main:app --port 8001 > "$LOG_DIR/tbc_ai.log" 2>&1 &
        echo $! > "$LOG_DIR/tbc_ai.pid"
        disown
    )
    echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/tbc_ai.pid" 2>/dev/null))."
    echo "      Comprueba con: tail -f $LOG_DIR/tbc_ai.log"
fi

# --- 4. Llamafile / Mistral (puerto 8081, usado por dual_model_check.py) ---
if curl -s http://127.0.0.1:8081/health > /dev/null 2>&1; then
    echo "[4/7] Llamafile (Mistral) ya está corriendo, no se toca."
else
    if [ ! -f "$LLAMAFILE_DIR/$LLAMAFILE_BIN" ]; then
        echo "[4/7] AVISO: no encuentro $LLAMAFILE_DIR/$LLAMAFILE_BIN, no se arranca."
    else
        echo "[4/7] Arrancando Llamafile (Mistral)..."
        (
            cd "$LLAMAFILE_DIR" || exit 1
            nohup "./$LLAMAFILE_BIN" --server --port 8081 --nobrowser > "$LOG_DIR/llamafile.log" 2>&1 &
            echo $! > "$LOG_DIR/llamafile.pid"
            disown
        )
        echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/llamafile.pid" 2>/dev/null))."
        echo "      Comprueba con: tail -f $LOG_DIR/llamafile.log"
    fi
fi

# --- 5. n8n (puerto 5678, automatizaciones: copias de seguridad, etc.) ---
# NODES_EXCLUDE="[]" habilita nodos desactivados por defecto desde n8n 2.0
# (Execute Command, LocalFileTrigger) — necesario para el flujo de backups.
if curl -s http://127.0.0.1:5678 > /dev/null 2>&1; then
    echo "[5/7] n8n ya está corriendo, no se toca."
else
    echo "[5/7] Arrancando n8n..."
    (
        NODES_EXCLUDE="[]" nohup n8n start > "$LOG_DIR/n8n.log" 2>&1 &
        echo $! > "$LOG_DIR/n8n.pid"
        disown
    )
    echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/n8n.pid" 2>/dev/null))."
    echo "      Comprueba con: tail -f $LOG_DIR/n8n.log"
fi

# --- 6. Bibliografia TBC (puerto 8002, tbc_master.db) ---
if curl -s http://127.0.0.1:8002/health > /dev/null 2>&1; then
    echo "[6/7] Bibliografia TBC ya está corriendo, no se toca."
else
    if [ ! -f "$BIBLIOGRAPHY_DIR/bibliography_api.py" ]; then
        echo "[6/7] AVISO: no encuentro $BIBLIOGRAPHY_DIR/bibliography_api.py, no se arranca."
    else
        echo "[6/7] Arrancando Bibliografia TBC..."
        (
            cd "$BIBLIOGRAPHY_DIR" || exit 1
            source venv/bin/activate
            nohup python3 bibliography_api.py > "$LOG_DIR/bibliography.log" 2>&1 &
            echo $! > "$LOG_DIR/bibliography.pid"
            disown
        )
        echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/bibliography.pid" 2>/dev/null))."
        echo "      Comprueba con: tail -f $LOG_DIR/bibliography.log"
    fi
fi

# --- 7. Panel TBC-IA (puerto 8090, vista unica de los seis servicios) ---
if curl -s http://127.0.0.1:8090 > /dev/null 2>&1; then
    echo "[7/7] Panel TBC-IA ya está corriendo, no se toca."
else
    if [ ! -f "$DASHBOARD_DIR/dashboard_service.py" ]; then
        echo "[7/7] AVISO: no encuentro $DASHBOARD_DIR/dashboard_service.py, no se arranca."
    else
        echo "[7/7] Arrancando Panel TBC-IA..."
        (
            cd "$DASHBOARD_DIR" || exit 1
            source venv/bin/activate
            nohup python3 dashboard_service.py > "$LOG_DIR/dashboard.log" 2>&1 &
            echo $! > "$LOG_DIR/dashboard.pid"
            disown
        )
        echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/dashboard.pid" 2>/dev/null))."
        echo "      Abre: http://127.0.0.1:8090"
    fi
fi

echo ""
echo "Espera unos 15-20 segundos a que el motor complementario y n8n arranquen,"
echo "luego verifica el estado con: bash status_tbc_stack.sh"
echo "o abre el panel visual en: http://127.0.0.1:8090"
