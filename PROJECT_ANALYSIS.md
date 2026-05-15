# Crypto Technical Advisor - Análisis Arquitectónico y Estado del Proyecto

## Fase de estabilización completada

Se completó una fase incremental de seguridad y consistencia:

- Secretos removidos de scripts versionables; `.env.example` queda como plantilla segura.
- `data_provider.py` distingue `spot` y `futures`, incluyendo metadata de exchange real, símbolo de mercado y fallback.
- `backtester.py` dejó de usar una lógica de entrada simplificada y ahora evalúa con `strategy_engine.evaluate_signal()`.
- `futures_analyzer.py` usa la misma fuente de scoring que `backtester.py` para modo futures.
- SQLite quedó integrado al flujo real como default, manteniendo CSV como fallback legacy.
- Se agregó rate limit global configurable para llamadas CCXT.
- Se agregó empaquetado limpio con `tools/package_project.py`.
- Se agregaron tests de storage, strategy engine, market routing y packager.

Limitación vigente: queda duplicación legacy no activa en módulos futures y faltan datasets matemáticos externos para validar indicadores contra referencias de mercado.

## 1. Resumen Ejecutivo
El proyecto `crypto_technical_advisor` es un sistema robusto de análisis cuantitativo y simulación de operaciones (*paper trading*) para los mercados de criptomonedas (Spot y Futuros). Está desarrollado íntegramente en Python y orquestado mediante scripts CLI y un dashboard interactivo en **Streamlit**. Utiliza la librería **CCXT** para conectarse a exchanges como KuCoin y Binance, y emplea **Pandas** y **Numpy** para los cálculos vectorizados de indicadores técnicos. 
El sistema mantiene estrictamente un enfoque "read-only" respecto al capital real, ejecutando simulaciones locales o a través de entornos "sandbox", ideal para propósitos de backtesting, asesoramiento y evaluación de estrategias.

## 2. Arquitectura del Sistema
El sistema posee una arquitectura basada en pipelines secuenciales de datos, separando la obtención, procesamiento y ejecución:
- **Data Ingestion (`data_provider.py`):** Encargado de la abstracción de los exchanges, gestionando el rate-limiting, paginación de datos OHLCV largos y lógica de "fallback" inteligente entre exchanges configurados (prioridad: KuCoin -> Binance).
- **Core de Análisis (`indicators.py`, `support_resistance.py`, `technical_analyzer.py`, `futures_analyzer.py`):** Calcula métricas técnicas (EMA, RSI, MACD, ATR, Volúmenes) y detecta clusters de Soporte/Resistencia. Aplica reglas heurísticas complejas para derivar un *Score* de 0 a 10 y dictaminar decisiones concretas (`LONG`, `SHORT`, `WAIT`, `ENTER_NOW_CANDIDATE`).
- **Escaneo y Validación (`scanner.py`, `validator.py`):** Permite analizar en lote las monedas de mayor volumen del mercado mediante *multithreading*, filtrando candidatos viables y confirmándolos con una validación secundaria.
- **Simulación y Persistencia (`paper_trader.py`, `signal_tracker.py`, `cycle_runner.py`, `storage.py`):** Gestiona el ciclo de vida de operaciones simuladas, desde la apertura basada en la señal, el cálculo del tamaño de la posición ajustado por riesgo (`config.RISK_PER_TRADE_PCT`), hasta su seguimiento y cierre (SL/TP). Usa SQLite por defecto y conserva CSV como fallback legacy.
- **Presentación (`app.py`, `cli.py`, `report_builder.py`):** Interfaces para la interacción humana. Generan reportes Markdown legibles y dashboards visuales detallados.

## 3. Flujo Operativo End-to-End
1. **Adquisición:** Se solicitan los símbolos de mayor liquidez (`scanner.py` a través de `data_provider.py`).
2. **Cálculo Técnico:** Se obtiene el OHLCV de cada símbolo en los timeframes configurados. Se calculan los indicadores matemáticos (`indicators.py`).
3. **Scoring:** `technical_analyzer` o `futures_analyzer` evalúan alineaciones de tendencias y momentum. Emiten un veredicto (ej: `ENTER_NOW_CANDIDATE`).
4. **Validación Histórica:** El sistema opcionalmente lanza `backtester.py` para realizar una comprobación de sanidad histórica de las métricas sobre ese mismo activo.
5. **Ejecución (Paper):** Si pasa los filtros, `paper_trader.py` o `signal_tracker.py` inician el tracking de la operación.
6. **Re-evaluación:** Mediante un bucle automatizado (`paper_cycle.py`), el sistema verifica periódicamente los precios actuales para procesar Take Profits (TP) o Stop Losses (SL).

## 4. Riesgos Potenciales y Bugs Identificados
- **Divergencia Analyzer vs Backtester:** El `backtester.py` posee su propia implementación reducida de condiciones de entrada (EMAs, MACD) la cual está **desacoplada** de las complejas reglas de scoring en `technical_analyzer.py`. Esto puede producir que las métricas de backtest no reflejen fielmente el rendimiento del analyzer en vivo.
- **Persistencia Legacy CSV:** El riesgo de concurrencia queda mitigado con SQLite por defecto. Si se fuerza `STORAGE_BACKEND=csv`, vuelven los riesgos propios de escritura concurrente sobre archivos CSV.
- **Rate-Limiting Susceptible:** Aunque `data_provider.py` maneja errores, el uso de multithreading en el scanner (`scanner.py` con hasta 8 workers) sobre la API pública de Binance/KuCoin sin un tokenizer global de peticiones cruzadas, puede provocar *IP bans* (429 Too Many Requests) en escaneos masivos (`--limit 100`).
- **Fallo Silencioso en Precios Offline:** En `paper_trader.py`, si falla la actualización de precios (`fetch_ohlcv` falla), el motor se apoya en el caché (`_last_prices`), lo cual puede retrasar cierres por SL y causar slippage fantasma en la simulación durante interrupciones de red.

## 5. Deuda Técnica
- **Código Duplicado en Analyzers:** `technical_analyzer.py` (Spot) y `futures_analyzer.py` (Futuros) contienen extensos bloques de código repetido (~1100 y ~600 líneas) para la asignación de puntajes, validación de volumen e impresión de razones. Falta una abstracción en una clase base (ej. `BaseAnalyzer`).
- **Hardcoding de Parámetros de Estrategia:** Los multiplicadores para ATR (Stop Loss y Take Profit) y los pesos del scoring se encuentran pre-configurados en `config.py` o directamente incrustados en los módulos. Esto dificulta la experimentación sin modificar el código fuente.
- **Falta de Unit Tests para Matemáticas:** Los tests (`tests_pipeline_smoke.py`, `tests_futures_smoke.py`) validan integraciones pero simulan/mockean los inputs y outputs (ej. `fake_backtest`, `synthetic_ohlcv`). No hay tests que aseguren que los cálculos de RSI, ATR y MACD no diverjan de los estándares de la industria (ej. TradingView).
- **Acoplamiento de Reportes:** `report_builder.py` depende rígidamente de las claves del diccionario generado por los analyzers, haciéndolo frágil ante cambios estructurales en los datos.

## 6. Recomendaciones y Próximos Pasos (Hoja de Ruta)

### Fase 1: Estabilización y Consolidación (Corto Plazo)
1. **Refactorización Orientada a Objetos:** Extraer la lógica común de `technical_analyzer` y `futures_analyzer` hacia un módulo genérico de estrategias (Pattern Strategy).
2. **Persistencia Robusta:** Reemplazar la escritura/lectura directa de CSVs por una base de datos **SQLite** mediante `SQLAlchemy` o `dataset` para transacciones seguras (ACID) y consultas analíticas.
3. **Manejo Global de Rate Limits:** Implementar un `TokenBucket` o un `Semaphore` global para limitar las solicitudes HTTP concurrentes en todo el proyecto, no solo por worker.

### Fase 2: Alineación Cuantitativa (Mediano Plazo)
4. **Unificación Analyzer-Backtester:** Asegurarse de que el motor de `backtester.py` importe y consuma la **misma función evaluadora** que el bot de live paper trading. El backtest debe evaluar los ticks históricos pasando por el `compute_score` unificado.
5. **Configuración de Estrategias via JSON/YAML:** Mover las constantes como `ATR_SL_MULT`, niveles críticos de RSI y requisitos mínimos de volumen a archivos de configuración de estrategia (ej. `strategy_aggressive.json`, `strategy_conservative.json`).

### Fase 3: Mejoras Analíticas (Largo Plazo)
6. **Ampliación del Dashboard de Performance:** Enriquecer `app.py` en la pestaña "Paper Trading" con analíticas avanzadas: Maximum Adverse Excursion (MAE), Maximum Favorable Excursion (MFE), gráficos de distribución de trades y heatmaps de timeframes ganadores.
7. **Suite de Pruebas Matemáticas:** Crear un módulo `tests_math.py` que importe series de datos históricos con indicadores previamente validados (dataset de control) para realizar `assert` sobre los outputs de `indicators.py`.
