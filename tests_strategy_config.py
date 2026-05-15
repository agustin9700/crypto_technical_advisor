import os
import json
import unittest
from strategy_config import load_strategy_profile, get_strategy_meta

class TestStrategyConfig(unittest.TestCase):
    def test_load_existing_profiles(self):
        profiles = ["conservative", "balanced", "aggressive", "scalping", "swing"]
        for p in profiles:
            config = load_strategy_profile(p)
            self.assertIsNotNone(config, f"Should load profile {p}")
            self.assertIn("name", config)
            self.assertEqual(config["name"].lower(), p.lower())
            
    def test_get_strategy_meta(self):
        meta = get_strategy_meta("aggressive")
        self.assertEqual(meta["strategy_profile"], "aggressive")
        self.assertIn("strategy_version", meta)
        
    def test_config_structure(self):
        # The actual JSONs have these fields at root, not nested
        config = load_strategy_profile("aggressive")
        self.assertIn("min_score_enter", config)
        self.assertIn("rsi_overbought", config)
        self.assertIn("atr_stop_loss_mult", config)
        self.assertIn("risk_reward_min", config)

if __name__ == "__main__":
    unittest.main()
