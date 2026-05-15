import os
import unittest
import config
import data_provider

class TestExchangeDefaults(unittest.TestCase):
    def test_default_exchange_is_binance(self):
        # Verifica que el default en config sea binance
        self.assertEqual(config.DEFAULT_EXCHANGE, "binance")

    def test_fallback_order(self):
        # Verifica que la prioridad sea [binance, kucoin]
        self.assertEqual(config.EXCHANGE_PRIORITY, ["binance", "kucoin"])

    def test_data_provider_sequence_manual(self):
        # En modo manual, solo debe devolver el seleccionado
        seq, mode = data_provider._exchange_sequence(exchange_id="kucoin", exchange_mode="manual")
        self.assertEqual(seq, ["kucoin"])
        self.assertEqual(mode, "manual")

    def test_data_provider_sequence_fallback(self):
        # En modo fallback, debe seguir la prioridad
        seq, mode = data_provider._exchange_sequence(exchange_mode="fallback")
        self.assertEqual(seq, ["binance", "kucoin"])
        self.assertEqual(mode, "fallback")

    def test_data_provider_sequence_fallback_respects_priority(self):
        # Si se pasa una prioridad personalizada, debe respetarla
        custom_priority = ["kucoin", "binance"]
        seq, mode = data_provider._exchange_sequence(exchange_mode="fallback", exchange_priority=custom_priority)
        self.assertEqual(seq, ["kucoin", "binance"])

if __name__ == "__main__":
    unittest.main()
