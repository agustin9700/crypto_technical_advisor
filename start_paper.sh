#!/usr/bin/env bash

# Start Binance Testnet paper trading from Git Bash on Windows.
# If Git Bash prints "sed: command not found" before this script starts,
# it usually comes from ~/.bashrc. This script does not use sed, so that
# warning can be ignored.

set -u
set -o pipefail

echo "== Crypto Technical Advisor - Binance Testnet Paper Trading =="

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi

if ! cd "$SCRIPT_DIR"; then
  echo "ERROR: No se pudo entrar al directorio del proyecto."
  exit 1
fi

find_python() {
  local candidate

  for candidate in python python3 py; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  return 1
}

echo "[1/4] Detectando Python disponible..."
if ! PYTHON_CMD="$(find_python)"; then
  echo "ERROR: No se encontro un ejecutable de Python valido."
  echo "Instala Python o agrega python, python3 o py al PATH de Git Bash."
  exit 1
fi
echo "Python detectado: $PYTHON_CMD"

echo "[2/4] Configurando credenciales de Binance Testnet..."

# === Binance Testnet API keys ===
# Exportalas antes de correr este script o cargalas desde un .env local:
#   export PAPER_API_KEY="tu_api_key"
#   export PAPER_API_SECRET="tu_api_secret"
# No pegues credenciales reales en archivos versionables.
PAPER_API_KEY="${PAPER_API_KEY:-}"
PAPER_API_SECRET="${PAPER_API_SECRET:-}"
PAPER_EXCHANGE="${PAPER_EXCHANGE:-binance}"

if [[ -z "$PAPER_API_KEY" || -z "$PAPER_API_SECRET" ]]; then
  echo "ERROR: PAPER_API_KEY y PAPER_API_SECRET deben estar configuradas como variables de entorno."
  echo "Ejemplo:"
  echo "  export PAPER_API_KEY=\"tu_api_key\""
  echo "  export PAPER_API_SECRET=\"tu_api_secret\""
  exit 1
fi
export PAPER_API_KEY PAPER_API_SECRET PAPER_EXCHANGE

echo "Credenciales configuradas para Binance Testnet."
echo "Nota: si viste 'sed: command not found', es un warning de .bashrc y no afecta esta ejecucion."

echo "[3/4] Verificando conexion con paper_trader..."
if "$PYTHON_CMD" -c "import os, paper_trader; pt = paper_trader.PaperTrader(os.getenv('PAPER_EXCHANGE', 'binance')); print(pt.get_summary())"; then
  echo "Verificacion OK."
else
  status=$?
  echo "ERROR: La verificacion fallo con codigo $status."
  echo "Revisa credenciales, dependencias y conexion a Binance Testnet."
  exit "$status"
fi

echo "[4/4] Iniciando ciclo de paper trading..."
exec "$PYTHON_CMD" paper_cycle.py --exchange "$PAPER_EXCHANGE" --capital 1000 --interval 60
