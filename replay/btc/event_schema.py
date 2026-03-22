from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScenarioMeta:
    scenario_id: str
    title: str
    description: str
    start_utc: str
    end_utc: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ReplaySignal:
    timestamp_utc: str
    state: str
    direction: str
    price_now: float
    move_1m: float | None
    move_3m: float | None
    move_5m: float | None
    up_score: int
    down_score: int
    trend_state: str | None = None
    range_position: str | None = None
    volatility_state: str | None = None
    skip_candidate: bool | None = None
    selected_model: str | None = None


@dataclass
class ReplaySimulation:
    model: str
    signal_state: str
    signal_direction: str
    trade_direction: str
    entry_price: float
    checkpoints: dict[int, dict[str, float]]
    selected: int
