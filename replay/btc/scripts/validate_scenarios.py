import json
from pathlib import Path


SCENARIOS_ROOT = Path(__file__).resolve().parent.parent / "scenarios"


def main():
    errors = []
    for meta_path in sorted(SCENARIOS_ROOT.glob("*/meta.json")):
        scenario_dir = meta_path.parent
        headlines_path = scenario_dir / "headlines.jsonl"
        if not headlines_path.exists():
            errors.append(f"missing headlines.jsonl for {scenario_dir.name}")
            continue
        with meta_path.open("r", encoding="utf-8") as handle:
            json.load(handle)

    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print("scenario validation ok")


if __name__ == "__main__":
    main()
