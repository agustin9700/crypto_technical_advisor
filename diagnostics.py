import platform
import sys
import traceback

import ccxt
import requests

import config


def _runtime_info() -> dict:
    return {
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "ccxt_version": getattr(ccxt, "__version__", "unknown"),
    }


def _row(
    test_name: str,
    status: str,
    http_status_code=None,
    error_type: str = "",
    error_message: str = "",
    response_preview: str = "",
) -> dict:
    info = _runtime_info()
    return {
        "test_name": test_name,
        "status": status,
        "http_status_code": http_status_code,
        "error_type": error_type,
        "error_message": error_message,
        "response_preview": response_preview,
        "python_version": info["python_version"],
        "platform": info["platform"],
        "ccxt_version": info["ccxt_version"],
    }


def _request_test(test_name: str, url: str) -> dict:
    try:
        response = requests.get(url, timeout=10)
        body = response.text or ""
        if 200 <= response.status_code < 300:
            preview = body if test_name == "Public IP" else body[:500]
            return _row(
                test_name,
                "OK",
                response.status_code,
                response_preview=preview,
            )
        return _row(
            test_name,
            "FAIL",
            response.status_code,
            error_type=f"HTTP_{response.status_code}",
            error_message=body,
            response_preview=body,
        )
    except Exception as exc:
        return _row(
            test_name,
            "FAIL",
            error_type=type(exc).__name__,
            error_message=traceback.format_exc(),
            response_preview=str(exc),
        )


def _ccxt_test(test_name: str, action) -> dict:
    try:
        result = action()
        message = "OK"
        preview = "OK"
        if isinstance(result, dict) and "symbol" in result:
            preview = str({
                "symbol": result.get("symbol"),
                "last": result.get("last"),
                "datetime": result.get("datetime"),
            })
        if isinstance(result, list):
            message = f"{len(result)} rows"
            preview = message
        return _row(test_name, "OK", error_message=message, response_preview=preview)
    except Exception as exc:
        return _row(
            test_name,
            "FAIL",
            error_type=type(exc).__name__,
            error_message=traceback.format_exc(),
            response_preview=str(exc),
        )


def run_binance_diagnostics() -> list:
    tests = [
        _request_test("Public IP", "https://api.ipify.org?format=json"),
        _request_test("Binance time", "https://api.binance.com/api/v3/time"),
        _request_test("Binance exchangeInfo", "https://api.binance.com/api/v3/exchangeInfo"),
    ]

    exchange = ccxt.binance({"enableRateLimit": True})
    tests.extend([
        _ccxt_test("CCXT load_markets", exchange.load_markets),
        _ccxt_test("CCXT fetch_ticker BTC/USDT", lambda: exchange.fetch_ticker("BTC/USDT")),
        _ccxt_test(
            "CCXT fetch_ohlcv BTC/USDT 1h",
            lambda: exchange.fetch_ohlcv("BTC/USDT", "1h", limit=10),
        ),
    ])
    return tests


def _exchange_row(exchange_id: str, load_markets: str, ticker: str, ohlcv: str, error: str = "") -> dict:
    return {
        "exchange": exchange_id,
        "load_markets": load_markets,
        "ticker": ticker,
        "ohlcv": ohlcv,
        "error": error,
    }


def run_exchange_diagnostics(exchange_priority=None) -> list:
    rows = []
    for exchange_id in list(exchange_priority or config.EXCHANGE_PRIORITY):
        load_status = "FAIL"
        ticker_status = "FAIL"
        ohlcv_status = "FAIL"
        errors = []

        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
        except Exception as exc:
            rows.append(_exchange_row(
                exchange_id,
                load_status,
                ticker_status,
                ohlcv_status,
                traceback.format_exc() or str(exc),
            ))
            continue

        try:
            exchange.load_markets()
            load_status = "OK"
        except Exception as exc:
            errors.append(f"load_markets {type(exc).__name__}: {exc}")
            rows.append(_exchange_row(
                exchange_id,
                load_status,
                ticker_status,
                ohlcv_status,
                " | ".join(errors),
            ))
            continue

        try:
            exchange.fetch_ticker("BTC/USDT")
            ticker_status = "OK"
        except Exception as exc:
            errors.append(f"ticker {type(exc).__name__}: {exc}")

        try:
            exchange.fetch_ohlcv("BTC/USDT", "1h", limit=10)
            ohlcv_status = "OK"
        except Exception as exc:
            errors.append(f"ohlcv {type(exc).__name__}: {exc}")

        rows.append(_exchange_row(
            exchange_id,
            load_status,
            ticker_status,
            ohlcv_status,
            " | ".join(errors),
        ))
    return rows
