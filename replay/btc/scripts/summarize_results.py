import json
import sys
from pathlib import Path


def main():
    result_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("replay/btc/outputs/runs/2022-11-11_ftx_collapse/result.json")
    with result_path.open("r", encoding="utf-8") as handle:
        result = json.load(handle)

    selected = 0
    for signal in result["signals"]:
        selected += sum(1 for simulation in signal["simulations"] if simulation["selected"] == 1)

    print(
        f"scenario={result['scenario_id']} "
        f"signals={result['signal_count']} "
        f"selected_simulations={selected}"
    )


if __name__ == "__main__":
    main()
