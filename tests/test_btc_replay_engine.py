import tempfile
import unittest
from pathlib import Path

from replay.btc.replay_engine import run_replay


class BTCReplayEngineTest(unittest.TestCase):
    def test_run_replay_writes_result_under_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = run_replay("2022-11-11_ftx_collapse", output_dir=output_dir)
            self.assertEqual(result["scenario_id"], "2022-11-11_ftx_collapse")
            self.assertTrue((output_dir / "result.json").exists())
            self.assertGreaterEqual(result["signal_count"], 1)


if __name__ == "__main__":
    unittest.main()
