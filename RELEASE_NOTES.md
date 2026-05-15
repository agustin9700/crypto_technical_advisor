# Release Notes

## maintenance-v1 (Actual)

Estado:
- **Limpieza de Caches y Temporales**: Completada via `tools/clean_project.py` ✅
- **Auditoría de Dependencias**: Eliminada `starlette`, consolidado `requirements.txt` ✅
- **Hoja de Ruta Actualizada**: Hitos de SQLite y Estrategias marcados como completados ✅
- **Corrección de Tests**: Sincronización de `tests_futures_smoke.py` con la lógica de apalancamiento ✅
- **Empaquetado Robusto**: Exclusión de backups y temporales verificada ✅

Fecha:
- 2026-05-15 (Local)

## strategy-profiles-v2

Estado:
- **Binance como Exchange por Defecto** ✅
- **Orden de Fallback configurado**: Binance -> KuCoin ✅
- **Modo Manual**: Respeta la selección del usuario ✅
- **QA de UI Streamlit**: Todas las pestañas verificadas y funcionales ✅
- **Diagnósticos**: Pestaña mejorada con info de sistema y conectividad ✅
- **Tests de Humo UI**: Implementados y aprobados ✅
- **Packaging**: Verificado (Binance default incluido) ✅

Fecha:
- 2026-05-15 (Local)

## strategy-profiles-v1

Estado:
- SQLite operativo
- Strategy profiles auditados (5 perfiles: conservative, balanced, aggressive, scalping, swing)
- Dashboard operativo con filtros por perfil
- CLI parametrizada con soporte para --strategy
- check_deploy_ready.py aprobado ✅

Fecha:
- 2026-05-14 (Local)

Notas:
- Esta versión es apta para análisis técnico, backtesting, scanner, dashboard de performance y paper trading.
- La lógica de trading está parametrizada mediante archivos JSON en la carpeta `strategies/`.
- No está habilitada para trading real automático (modo simulación/análisis únicamente).
- El sistema utiliza SQLite como backend de almacenamiento principal por defecto.
