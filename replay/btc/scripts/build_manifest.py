import json
from pathlib import Path


SCENARIOS_ROOT = Path(__file__).resolve().parent.parent / "scenarios"


def main():
    entries = []
    for meta_path in sorted(SCENARIOS_ROOT.glob("*/meta.json")):
        with meta_path.open("r", encoding="utf-8") as handle:
            meta = json.load(handle)
        entries.append(
            {
                "scenario_id": meta["scenario_id"],
                "title": meta["title"],
                "path": str(meta_path.parent.relative_to(SCENARIOS_ROOT)),
            }
        )

    manifest_path = SCENARIOS_ROOT / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump({"scenarios": entries}, handle, indent=2, ensure_ascii=False)
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
