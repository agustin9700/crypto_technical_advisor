# Paper Trading Setup

Este proyecto puede operar en modo paper conectado a sandbox de exchange via CCXT o en modo offline local si no hay credenciales configuradas.

## KuCoin Sandbox

1. Entrar a https://sandbox.kucoin.com
2. Crear una cuenta sandbox.
3. Ir a la sección de API Management.
4. Crear una API key para trading sandbox.
5. Guardar estos datos:
   - API key
   - API secret
   - API password o passphrase
6. Configurar variables de entorno.

Windows:

```bat
set PAPER_API_KEY=tu_key
set PAPER_API_SECRET=tu_secret
set PAPER_API_PASSWORD=tu_password
```

Linux/Mac:

```bash
export PAPER_API_KEY=tu_key
export PAPER_API_SECRET=tu_secret
export PAPER_API_PASSWORD=tu_password
```

KuCoin Sandbox requiere `PAPER_API_PASSWORD`. Si falta, el sistema no intenta operar online en KuCoin.

## Binance Testnet

1. Entrar a https://testnet.binance.vision
2. Crear o acceder a la cuenta de testnet.
3. Generar API key y API secret.
4. Configurar variables de entorno.

Windows:

```bat
set PAPER_API_KEY=tu_key
set PAPER_API_SECRET=tu_secret
```

Linux/Mac:

```bash
export PAPER_API_KEY=tu_key
export PAPER_API_SECRET=tu_secret
```

Binance Testnet no requiere `PAPER_API_PASSWORD`.

## Scripts de arranque seguros

Los scripts `start_paper.sh` y `start_paper.bat` no contienen credenciales. Primero configurar variables de entorno:

Git Bash:

```bash
export PAPER_API_KEY=tu_key
export PAPER_API_SECRET=tu_secret
bash start_paper.sh
```

PowerShell/CMD:

```bat
set PAPER_API_KEY=tu_key
set PAPER_API_SECRET=tu_secret
start_paper.bat
```

## Verificar conexión

Ejecutar:

```bash
python -c "import paper_trader; pt = paper_trader.PaperTrader(); print(pt.get_summary())"
```

Si las credenciales son válidas, el resumen debe mostrar `modo: online`. Si falta alguna credencial o el sandbox rechaza la conexión, el sistema cae a modo offline y lo registra por logging.

## Modo offline

Si no se setean las variables de entorno, el sistema funciona igual pero simula todo localmente sin conectarse al exchange.

Este modo sirve para validar la lógica de apertura, cierre, PnL, reportes y UI antes de conseguir credenciales sandbox.

Comandos útiles:

```bash
python cli.py --paper-status
python cli.py --paper-start --paper-dry-run
python cli.py --paper-start --paper-capital 1000 --paper-interval 60
python cli.py --paper-close BTC/USDT
```
