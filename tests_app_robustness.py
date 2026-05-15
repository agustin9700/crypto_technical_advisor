import unittest
import pandas as pd
import sys
import datetime
from unittest.mock import MagicMock

# Mock streamlit before importing app
mock_st = MagicMock()
mock_st.columns.side_effect = lambda n: [MagicMock()] * (n if isinstance(n, int) else len(n))
mock_st.tabs.side_effect = lambda titles: [MagicMock()] * len(titles)
mock_st.date_input.return_value = [datetime.date.today(), datetime.date.today()]
mock_st.button.return_value = False
mock_st.checkbox.return_value = False
sys.modules['streamlit'] = mock_st

import app

class TestAppRobustness(unittest.TestCase):
    def test_safe_unique_values(self):
        # Case 1: None
        self.assertEqual(app.safe_unique_values(None, "symbol"), [])
        
        # Case 2: Empty DF
        df_empty = pd.DataFrame()
        self.assertEqual(app.safe_unique_values(df_empty, "symbol"), [])
        
        # Case 3: Column missing
        df_no_col = pd.DataFrame({"other": [1, 2]})
        self.assertEqual(app.safe_unique_values(df_no_col, "symbol"), [])
        
        # Case 4: Normal data
        df_ok = pd.DataFrame({"symbol": ["BTC", "ETH", None, "BTC", " "]})
        # BTC, ETH, " " (but strip check might remove empty strings depending on implementation)
        # result = [" ", "BTC", "ETH"] or ["BTC", "ETH"]
        res = app.safe_unique_values(df_ok, "symbol")
        self.assertIn("BTC", res)
        self.assertIn("ETH", res)
        self.assertNotIn(None, res)

    def test_safe_union_unique(self):
        df_a = pd.DataFrame({"symbol": ["BTC", "ETH"]})
        df_b = pd.DataFrame({"symbol": ["BTC", "XRP"]})
        res = app.safe_union_unique(df_a, df_b, "symbol")
        self.assertEqual(res, ["BTC", "ETH", "XRP"])
        
        # One empty
        self.assertEqual(app.safe_union_unique(df_a, None, "symbol"), ["BTC", "ETH"])

    def test_ensure_columns(self):
        df = pd.DataFrame({"a": [1]})
        cols = ["a", "b", "c"]
        res = app.ensure_columns(df, cols)
        self.assertIn("a", res.columns)
        self.assertIn("b", res.columns)
        self.assertIn("c", res.columns)
        self.assertEqual(res["b"].iloc[0], None)

    def test_legacy_strategy_profile_handling(self):
        # Simulating logic in app.py
        df = pd.DataFrame({"other": [1]})
        df = app.ensure_columns(df, ["strategy_profile"])
        df["strategy_profile"] = df["strategy_profile"].fillna("legacy")
        self.assertEqual(df["strategy_profile"].iloc[0], "legacy")

if __name__ == '__main__':
    unittest.main()
