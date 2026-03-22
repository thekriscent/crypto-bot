from pathlib import Path
import sys

from replay.btc.replay_engine import run_replay


def main():
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "2022-11-11_ftx_collapse"
    result = run_replay(scenario_id, output_dir=Path("replay/btc/outputs/runs") / scenario_id)
    print(f"scenario={scenario_id} signal_count={result['signal_count']}")


if __name__ == "__main__":
    main()
