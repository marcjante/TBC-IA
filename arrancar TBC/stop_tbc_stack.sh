#!/bin/bash
# stop_tbc_stack.sh
# Para los tres servicios arrancados por start_tbc_stack.sh, usando los
# PID guardados. Si algún PID no existe o ya no corresponde a un proceso
# vivo, lo indica y sigue con el resto sin fallar.

LOG_DIR="$HOME/tbc_stack_logs"

stop_one() {
    local name="$1"
    local pidfile="$LOG_DIR/$2.pid"
    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "$name: parado (PID $pid)"
        else
            echo "$name: el PID $pid ya no está activo"
        fi
        rm -f "$pidfile"
    else
        echo "$name: no hay PID guardado (¿se arrancó con start_tbc_stack.sh?)"
    fi
}

stop_one "Ollama" "ollama"
stop_one "Motor complementario" "sota_engine"
stop_one "TBC-AI" "tbc_ai"
stop_one "Llamafile / Mistral" "llamafile"
stop_one "n8n" "n8n"
stop_one "Bibliografia TBC" "bibliography"
stop_one "Panel TBC-IA" "dashboard"
