@echo off
setlocal EnableExtensions

echo == Crypto Technical Advisor - Binance Testnet Paper Trading ==

cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: No se pudo entrar al directorio del proyecto.
  exit /b 1
)

echo [1/4] Detectando Python disponible...
set "PYTHON_CMD="

for %%P in (python python3 py) do (
  if not defined PYTHON_CMD (
    where %%P >nul 2>nul
    if not errorlevel 1 (
      %%P -c "import sys; sys.exit(0)" >nul 2>nul
      if not errorlevel 1 set "PYTHON_CMD=%%P"
    )
  )
)

if not defined PYTHON_CMD (
  echo ERROR: No se encontro un ejecutable de Python valido.
  echo Instala Python o agrega python, python3 o py al PATH de Windows.
  exit /b 1
)

echo Python detectado: %PYTHON_CMD%
echo [2/4] Configurando credenciales de Binance Testnet...

REM === Binance Testnet API keys ===
REM Configuralas antes de correr este script:
REM   set PAPER_API_KEY=tu_api_key
REM   set PAPER_API_SECRET=tu_api_secret
REM No pegues credenciales reales en archivos versionables.
if "%PAPER_EXCHANGE%"=="" set "PAPER_EXCHANGE=binance"

if "%PAPER_API_KEY%"=="" (
  echo ERROR: PAPER_API_KEY debe estar configurada como variable de entorno.
  echo Ejemplo: set PAPER_API_KEY=tu_api_key
  exit /b 1
)

if "%PAPER_API_SECRET%"=="" (
  echo ERROR: PAPER_API_SECRET debe estar configurada como variable de entorno.
  echo Ejemplo: set PAPER_API_SECRET=tu_api_secret
  exit /b 1
)

echo Credenciales configuradas para Binance Testnet.

echo [3/4] Verificando conexion con paper_trader...
%PYTHON_CMD% -c "import os, paper_trader; pt = paper_trader.PaperTrader(os.getenv('PAPER_EXCHANGE', 'binance')); print(pt.get_summary())"
if errorlevel 1 (
  echo ERROR: La verificacion fallo.
  echo Revisa credenciales, dependencias y conexion a Binance Testnet.
  exit /b 1
)

echo Verificacion OK.
echo [4/4] Iniciando ciclo de paper trading...
%PYTHON_CMD% paper_cycle.py --exchange %PAPER_EXCHANGE% --capital 1000 --interval 60
exit /b %ERRORLEVEL%
