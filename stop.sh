#!/bin/bash
# Para o servidor YTFBVIDS
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Parando servidor (PID $PID)..."
        kill "$PID" 2>/dev/null
        sleep 1
        if kill -0 "$PID" 2>/dev/null; then
            echo "Forçando parada..."
            kill -9 "$PID" 2>/dev/null
        fi
        echo "✅ Servidor parado."
    else
        echo "Servidor ja nao estava rodando."
    fi
    rm -f "$PID_FILE"
else
    # Tenta encontrar pelo nome
    PID=$(pgrep -f "python3.*app.py" 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Parando servidor (PID $PID)..."
        kill "$PID" 2>/dev/null
        echo "✅ Servidor parado."
    else
        echo "Nenhum servidor rodando."
    fi
fi
