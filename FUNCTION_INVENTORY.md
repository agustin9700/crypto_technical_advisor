# Function Inventory

## Resumen
- Total archivos analizados: 41
- Total funciones top-level: 359
- Total clases: 14
- Total métodos: 90
- Funciones/Métodos sin referencias externas directas: 50
- Funciones privadas (empiezan con _): 187
- Usadas por Streamlit (app.py): 61
- Usadas por CLI (cli.py): 48
- Usadas por tests: 140

## Por archivo

### app.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _exchange_label | 37 | function | app.py, tests_ui_smoke.py | PRIVATE_HELPER |
| _exchange_id_from_label | 41 | function | app.py, tests_ui_smoke.py | PRIVATE_HELPER |
| safe_unique_values | 49 | function | tests_app_robustness.py, app.py | KEEP_TEST |
| safe_union_unique | 60 | function | tests_app_robustness.py, app.py | KEEP_TEST |
| ensure_columns | 67 | function | tests_app_robustness.py, app.py | KEEP_TEST |
| _is_binance_network_error | 80 | function | app.py | PRIVATE_HELPER |
| _friendly_error | 98 | function | app.py, tests_ui_smoke.py | PRIVATE_HELPER |
| _show_action_error | 107 | function | app.py | PRIVATE_HELPER |
| render_decision_badge | 122 | function | app.py | KEEP_UI |
| _spot_best | 135 | function | app.py | PRIVATE_HELPER |
| _spot_plan | 139 | function | app.py | PRIVATE_HELPER |
| _spot_entry_text | 144 | function | app.py | PRIVATE_HELPER |
| render_action_hint | 153 | function | app.py | KEEP_UI |
| _summary_box | 175 | function | app.py | PRIVATE_HELPER |
| render_result_summary | 186 | function | app.py | KEEP_UI |
| _metric_display | 256 | function | app.py | PRIVATE_HELPER |
| render_backtest_metrics | 275 | function | app.py | KEEP_UI |
| render_advanced_details | 313 | function | app.py | KEEP_UI |
| futures_unavailable_notice | 382 | function | app.py | KEEP_UI |
| _paper_report_path | 386 | function | app.py | PRIVATE_HELPER |
| _get_paper_trader | 390 | function | app.py | PRIVATE_HELPER |
| _hours_since | 399 | function | app.py | PRIVATE_HELPER |
| _paper_positions_rows | 408 | function | app.py | PRIVATE_HELPER |
| render_paper_trading_tab | 435 | function | app.py | KEEP_UI |
| _get_signals_cached | 525 | function | app.py | PRIVATE_HELPER |
| _get_trades_cached | 529 | function | app.py | PRIVATE_HELPER |
| render_performance_dashboard_tab | 532 | function | app.py | KEEP_UI |
| format_list_cols | 620 | function | app.py | KEEP_UI |
| apply_comp_filters | 795 | function | app.py | KEEP_UI |
| update_scan_progress | 1080 | function | app.py | KEEP_UI |

### audit_functions.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| get_python_files | 6 | function | audit_functions.py | KEEP_CORE |
| audit_file | 16 | function | audit_functions.py | KEEP_CORE |
| Visitor | 27 | class | audit_functions.py | KEEP_CORE |
| Visitor.__init__ | 28 | method | python_internal | PRIVATE_HELPER |
| Visitor.visit_ClassDef | 31 | method | None | UNUSED_CANDIDATE |
| Visitor.visit_FunctionDef | 47 | method | audit_functions.py | KEEP_CORE |
| Visitor.visit_AsyncFunctionDef | 60 | method | None | UNUSED_CANDIDATE |
| find_references | 67 | function | audit_functions.py | KEEP_CORE |
| generate_report | 98 | function | audit_functions.py | KEEP_CORE |
| main | 160 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### backtester.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _entry_side | 13 | function | backtester.py | PRIVATE_HELPER |
| run_quick_backtest | 23 | function | scanner.py, tests_pipeline_smoke.py, tests_strategy_engine.py, validator.py, cli.py, app.py | KEEP_TEST |

### check_deploy_ready.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _relative | 79 | function | check_deploy_ready.py, package_project.py | PRIVATE_HELPER |
| _remove_pycache | 83 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _find_absolute_paths | 90 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _find_runtime_outputs | 116 | function | None | PRIVATE_HELPER |
| _find_clean_package_issues | 120 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _has_absolute_path | 143 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _find_packaging_issues | 161 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _find_hardcoded_secrets | 175 | function | check_deploy_ready.py | PRIVATE_HELPER |
| _compile_main_files | 201 | function | check_deploy_ready.py | PRIVATE_HELPER |
| check_deploy_ready | 226 | function | check_deploy_ready.py | KEEP_CORE |

### clean_project.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| clean_project | 6 | function | clean_project.py | KEEP_CORE |

### cli.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| print_separator | 35 | function | cli.py | KEEP_CLI |
| _backtest_warning | 42 | function | report_builder.py, cli.py | PRIVATE_HELPER |
| _print_list_section | 52 | function | cli.py | PRIVATE_HELPER |
| _dedupe_scan_rows | 62 | function | cli.py | PRIVATE_HELPER |
| print_result | 80 | function | cli.py | KEEP_CLI |
| print_scan_result | 179 | function | cli.py | KEEP_CLI |
| print_futures_result | 240 | function | cli.py | KEEP_CLI |
| print_paper_summary | 287 | function | cli.py | KEEP_CLI |
| print_strategy_report | 316 | function | cli.py | KEEP_CLI |
| main | 340 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |
| filter_df | 462 | function | cli.py | KEEP_CLI |

### config.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _env_bool | 4 | function | config.py | PRIVATE_HELPER |
| _env_float | 11 | function | config.py | PRIVATE_HELPER |
| _env_int | 18 | function | config.py | PRIVATE_HELPER |

### cycle_runner.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| run_cycle | 13 | function | app.py, cli.py | KEEP_CLI |
| render_sig_table | 172 | function | cycle_runner.py | KEEP_CORE |

### data_provider.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| normalize_market_type | 18 | function | data_provider.py, backtester.py | KEEP_CORE |
| _normalize_exchange_mode | 34 | function | data_provider.py | PRIVATE_HELPER |
| _normalize_exchange_id | 41 | function | data_provider.py | PRIVATE_HELPER |
| _exchange_priority | 49 | function | data_provider.py | PRIVATE_HELPER |
| _exchange_sequence | 53 | function | data_provider.py, tests_exchange_defaults.py | PRIVATE_HELPER |
| _ccxt_exchange_id | 70 | function | data_provider.py | PRIVATE_HELPER |
| _exchange_options | 76 | function | data_provider.py | PRIVATE_HELPER |
| get_exchange | 86 | function | data_provider.py, tests_market_type_routing.py | KEEP_TEST |
| normalize_symbol | 112 | function | scanner.py, backtester.py, data_provider.py, futures_analyzer.py, technical_analyzer.py | KEEP_CORE |
| copy_df_with_attrs | 133 | function | technical_analyzer.py, futures_analyzer.py | KEEP_CORE |
| _error_text | 139 | function | data_provider.py | PRIVATE_HELPER |
| _is_recoverable_exchange_error | 143 | function | data_provider.py | PRIVATE_HELPER |
| _load_markets | 168 | function | data_provider.py | PRIVATE_HELPER |
| _market_matches_type | 175 | function | data_provider.py | PRIVATE_HELPER |
| _market_symbol | 187 | function | data_provider.py | PRIVATE_HELPER |
| _source_meta | 202 | function | data_provider.py | PRIVATE_HELPER |
| _data_unavailable_error | 229 | function | data_provider.py | PRIVATE_HELPER |
| get_exchange_for_symbol | 238 | function | None | UNUSED_CANDIDATE |
| _ohlcv_dataframe | 268 | function | data_provider.py | PRIVATE_HELPER |
| _fetch_ohlcv_from_exchange | 281 | function | data_provider.py | PRIVATE_HELPER |
| fetch_ohlcv_with_fallback | 342 | function | data_provider.py, tests_strategy_engine.py, futures_analyzer.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| fetch_ohlcv | 383 | function | signal_tracker.py, backtester.py, tests_pipeline_smoke.py, diagnostics.py, data_provider.py, paper_trader.py, tests_strategy_engine.py, app.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| _quote_volume_from_ticker | 405 | function | data_provider.py | PRIVATE_HELPER |
| fetch_ticker_volume_with_fallback | 417 | function | data_provider.py | KEEP_CORE |
| fetch_ticker_volume | 464 | function | None | UNUSED_CANDIDATE |
| is_symbol_liquid | 473 | function | None | UNUSED_CANDIDATE |
| _top_symbols_for_exchange | 500 | function | data_provider.py | PRIVATE_HELPER |
| get_top_usdt_symbols_by_volume_result | 523 | function | scanner.py, data_provider.py | KEEP_CORE |
| get_top_usdt_symbols_by_volume | 554 | function | data_provider.py | KEEP_CORE |
| get_top_usdt_symbols_by_volume_with_fallback | 580 | function | None | UNUSED_CANDIDATE |

### diagnostics.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _runtime_info | 11 | function | diagnostics.py | PRIVATE_HELPER |
| _row | 19 | function | diagnostics.py | PRIVATE_HELPER |
| _request_test | 41 | function | diagnostics.py | PRIVATE_HELPER |
| _ccxt_test | 71 | function | diagnostics.py | PRIVATE_HELPER |
| run_binance_diagnostics | 96 | function | None | UNUSED_CANDIDATE |
| _exchange_row | 115 | function | diagnostics.py | PRIVATE_HELPER |
| run_exchange_diagnostics | 125 | function | app.py | KEEP_UI |

### futures_analyzer.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _copy_from_cache | 18 | function | futures_analyzer.py | PRIVATE_HELPER |
| _fetch_ohlcv_cached | 24 | function | tests_futures_smoke.py, technical_analyzer.py, futures_analyzer.py | PRIVATE_HELPER |
| _source_meta_from_df | 62 | function | technical_analyzer.py, futures_analyzer.py | PRIVATE_HELPER |
| _data_unavailable_result | 76 | function | futures_analyzer.py | PRIVATE_HELPER |
| _result_from_strategy_signal | 114 | function | futures_analyzer.py | PRIVATE_HELPER |
| analyze_futures_symbol_timeframe | 175 | function | tests_futures_smoke.py, tests_strategy_engine.py, cli.py, futures_analyzer.py, app.py, tests_market_type_routing.py | KEEP_TEST |
| _auto_rank | 232 | function | futures_analyzer.py | PRIVATE_HELPER |
| analyze_futures_symbol_auto | 242 | function | app.py, cli.py, tests_futures_smoke.py | KEEP_TEST |

### import_csv_to_sqlite.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _read_csv | 14 | function | import_csv_to_sqlite.py | PRIVATE_HELPER |
| import_latest_scan | 21 | function | import_csv_to_sqlite.py | KEEP_CORE |
| import_paper_trades | 43 | function | import_csv_to_sqlite.py | KEEP_CORE |
| main | 64 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### indicators.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| ema | 6 | function | indicators.py | KEEP_CORE |
| rsi | 10 | function | scanner.py, backtester.py, indicators.py, tests_pipeline_smoke.py, tests_futures_smoke.py, strategy_engine.py, tests_strategy_engine.py, report_builder.py, cli.py, validator.py, futures_analyzer.py, app.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| atr | 20 | function | backtester.py, indicators.py, tests_futures_smoke.py, strategy_engine.py, tests_strategy_engine.py, futures_analyzer.py, app.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| macd | 32 | function | indicators.py, tests_futures_smoke.py, strategy_engine.py, tests_strategy_engine.py, futures_analyzer.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| bollinger_bands | 41 | function | indicators.py | KEEP_CORE |
| add_indicators | 51 | function | backtester.py, tests_futures_smoke.py, strategy_engine.py, tests_strategy_engine.py, futures_analyzer.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |

### package_project.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _relative | 60 | function | check_deploy_ready.py, package_project.py | PRIVATE_HELPER |
| _has_secret_assignment | 64 | function | tests_package_project.py, package_project.py | PRIVATE_HELPER |
| classify_path | 80 | function | tests_package_project.py, package_project.py | KEEP_TEST |
| collect_files | 99 | function | tests_package_project.py, check_deploy_ready.py, package_project.py | KEEP_TEST |
| create_zip | 123 | function | package_project.py | KEEP_CORE |
| main | 133 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### paper_cycle.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _row_to_signal | 14 | function | paper_cycle.py | PRIVATE_HELPER |
| _log_closed_trades | 33 | function | paper_cycle.py | PRIVATE_HELPER |
| _open_new_positions | 45 | function | paper_cycle.py | PRIVATE_HELPER |
| run_paper_cycle | 87 | function | paper_cycle.py, cli.py | KEEP_CLI |
| _parse_args | 154 | function | paper_cycle.py | PRIVATE_HELPER |
| main | 166 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### paper_trader.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _now_utc | 23 | function | paper_trader.py | PRIVATE_HELPER |
| _iso_utc | 27 | function | paper_trader.py | PRIVATE_HELPER |
| _parse_utc | 37 | function | paper_trader.py | PRIVATE_HELPER |
| _output_path | 48 | function | paper_trader.py | PRIVATE_HELPER |
| PaperPosition | 53 | class | paper_trader.py | KEEP_CORE |
| PaperTrader | 74 | class | tests_storage_sqlite.py, paper_trader.py, cli.py, paper_cycle.py, app.py | KEEP_TEST |
| PaperTrader.__init__ | 83 | method | python_internal | PRIVATE_HELPER |
| PaperTrader.open_position | 106 | method | paper_cycle.py, tests_storage_sqlite.py | KEEP_TEST |
| PaperTrader.update_positions | 174 | method | app.py, paper_cycle.py | KEEP_UI |
| PaperTrader._close_position | 207 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader.close_position_manual | 287 | method | app.py, cli.py | KEEP_CLI |
| PaperTrader.get_summary | 306 | method | app.py, cli.py, paper_cycle.py | KEEP_CLI |
| PaperTrader._save_report | 351 | method | paper_trader.py, paper_cycle.py | PRIVATE_HELPER |
| PaperTrader._current_equity | 417 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader.load_from_report | 433 | method | app.py, cli.py, paper_cycle.py, tests_storage_sqlite.py | KEEP_TEST |
| PaperTrader._save_sqlite_state | 482 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._position_storage_key | 486 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._position_storage_payload | 496 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._persist_position_open | 516 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._load_from_sqlite | 524 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._position_from_storage | 538 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._closed_trade_from_storage | 555 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._create_entry_order | 575 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._create_close_order | 593 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._connect_exchange | 611 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._exchange_call | 666 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._get_current_price | 682 | method | app.py, paper_trader.py | PRIVATE_HELPER |
| PaperTrader._exit_price_for_reason | 692 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._snapshot_equity | 701 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._unrealized_pnl | 707 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._max_drawdown_pct | 717 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._sharpe_ratio | 729 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._position_to_dict | 737 | method | paper_trader.py | PRIVATE_HELPER |
| PaperTrader._position_from_dict | 742 | method | paper_trader.py | PRIVATE_HELPER |

### performance_metrics.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| normalize_strategy_profile | 5 | function | tests_performance_metrics.py, performance_metrics.py | KEEP_TEST |
| calculate_trade_metrics | 19 | function | tests_performance_metrics.py, performance_metrics.py | KEEP_TEST |
| calculate_signal_metrics | 107 | function | performance_metrics.py | KEEP_CORE |
| calculate_strategy_comparison | 129 | function | tests_performance_metrics.py, app.py, cli.py, performance_metrics.py | KEEP_TEST |
| calculate_equity_curve | 170 | function | tests_performance_metrics.py, app.py | KEEP_TEST |
| calculate_profile_summary | 201 | function | app.py, cli.py | KEEP_CLI |
| clean_pf | 208 | function | performance_metrics.py | KEEP_CORE |

### rate_limiter.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| is_enabled | 13 | function | rate_limiter.py | KEEP_CORE |
| requests_per_second | 17 | function | rate_limiter.py | KEEP_CORE |
| wait_for_slot | 25 | function | rate_limiter.py | KEEP_CORE |
| call | 39 | function | data_provider.py, tests_strategy_engine.py | KEEP_TEST |

### report_builder.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _backtest_warning | 15 | function | report_builder.py, cli.py | PRIVATE_HELPER |
| _get_analysis_time | 22 | function | report_builder.py | PRIVATE_HELPER |
| _format_analysis_time | 31 | function | report_builder.py | PRIVATE_HELPER |
| get_report_metadata | 50 | function | report_builder.py | KEEP_CORE |
| markdown_matches_symbol | 81 | function | None | UNUSED_CANDIDATE |
| _merge_warnings | 85 | function | scanner.py, report_builder.py | PRIVATE_HELPER |
| _add_multi_timeframe_table | 93 | function | report_builder.py | PRIVATE_HELPER |
| _plan_items | 129 | function | report_builder.py | PRIVATE_HELPER |
| build_markdown | 136 | function | report_builder.py | KEEP_CORE |
| save_report | 288 | function | app.py, cli.py | KEEP_CLI |

### scanner.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _normalize_scan_mode | 80 | function | scanner.py | PRIVATE_HELPER |
| _timeframes_for_mode | 87 | function | scanner.py | PRIVATE_HELPER |
| _ohlcv_limit_for_mode | 93 | function | scanner.py | PRIVATE_HELPER |
| _normalize_workers | 99 | function | scanner.py | PRIVATE_HELPER |
| _format_duration | 107 | function | scanner.py | PRIVATE_HELPER |
| _yes_no | 116 | function | scanner.py | PRIVATE_HELPER |
| _base_asset | 120 | function | scanner.py | PRIVATE_HELPER |
| _is_excluded_base_asset | 125 | function | scanner.py | PRIVATE_HELPER |
| _analysis_has_enough_history | 129 | function | scanner.py | PRIVATE_HELPER |
| _append_warning_text | 145 | function | scanner.py | PRIVATE_HELPER |
| _degrade_unvalidated_candidate | 152 | function | scanner.py | PRIVATE_HELPER |
| _validation_status | 173 | function | scanner.py | PRIVATE_HELPER |
| _apply_fast_pending_validation | 188 | function | scanner.py | PRIVATE_HELPER |
| _merge_warnings | 199 | function | scanner.py, report_builder.py | PRIVATE_HELPER |
| _decision_rank | 207 | function | scanner.py | PRIVATE_HELPER |
| _sort_key | 217 | function | scanner.py | PRIVATE_HELPER |
| _format_volume | 227 | function | scanner.py | PRIVATE_HELPER |
| _table_value | 238 | function | scanner.py | PRIVATE_HELPER |
| _scan_table | 245 | function | scanner.py | PRIVATE_HELPER |
| _build_row | 273 | function | scanner.py | PRIVATE_HELPER |
| _build_error_row | 336 | function | scanner.py | PRIVATE_HELPER |
| _write_csv | 393 | function | scanner.py | PRIVATE_HELPER |
| _write_markdown | 404 | function | scanner.py | PRIVATE_HELPER |
| _progress | 520 | function | scanner.py | PRIVATE_HELPER |
| _fetch_scan_symbols | 525 | function | scanner.py, tests_pipeline_smoke.py | PRIVATE_HELPER |
| _analyze_scan_symbol | 567 | function | scanner.py | PRIVATE_HELPER |
| run_scan | 644 | function | scanner.py, app.py, paper_cycle.py, tests_pipeline_smoke.py | KEEP_TEST |
| handle_symbol_result | 705 | function | scanner.py | KEEP_CORE |
| run_market_scan | 898 | function | cli.py, cycle_runner.py | KEEP_CLI |

### signal_tracker.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _ensure_columns | 24 | function | storage.py, signal_tracker.py | PRIVATE_HELPER |
| _ensure_file | 36 | function | signal_tracker.py | PRIVATE_HELPER |
| _to_utc_timestamp | 58 | function | signal_tracker.py | PRIVATE_HELPER |
| _storage_row_to_tracking_row | 68 | function | signal_tracker.py | PRIVATE_HELPER |
| load_signals_dataframe | 97 | function | signal_tracker.py, cycle_runner.py | KEEP_CORE |
| record_signal | 109 | function | validator.py, tests_storage_sqlite.py, tests_pipeline_smoke.py | KEEP_TEST |
| _generate_markdown | 177 | function | validator.py, signal_tracker.py | PRIVATE_HELPER |
| add_table | 184 | function | validator.py, signal_tracker.py | KEEP_CORE |
| _signal_group_key | 216 | function | signal_tracker.py | PRIVATE_HELPER |
| _evaluate_signal_row | 224 | function | signal_tracker.py | PRIVATE_HELPER |
| update_signals | 280 | function | app.py, cli.py, cycle_runner.py, tests_pipeline_smoke.py | KEEP_TEST |

### storage.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| utc_now | 14 | function | storage.py | KEEP_CORE |
| get_storage_backend | 18 | function | scanner.py, storage.py, cycle_runner.py, cli.py, app.py | KEEP_CLI |
| is_sqlite_backend | 22 | function | scanner.py, signal_tracker.py, storage.py, cycle_runner.py, validator.py, tests_dashboard.py, paper_trader.py | KEEP_TEST |
| is_csv_backend | 26 | function | None | UNUSED_CANDIDATE |
| get_sqlite_path | 30 | function | storage.py | KEEP_CORE |
| _json | 34 | function | storage.py | PRIVATE_HELPER |
| _loads | 38 | function | storage.py | PRIVATE_HELPER |
| SQLiteStorage | 50 | class | storage.py, tests_storage_sqlite.py, import_csv_to_sqlite.py | KEEP_TEST |
| SQLiteStorage.__init__ | 51 | method | python_internal | PRIVATE_HELPER |
| SQLiteStorage.connect | 57 | method | storage.py | KEEP_CORE |
| SQLiteStorage._ensure_schema | 72 | method | storage.py | PRIVATE_HELPER |
| SQLiteStorage._ensure_columns | 206 | method | storage.py, signal_tracker.py | PRIVATE_HELPER |
| SQLiteStorage.insert_signal | 248 | method | storage.py, tests_storage_sqlite.py, import_csv_to_sqlite.py | KEEP_TEST |
| SQLiteStorage.upsert_tracked_signal | 310 | method | tests_storage_sqlite.py, signal_tracker.py | KEEP_TEST |
| SQLiteStorage.list_signals | 405 | method | storage.py, tests_dashboard.py, signal_tracker.py, tests_storage_sqlite.py | KEEP_TEST |
| SQLiteStorage._signal_row_to_dict | 416 | method | storage.py | PRIVATE_HELPER |
| SQLiteStorage.update_tracked_signal | 425 | method | signal_tracker.py | KEEP_CORE |
| SQLiteStorage.insert_paper_trade | 459 | method | tests_storage_sqlite.py, import_csv_to_sqlite.py | KEEP_TEST |
| SQLiteStorage.upsert_open_paper_trade | 462 | method | storage.py, paper_trader.py | KEEP_CORE |
| SQLiteStorage.close_paper_trade | 506 | method | paper_trader.py, tests_storage_sqlite.py | KEEP_TEST |
| SQLiteStorage.list_paper_trades | 527 | method | storage.py, paper_trader.py | KEEP_CORE |
| SQLiteStorage.get_open_trades | 546 | method | paper_trader.py, tests_storage_sqlite.py | KEEP_TEST |
| SQLiteStorage.insert_scanner_run | 549 | method | scanner.py | KEEP_CORE |
| SQLiteStorage.get_latest_scanner_rows | 569 | method | validator.py | KEEP_CORE |
| SQLiteStorage.insert_validation_results | 579 | method | validator.py | KEEP_CORE |
| SQLiteStorage.insert_backtest_result | 603 | method | scanner.py, validator.py | KEEP_CORE |
| SQLiteStorage.insert_cycle_summary | 627 | method | cycle_runner.py | KEEP_CORE |
| get_storage | 646 | function | scanner.py, signal_tracker.py, storage.py, cycle_runner.py, import_csv_to_sqlite.py, validator.py, tests_dashboard.py, paper_trader.py | KEEP_TEST |
| get_all_signals | 650 | function | app.py, cli.py, tests_dashboard.py | KEEP_TEST |
| get_all_paper_trades | 662 | function | app.py, cli.py | KEEP_CLI |

### strategy_config.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| list_strategy_profiles | 10 | function | None | UNUSED_CANDIDATE |
| get_default_strategy_profile | 22 | function | strategy_engine.py | KEEP_CORE |
| load_strategy_profile | 26 | function | tests_strategy_config.py, strategy_engine.py | KEEP_TEST |
| validate_strategy_config | 54 | function | strategy_config.py | KEEP_CORE |
| _get_fallback_balanced_config | 79 | function | strategy_config.py | PRIVATE_HELPER |
| get_strategy_meta | 100 | function | tests_strategy_config.py | KEEP_TEST |

### strategy_engine.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| compute_spot_score | 47 | function | technical_analyzer.py, strategy_engine.py | KEEP_CORE |
| dynamic_sl_tp_mult | 127 | function | technical_analyzer.py, strategy_engine.py | KEEP_CORE |
| compute_long_rr | 152 | function | technical_analyzer.py, backtester.py, strategy_engine.py | KEEP_CORE |
| compute_short_rr | 164 | function | backtester.py, strategy_engine.py | KEEP_CORE |
| decide_spot | 176 | function | technical_analyzer.py, strategy_engine.py | KEEP_CORE |
| _ensure_indicator_frame | 208 | function | strategy_engine.py | PRIVATE_HELPER |
| _normal_market_type | 215 | function | strategy_engine.py | PRIVATE_HELPER |
| _source_value | 222 | function | strategy_engine.py | PRIVATE_HELPER |
| evaluate_signal | 226 | function | technical_analyzer.py, backtester.py, futures_analyzer.py, tests_strategy_engine.py | KEEP_TEST |
| _latest_futures_levels | 334 | function | tests_futures_smoke.py, strategy_engine.py | PRIVATE_HELPER |
| _futures_structure_flags | 344 | function | tests_futures_smoke.py, strategy_engine.py | PRIVATE_HELPER |
| _distance_pct | 354 | function | strategy_engine.py | PRIVATE_HELPER |
| score_futures_direction | 359 | function | strategy_engine.py | KEEP_CORE |
| futures_trade_plan | 491 | function | strategy_engine.py | KEEP_CORE |
| futures_decision_from_scores | 535 | function | strategy_engine.py | KEEP_CORE |
| futures_leverage_fields | 550 | function | tests_futures_smoke.py, strategy_engine.py | KEEP_TEST |
| _futures_texts | 575 | function | strategy_engine.py | PRIVATE_HELPER |
| _evaluate_futures_frame | 607 | function | strategy_engine.py | PRIVATE_HELPER |
| _legacy_evaluate_futures_row | 699 | function | None | PRIVATE_HELPER |
| normalize_analysis_result | 789 | function | None | UNUSED_CANDIDATE |

### support_resistance.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| find_support_resistance | 5 | function | strategy_engine.py | KEEP_CORE |
| _cluster_levels | 35 | function | support_resistance.py | PRIVATE_HELPER |
| _cluster_levels_weighted | 70 | function | support_resistance.py | PRIVATE_HELPER |
| find_support_resistance_weighted | 127 | function | support_resistance.py | KEEP_CORE |
| nearest_level | 163 | function | None | UNUSED_CANDIDATE |
| nearest_support_below | 170 | function | strategy_engine.py | KEEP_CORE |
| nearest_resistance_above | 178 | function | strategy_engine.py | KEEP_CORE |
| distance_pct | 186 | function | technical_analyzer.py, strategy_engine.py | KEEP_CORE |

### technical_analyzer.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _compute_score | 23 | function | None | PRIVATE_HELPER |
| _dynamic_sl_tp_mult | 27 | function | None | PRIVATE_HELPER |
| _compute_rr | 31 | function | None | PRIVATE_HELPER |
| _decide | 35 | function | None | PRIVATE_HELPER |
| get_btc_regime | 54 | function | scanner.py, technical_analyzer.py | KEEP_CORE |
| _is_near_resistance | 152 | function | technical_analyzer.py | PRIVATE_HELPER |
| _is_incomplete_candle | 157 | function | technical_analyzer.py | PRIVATE_HELPER |
| _adjust_intracandle_volume | 173 | function | technical_analyzer.py | PRIVATE_HELPER |
| _get_volume_for_scoring | 190 | function | technical_analyzer.py | PRIVATE_HELPER |
| _main_reason | 214 | function | technical_analyzer.py | PRIVATE_HELPER |
| _what_needs_to_happen | 247 | function | technical_analyzer.py | PRIVATE_HELPER |
| _entry_now_text | 284 | function | technical_analyzer.py | PRIVATE_HELPER |
| _entry_trigger | 317 | function | technical_analyzer.py | PRIVATE_HELPER |
| _invalidation_level | 343 | function | technical_analyzer.py | PRIVATE_HELPER |
| _action_summary | 355 | function | technical_analyzer.py | PRIVATE_HELPER |
| _human_verdict | 372 | function | technical_analyzer.py | PRIVATE_HELPER |
| _add_action_plan | 396 | function | technical_analyzer.py | PRIVATE_HELPER |
| _volume_regime_not_bad | 410 | function | technical_analyzer.py | PRIVATE_HELPER |
| _auto_candidate_rank | 416 | function | technical_analyzer.py | PRIVATE_HELPER |
| _is_auto_candidate_acceptable | 442 | function | technical_analyzer.py | PRIVATE_HELPER |
| _is_15m_candidate_recommendable | 450 | function | technical_analyzer.py | PRIVATE_HELPER |
| _best_observation | 460 | function | technical_analyzer.py | PRIVATE_HELPER |
| _observation_summary | 471 | function | technical_analyzer.py | PRIVATE_HELPER |
| _pick_auto_timeframe | 480 | function | technical_analyzer.py | PRIVATE_HELPER |
| _build_no_clear_auto_result | 510 | function | technical_analyzer.py | PRIVATE_HELPER |
| apply_backtest_to_analysis | 553 | function | scanner.py, tests_pipeline_smoke.py, validator.py, cli.py, app.py | KEEP_TEST |
| _fetch_ohlcv_cached | 603 | function | tests_futures_smoke.py, technical_analyzer.py, futures_analyzer.py | PRIVATE_HELPER |
| _source_meta_from_df | 635 | function | technical_analyzer.py, futures_analyzer.py | PRIVATE_HELPER |
| _source_meta_from_results | 650 | function | technical_analyzer.py | PRIVATE_HELPER |
| analyze_symbol_timeframe | 675 | function | app.py, cli.py, technical_analyzer.py, tests_market_type_routing.py | KEEP_TEST |
| _normalize_auto_timeframes | 862 | function | technical_analyzer.py | PRIVATE_HELPER |
| analyze_symbol_auto | 882 | function | scanner.py, tests_pipeline_smoke.py, tests_futures_smoke.py, validator.py, cli.py, app.py | KEEP_TEST |

### tests_app_robustness.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| TestAppRobustness | 18 | class | None | UNUSED_CANDIDATE |
| TestAppRobustness.test_safe_unique_values | 19 | method | None | UNUSED_CANDIDATE |
| TestAppRobustness.test_safe_union_unique | 40 | method | None | UNUSED_CANDIDATE |
| TestAppRobustness.test_ensure_columns | 49 | method | None | UNUSED_CANDIDATE |
| TestAppRobustness.test_legacy_strategy_profile_handling | 58 | method | None | UNUSED_CANDIDATE |

### tests_cli_strategy_report.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| test_cli_strategy_report_help | 5 | function | None | UNUSED_CANDIDATE |
| test_cli_strategy_report_execution | 12 | function | None | UNUSED_CANDIDATE |
| test_cli_strategy_report_output_file | 18 | function | None | UNUSED_CANDIDATE |

### tests_dashboard.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| TestDashboard | 12 | class | None | UNUSED_CANDIDATE |
| TestDashboard.setUp | 13 | method | None | UNUSED_CANDIDATE |
| TestDashboard.test_get_all_signals_sqlite | 19 | method | None | UNUSED_CANDIDATE |
| TestDashboard.test_get_all_signals_csv | 31 | method | None | UNUSED_CANDIDATE |
| TestDashboard.test_metrics_calculation_logic | 38 | method | None | UNUSED_CANDIDATE |
| TestDashboard.test_robustness_missing_columns | 59 | method | None | UNUSED_CANDIDATE |
| TestDashboard.test_union_symbols_robustness | 79 | method | None | UNUSED_CANDIDATE |
| TestDashboard._safe_unique | 89 | method | tests_dashboard.py | PRIVATE_HELPER |
| TestDashboard.test_large_dataset_performance_simulation | 97 | method | None | UNUSED_CANDIDATE |

### tests_exchange_defaults.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| TestExchangeDefaults | 6 | class | None | UNUSED_CANDIDATE |
| TestExchangeDefaults.test_default_exchange_is_binance | 7 | method | None | UNUSED_CANDIDATE |
| TestExchangeDefaults.test_fallback_order | 11 | method | None | UNUSED_CANDIDATE |
| TestExchangeDefaults.test_data_provider_sequence_manual | 15 | method | None | UNUSED_CANDIDATE |
| TestExchangeDefaults.test_data_provider_sequence_fallback | 21 | method | None | UNUSED_CANDIDATE |
| TestExchangeDefaults.test_data_provider_sequence_fallback_respects_priority | 27 | method | None | UNUSED_CANDIDATE |

### tests_futures_smoke.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| PatchSet | 16 | class | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.__init__ | 17 | method | python_internal | PRIVATE_HELPER |
| PatchSet.setattr | 20 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.restore | 24 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| synthetic_ohlcv | 30 | function | tests_futures_smoke.py, tests_strategy_engine.py | KEEP_TEST |
| indicator_frame | 44 | function | tests_strategy_engine.py, tests_futures_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| run_timeframe_case | 98 | function | tests_futures_smoke.py | KEEP_TEST |
| test_long_clear | 129 | function | tests_futures_smoke.py | KEEP_TEST |
| test_short_clear | 142 | function | tests_futures_smoke.py | KEEP_TEST |
| test_neutral_no_setup | 154 | function | tests_futures_smoke.py | KEEP_TEST |
| test_data_unavailable | 160 | function | tests_futures_smoke.py | KEEP_TEST |
| auto_result | 183 | function | tests_futures_smoke.py, futures_analyzer.py | KEEP_TEST |
| test_auto_timeframe_prefers_1h_over_15m_when_similar | 219 | function | tests_futures_smoke.py | KEEP_TEST |
| test_auto_timeframe_allows_15m_only_when_strict_rules_pass | 239 | function | tests_futures_smoke.py | KEEP_TEST |
| test_leverage_defensive | 261 | function | tests_futures_smoke.py | KEEP_TEST |
| test_cli_futures_routes_to_futures_analyzer | 278 | function | tests_futures_smoke.py | KEEP_TEST |
| fake_futures_auto | 282 | function | tests_futures_smoke.py | KEEP_TEST |
| fake_spot | 286 | function | tests_futures_smoke.py | KEEP_TEST |
| run_test | 317 | function | tests_futures_smoke.py, tests_pipeline_smoke.py | KEEP_TEST |
| main | 326 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_market_type_routing.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| PatchSet | 10 | class | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.__init__ | 11 | method | python_internal | PRIVATE_HELPER |
| PatchSet.setattr | 14 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.restore | 18 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| raw_frame | 24 | function | tests_market_type_routing.py | KEEP_TEST |
| indicator_frame | 48 | function | tests_strategy_engine.py, tests_futures_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| FakeExchange | 75 | class | tests_market_type_routing.py | KEEP_TEST |
| FakeExchange.__init__ | 76 | method | python_internal | PRIVATE_HELPER |
| FakeExchange.load_markets | 81 | method | app.py, data_provider.py, paper_trader.py, diagnostics.py | KEEP_UI |
| FakeExchange.fetch_ohlcv | 84 | method | signal_tracker.py, backtester.py, tests_pipeline_smoke.py, diagnostics.py, data_provider.py, paper_trader.py, tests_strategy_engine.py, app.py, technical_analyzer.py | KEEP_TEST |
| spot_markets | 92 | function | tests_market_type_routing.py | KEEP_TEST |
| futures_markets | 105 | function | tests_market_type_routing.py | KEEP_TEST |
| test_spot_analyzer_requests_spot_data | 119 | function | tests_market_type_routing.py | KEEP_TEST |
| fake_fetch | 123 | function | tests_strategy_engine.py, tests_market_type_routing.py | KEEP_TEST |
| test_futures_analyzer_requests_futures_data | 138 | function | tests_market_type_routing.py | KEEP_TEST |
| fake_fetch | 142 | function | tests_strategy_engine.py, tests_market_type_routing.py | KEEP_TEST |
| test_ccxt_like_symbol_routing_spot_and_futures | 158 | function | tests_market_type_routing.py | KEEP_TEST |
| fake_get_exchange | 163 | function | tests_market_type_routing.py | KEEP_TEST |
| test_fallback_keeps_futures_market_type_and_never_fetches_spot | 196 | function | tests_market_type_routing.py | KEEP_TEST |
| fake_get_exchange | 201 | function | tests_market_type_routing.py | KEEP_TEST |
| test_missing_futures_symbol_errors_without_spot_fallback | 226 | function | tests_market_type_routing.py | KEEP_TEST |
| fake_get_exchange | 231 | function | tests_market_type_routing.py | KEEP_TEST |
| main | 257 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_package_project.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| test_packager_excludes_runtime_and_secrets | 6 | function | tests_package_project.py | KEEP_TEST |
| test_secret_assignment_detector_allows_examples | 21 | function | tests_package_project.py | KEEP_TEST |
| main | 26 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_performance_metrics.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| test_normalize_strategy_profile_empty | 5 | function | None | UNUSED_CANDIDATE |
| test_normalize_strategy_profile_legacy | 10 | function | None | UNUSED_CANDIDATE |
| test_calculate_trade_metrics_empty | 16 | function | None | UNUSED_CANDIDATE |
| test_calculate_trade_metrics_basic | 22 | function | None | UNUSED_CANDIDATE |
| test_calculate_strategy_comparison | 38 | function | None | UNUSED_CANDIDATE |
| test_calculate_equity_curve | 60 | function | None | UNUSED_CANDIDATE |

### tests_pipeline_smoke.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| PatchSet | 25 | class | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.__init__ | 26 | method | python_internal | PRIVATE_HELPER |
| PatchSet.setattr | 29 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.restore | 33 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| patched_environment | 40 | function | tests_pipeline_smoke.py | KEEP_TEST |
| fake_backtest | 64 | function | tests_pipeline_smoke.py | KEEP_TEST |
| fake_scan_analysis | 73 | function | tests_pipeline_smoke.py | KEEP_TEST |
| fake_fetch_scan_symbols | 124 | function | tests_pipeline_smoke.py | KEEP_TEST |
| test_scanner_ranks_and_backtest_rows | 141 | function | tests_pipeline_smoke.py | KEEP_TEST |
| write_latest_scan | 187 | function | tests_pipeline_smoke.py | KEEP_TEST |
| test_validator_timeframe_lock | 192 | function | tests_pipeline_smoke.py | KEEP_TEST |
| fake_validator_analysis | 195 | function | tests_pipeline_smoke.py | KEEP_TEST |
| test_validator_data_unavailable_not_avoid | 241 | function | tests_pipeline_smoke.py | KEEP_TEST |
| should_not_call_analyzer | 242 | function | tests_pipeline_smoke.py | KEEP_TEST |
| test_signal_tracker_grouping | 264 | function | tests_pipeline_smoke.py | KEEP_TEST |
| fake_fetch_ohlcv | 294 | function | tests_pipeline_smoke.py | KEEP_TEST |
| run_test | 312 | function | tests_futures_smoke.py, tests_pipeline_smoke.py | KEEP_TEST |
| main | 321 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_storage_sqlite.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| test_sqlite_storage_roundtrip | 14 | function | tests_storage_sqlite.py | KEEP_TEST |
| test_sqlite_storage_concurrent_writers | 73 | function | tests_storage_sqlite.py | KEEP_TEST |
| write_signal | 81 | function | tests_storage_sqlite.py | KEEP_TEST |
| test_sqlite_backend_does_not_write_csv_outputs | 110 | function | tests_storage_sqlite.py | KEEP_TEST |
| main | 172 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_strategy_config.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| TestStrategyConfig | 6 | class | None | UNUSED_CANDIDATE |
| TestStrategyConfig.test_load_existing_profiles | 7 | method | None | UNUSED_CANDIDATE |
| TestStrategyConfig.test_get_strategy_meta | 15 | method | None | UNUSED_CANDIDATE |
| TestStrategyConfig.test_config_structure | 20 | method | None | UNUSED_CANDIDATE |

### tests_strategy_engine.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| PatchSet | 10 | class | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.__init__ | 11 | method | python_internal | PRIVATE_HELPER |
| PatchSet.setattr | 14 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| PatchSet.restore | 18 | method | tests_strategy_engine.py, tests_futures_smoke.py, tests_pipeline_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| synthetic_ohlcv | 24 | function | tests_futures_smoke.py, tests_strategy_engine.py | KEEP_TEST |
| indicator_frame | 38 | function | tests_strategy_engine.py, tests_futures_smoke.py, tests_market_type_routing.py | KEEP_TEST |
| test_strategy_engine_spot_signal | 52 | function | tests_strategy_engine.py | KEEP_TEST |
| test_backtester_routes_to_strategy_engine | 66 | function | tests_strategy_engine.py | KEEP_TEST |
| fake_fetch | 72 | function | tests_strategy_engine.py, tests_market_type_routing.py | KEEP_TEST |
| fake_eval | 78 | function | tests_strategy_engine.py | KEEP_TEST |
| test_backtester_routes_futures_to_strategy_engine | 104 | function | tests_strategy_engine.py | KEEP_TEST |
| fake_fetch | 110 | function | tests_strategy_engine.py, tests_market_type_routing.py | KEEP_TEST |
| fake_eval | 114 | function | tests_strategy_engine.py | KEEP_TEST |
| test_futures_analyzer_delegates_to_strategy_engine | 140 | function | tests_strategy_engine.py | KEEP_TEST |
| fake_eval | 154 | function | tests_strategy_engine.py | KEEP_TEST |
| main | 211 | function | tests_performance_metrics.py, tests_strategy_config.py, tests_pipeline_smoke.py, tests_ui_smoke.py, tests_storage_sqlite.py, tests_futures_smoke.py, import_csv_to_sqlite.py, tests_strategy_engine.py, tests_app_robustness.py, tests_cli_strategy_report.py, paper_cycle.py, cli.py, tests_dashboard.py, package_project.py, tests_exchange_defaults.py, tests_package_project.py, audit_functions.py, tests_market_type_routing.py | KEEP_TEST |

### tests_ui_smoke.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| mock_columns | 7 | function | tests_ui_smoke.py | KEEP_TEST |
| TestUISmoke | 18 | class | None | UNUSED_CANDIDATE |
| TestUISmoke.test_exchange_labels | 19 | method | None | UNUSED_CANDIDATE |
| TestUISmoke.test_exchange_id_from_label | 24 | method | None | UNUSED_CANDIDATE |
| TestUISmoke.test_unique_items | 28 | method | None | UNUSED_CANDIDATE |
| TestUISmoke.test_friendly_error | 33 | method | None | UNUSED_CANDIDATE |

### utils.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| now_utc | 6 | function | scanner.py | KEEP_CORE |
| safe_float | 10 | function | None | UNUSED_CANDIDATE |
| round_value | 22 | function | technical_analyzer.py, strategy_engine.py, futures_analyzer.py | KEEP_CORE |
| format_price | 34 | function | signal_tracker.py, cycle_runner.py, report_builder.py, cli.py, validator.py, app.py, technical_analyzer.py | KEEP_CLI |
| unique_items | 59 | function | scanner.py, app.py, cli.py, report_builder.py | KEEP_CLI |
| clean_optional | 86 | function | storage.py, signal_tracker.py | KEEP_CORE |
| volume_confirmation_text | 95 | function | strategy_engine.py | KEEP_CORE |
| display_timeframe | 107 | function | report_builder.py, cli.py, technical_analyzer.py | KEEP_CLI |
| entry_now_display | 115 | function | report_builder.py, cli.py | KEEP_CLI |

### validator.py
| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |
|---|---:|---|---|---|
| _generate_markdown | 13 | function | validator.py, signal_tracker.py | PRIVATE_HELPER |
| add_table | 41 | function | validator.py, signal_tracker.py | KEEP_CORE |
| run_validation | 69 | function | app.py, cli.py, cycle_runner.py, tests_pipeline_smoke.py | KEEP_TEST |
