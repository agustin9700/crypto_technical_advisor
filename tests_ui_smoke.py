import unittest
import sys
from unittest.mock import MagicMock

# Mock streamlit before import app
mock_st = MagicMock()
def mock_columns(spec, **kwargs):
    if isinstance(spec, list): return [MagicMock() for _ in spec]
    if isinstance(spec, int): return [MagicMock() for _ in range(spec)]
    return [MagicMock(), MagicMock()]
mock_st.columns.side_effect = mock_columns
mock_st.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
mock_st.button.return_value = False
sys.modules["streamlit"] = mock_st

import app

class TestUISmoke(unittest.TestCase):
    def test_exchange_labels(self):
        self.assertEqual(app._exchange_label("binance"), "Binance")
        self.assertEqual(app._exchange_label("kucoin"), "KuCoin")
        self.assertEqual(app._exchange_label("unknown"), "unknown")

    def test_exchange_id_from_label(self):
        self.assertEqual(app._exchange_id_from_label("Binance"), "binance")
        self.assertEqual(app._exchange_id_from_label("KuCoin"), "kucoin")

    def test_unique_items(self):
        items = ["razones:", "  ", "Buy", "Buy", "Sell", None, "Condiciones faltantes:"]
        cleaned = app._unique_items(items)
        self.assertEqual(cleaned, ["Buy", "Sell"])

    def test_friendly_error(self):
        err = Exception("binance error timeout")
        msg = app._friendly_error(err, "General error")
        self.assertIn("No se pudo consultar Binance", msg)

if __name__ == "__main__":
    unittest.main()
