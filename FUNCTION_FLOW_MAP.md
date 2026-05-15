# Function Flow Map

## 1. Flujo Analyze (Spot/Futures)
Este flujo se activa desde la UI o CLI para analizar un símbolo específico.

```mermaid
graph TD
    UI[app.py / cli.py] --> Analyzer[technical_analyzer.py / futures_analyzer.py]
    Analyzer --> Provider[data_provider.py]
    Provider --> CCXT[ccxt library]
    Analyzer --> Indicators[indicators.py]
    Analyzer --> Engine[strategy_engine.py]
    Engine --> SR[support_resistance.py]
    Engine --> Config[strategy_config.py]
    Analyzer --> Report[report_builder.py]
```

## 2. Flujo Scanner (Masivo)
Escaneo de múltiples pares para encontrar candidatos.

```mermaid
graph TD
    UI[app.py / cli.py] --> Scanner[scanner.py]
    Scanner --> Provider[data_provider.py]
    Scanner --> Analyzer[technical_analyzer.py]
    Scanner --> Backtest[backtester.py]
    Scanner --> Storage[storage.py]
```

## 3. Flujo Paper Trading (Simulación)
Mantenimiento de posiciones simuladas.

```mermaid
graph TD
    UI[app.py / cli.py] --> Trader[paper_trader.py]
    Trader --> Provider[data_provider.py]
    Trader --> Storage[storage.py]
    Cycle[paper_cycle.py] --> Scanner
    Cycle --> Trader
```

## 4. Flujo Dashboard & Performance
Visualización de resultados históricos.

```mermaid
graph TD
    UI[app.py] --> Storage[storage.py]
    Storage --> Metrics[performance_metrics.py]
```

## 5. Flujo Diagnostics
Verificación de conectividad y entorno.

```mermaid
graph TD
    UI[app.py] --> Diagnostics[diagnostics.py]
    Diagnostics --> Provider[data_provider.py]
```
