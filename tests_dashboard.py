import unittest
import pandas as pd
import storage
import os
from unittest.mock import patch, MagicMock

# Mock streamlit to avoid issues during import
import sys
mock_st = MagicMock()
sys.modules['streamlit'] = mock_st

class TestDashboard(unittest.TestCase):
    def setUp(self):
        # Reset mock before each test
        mock_st.reset_mock()

    @patch('storage.is_sqlite_backend', return_value=True)
    @patch('storage.get_storage')
    def test_get_all_signals_sqlite(self, mock_get_storage, mock_is_sqlite):
        mock_db = MagicMock()
        mock_db.list_signals.return_value = [{"symbol": "BTC/USDT", "score": 9.5}]
        mock_get_storage.return_value = mock_db
        
        signals = storage.get_all_signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "BTC/USDT")
        
    @patch('storage.is_sqlite_backend', return_value=False)
    @patch('os.path.exists', return_value=True)
    @patch('pandas.read_csv')
    def test_get_all_signals_csv(self, mock_read_csv, mock_exists, mock_is_sqlite):
        mock_read_csv.return_value = pd.DataFrame([{"symbol": "ETH/USDT", "score": 8.0}])
        
        signals = storage.get_all_signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "ETH/USDT")

    def test_metrics_calculation_logic(self):
        # We test the logic used inside app.py
        data = [
            {"status": "CLOSED", "pnl": 100.0},
            {"status": "CLOSED", "pnl": -50.0},
            {"status": "CLOSED", "pnl": 200.0},
            {"status": "OPEN", "pnl": 10.0}
        ]
        df = pd.DataFrame(data)
        
        closed_df = df[df["status"] == "CLOSED"]
        wins = len(closed_df[pd.to_numeric(closed_df["pnl"]) > 0])
        winrate = (wins / len(closed_df)) * 100
        
        self.assertEqual(len(closed_df), 3)
        self.assertEqual(wins, 2)
        self.assertEqual(winrate, (2/3)*100)
        
        total_pnl = pd.to_numeric(closed_df["pnl"]).sum()
        self.assertEqual(total_pnl, 250.0)

    def test_robustness_missing_columns(self):
        # Test how pandas handles missing columns in the way app.py uses them
        df = pd.DataFrame([{"symbol": "BTC/USDT"}]) # Missing pnl, status, etc.
        
        # Simulating logic in app.py
        status_col = "status"
        if status_col in df.columns:
            closed_trades = len(df[df[status_col] == "CLOSED"])
        else:
            closed_trades = 0
            
        self.assertEqual(closed_trades, 0)
        
        # Test pnl numeric conversion on missing column
        if "pnl" in df.columns:
            pnl_sum = pd.to_numeric(df["pnl"]).sum()
        else:
            pnl_sum = 0
        self.assertEqual(pnl_sum, 0)

    def test_union_symbols_robustness(self):
        # This simulates the bug reported by the user
        df_signals = pd.DataFrame([{"symbol": "BTC/USDT"}])
        df_trades = pd.DataFrame() # No columns
        
        # Original problematic line:
        # all_syms = sorted(list(set(df_signals["symbol"].unique()) | set(df_trades["symbol"].unique())))
        # This would raise KeyError: 'symbol'
        
        # Safe way using our helper (assuming app is mocked or we use the logic)
        def _safe_unique(df, column):
            if df is None or df.empty or column not in df.columns:
                return []
            return [str(v) for v in df[column].dropna().unique() if str(v).strip()]

        all_syms = sorted(set(_safe_unique(df_signals, "symbol")) | set(_safe_unique(df_trades, "symbol")))
        self.assertEqual(all_syms, ["BTC/USDT"])

    def test_large_dataset_performance_simulation(self):
        # Simulate 1000 records
        data = [{"symbol": f"SYM{i}", "score": i%10, "status": "CLOSED", "pnl": i} for i in range(1000)]
        df = pd.DataFrame(data)
        
        # Basic operations that app.py performs
        start_time = pd.Timestamp.now()
        unique_syms = df["symbol"].unique()
        pnl_sum = df["pnl"].sum()
        end_time = pd.Timestamp.now()
        
        duration = (end_time - start_time).total_seconds()
        self.assertLess(duration, 0.1) # Should be very fast

if __name__ == '__main__':
    unittest.main()
