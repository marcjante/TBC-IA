#!/bin/bash
# start_tbc_stack.sh
#
# Arranca los cinco servicios necesarios para probar TBC-AI con el motor
# complementario, el motor de consenso y las automatizaciones integrados,
# cada uno en segundo plano con su propio log:
#   1. Ollama              (puerto 11434)
#   2. Motor complementario / tbc-ia-sota-engine (puerto 8000)
#   3. TBC-AI backend      (puerto 8001)
#   4. Llamafile / Mistral (puerto 8081) — usado por dual_model_check.py
#   5. n8n                 (puerto 5678) — copias de seguridad automáticas
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

LOG_DIR="$HOME/tbc_stack_logs"
mkdir -p "$LOG_DIR"

echo "Logs en: $LOG_DIR"
echo ""

# --- 1. Ollama ---
if curl -s http://127.0.0.1:11434 > /dev/null 2>&1; then
    echo "[1/5] Ollama ya está corriendo, no se toca."
else
    echo "[1/5] Arrancando Ollama..."
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
    echo "[2/5] Motor complementario ya está corriendo, no se toca."
else
    echo "[2/5] Arrancando motor complementario (tarda ~10-15s en cargar modelos)..."
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
    echo "[3/5] TBC-AI ya está corriendo, no se toca."
else
    echo "[3/5] Arrancando TBC-AI..."
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
    echo "[4/5] Llamafile (Mistral) ya está corriendo, no se toca."
else
    if [ ! -f "$LLAMAFILE_DIR/$LLAMAFILE_BIN" ]; then
        echo "[4/5] AVISO: no encuentro $LLAMAFILE_DIR/$LLAMAFILE_BIN, no se arranca."
    else
        echo "[4/5] Arrancando Llamafile (Mistral)..."
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
    echo "[5/5] n8n ya está corriendo, no se toca."
else
    echo "[5/5] Arrancando n8n..."
    (
        NODES_EXCLUDE="[]" nohup n8n start > "$LOG_DIR/n8n.log" 2>&1 &
        echo $! > "$LOG_DIR/n8n.pid"
        disown
    )
    echo "      Arrancando en segundo plano (PID $(cat "$LOG_DIR/n8n.pid" 2>/dev/null))."
    echo "      Comprueba con: tail -f $LOG_DIR/n8n.log"
fi

echo ""
echo "Espera unos 15-20 segundos a que el motor complementario y n8n arranquen,"
echo "luego verifica el estado con: bash status_tbc_stack.sh"
