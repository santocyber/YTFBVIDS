#!/bin/bash
# Inicia o servidor YTFBVIDS na porta 5080
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"
LOG_FILE="/tmp/ytfbvids.log"

# Mata processo antigo se existir
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Parando servidor antigo (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# Inicia servidor com nohup
cd "$DIR"
nohup python3 app.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

sleep 2
if kill -0 "$NEW_PID" 2>/dev/null; then
    echo ""
    echo "✅ YTFBVIDS rodando em http://localhost:5080"
    echo "   Log: tail -f $LOG_FILE"
    echo "   Parar: ./stop.sh"
else
    echo "❌ Erro ao iniciar servidor. Veja o log:"
    tail -5 "$LOG_FILE"
    exit 1
fi
