#!/bin/bash
# status_tbc_stack.sh
# Comprueba si los tres servicios responden.

echo -n "Ollama (11434):              "
if curl -s http://127.0.0.1:11434 > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "Motor complementario (8000): "
if curl -s http://127.0.0.1:8000 > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "TBC-AI (8001):               "
if curl -s http://127.0.0.1:8001 > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "Llamafile / Mistral (8081):  "
if curl -s http://127.0.0.1:8081/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "n8n (5678):                  "
if curl -s http://127.0.0.1:5678 > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "Bibliografia TBC (8002):     "
if curl -s http://127.0.0.1:8002/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi

echo -n "Panel TBC-IA (8090):         "
if curl -s http://127.0.0.1:8090 > /dev/null 2>&1; then
    echo "OK"
else
    echo "NO RESPONDE"
fi
