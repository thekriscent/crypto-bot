from pathlib import Path

from replay.shared.utils import read_json, read_jsonl


BTC_REPLAY_ROOT = Path(__file__).resolve().parent
SCENARIOS_ROOT = BTC_REPLAY_ROOT / "scenarios"
OUTPUTS_ROOT = BTC_REPLAY_ROOT / "outputs"
MANIFEST_PATH = SCENARIOS_ROOT / "manifest.json"


def load_manifest():
    return read_json(MANIFEST_PATH)


def scenario_dir(scenario_id: str) -> Path:
    return SCENARIOS_ROOT / scenario_id


def load_scenario_meta(scenario_id: str):
    return read_json(scenario_dir(scenario_id) / "meta.json")


def load_scenario_headlines(scenario_id: str):
    return read_jsonl(scenario_dir(scenario_id) / "headlines.jsonl")


def ensure_output_dir(run_name: str) -> Path:
    output_dir = OUTPUTS_ROOT / "runs" / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
