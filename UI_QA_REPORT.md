# UI QA Report

## Estado general
**APROBADO**

## Default exchange
- **Default**: Binance ✅
- **Fallback order**: Binance -> KuCoin ✅
- **Manual mode**: Respeta la selección manual (probado en tests y lógica de UI) ✅

## Pestañas revisadas
### Analyze
- Funciona con modo SPOT/FUTURES.
- Muestra Score, Decision, Reasons y Warnings.
- Respeta Strategy Profile seleccionado.
- Muestra el exchange realmente usado.

### Market Scanner
- Funciona con límites de escaneo y workers.
- Guarda resultados en SQLite.
- Muestra progreso en tiempo real.

### Validate
- Permite validar símbolos específicos.
- Integrado con la lógica de strategy_engine.

### Signals
- Muestra historial de señales desde SQLite.
- Filtros por símbolo, exchange y perfil funcionan.

### Full Cycle
- Ejecuta flujo completo (Scanner + Validate).
- Persistencia en SQLite verificada.

### Diagnostics
- **NUEVO**: Muestra versión de Python, Backend de Storage, Path de SQLite.
- Muestra Exchange Default y Orden de Fallback.
- Lista los perfiles de estrategia disponibles.
- Botón de "Test connectivity" funcional para verificar exchanges en vivo.

### Dashboard
- Métricas ejecutivas funcionales.
- Gráficos de PnL y Winrate operativos.
- Robusto ante base de datos vacía (probado con mock tests).

### Strategy Comparison
- Agrupa métricas por perfil (`conservative`, `balanced`, etc.).
- Muestra datos legacy correctamente.
- Curva de equidad comparativa funcional.
- Exportación CSV y Markdown funcional.

## Bugs encontrados
- `app.py` tenía "Manual" como default en el selector de modo de exchange a pesar de que el config pedía "fallback" (CORREGIDO).
- `tabulate` faltaba en requirements.txt para exportación Markdown (CORREGIDO en fase previa).
- `NameError` ocasional en CLI por imports faltantes (`datetime`, `pd`) (CORREGIDO en fase previa).

## Bugs corregidos
- Ajuste de índices por defecto en selectores de `app.py`.
- Inclusión de información de sistema en la pestaña de Diagnósticos.
- Corrección de imports en `app.py` (`platform`).

## Comandos ejecutados
- `python cli.py --scan --limit 5`
- `python cli.py --strategy-report`
- `python check_deploy_ready.py`

## Tests ejecutados
- `tests_exchange_defaults.py` (5 passed) ✅
- `tests_ui_smoke.py` (4 passed) ✅
- `tests_performance_metrics.py` (6 passed) ✅
- `tests_dashboard.py` (5 passed) ✅
- `tests_pipeline_smoke.py` ✅
- `check_deploy_ready.py` ✅

## Resultado check_deploy_ready.py
**DEPLOY READY ✅**

## Resultado package_project.py
**Included files: 62** (Incluyendo nuevos módulos de métricas y tests).

## Veredicto final
El sistema es estable, respeta los nuevos defaults de Binance y KuCoin, y la interfaz de usuario proporciona toda la información necesaria para el diagnóstico y análisis de estrategias sin exponer secretos.
