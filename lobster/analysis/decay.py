from dataclasses import dataclass
from lobster.analysis.health import HealthReport
from lobster.storage.db import save_snapshot, get_last_snapshot


@dataclass
class DecaySignal:
    metric: str
    previous: float | int
    current: float | int
    delta_pct: float
    direction: str   # "up" | "down" | "stable"
    severity: str    # "watch" | "warn" | "ok"
    message: str


def _pct_change(prev: float, curr: float) -> float:
    if prev == 0:
        return 0.0
    return (curr - prev) / prev * 100


def _direction(delta: float, threshold: float = 2.0) -> str:
    if delta > threshold:
        return "up"
    if delta < -threshold:
        return "down"
    return "stable"


def _severity(metric: str, direction: str) -> str:
    # metrics where "down" is bad
    bad_when_down = {"weekly_downloads", "stars", "so_answer_rate", "score"}
    # metrics where "up" is bad
    bad_when_up = {"open_issues", "last_commit_days_ago"}

    if metric in bad_when_down and direction == "down":
        return "warn"
    if metric in bad_when_up and direction == "up":
        return "watch"
    return "ok"


def compute_decay(current: HealthReport) -> list[DecaySignal]:
    snapshot = get_last_snapshot(current.library)
    if snapshot is None:
        return []

    prev = snapshot["report"]
    captured_at = snapshot["captured_at"]
    signals = []

    checks = [
        ("score", "Health score", current.score, prev.get("score", current.score)),
        ("weekly_downloads", "Weekly downloads", current.weekly_downloads, prev.get("weekly_downloads", current.weekly_downloads)),
        ("stars", "GitHub stars", current.stars, prev.get("stars", current.stars)),
        ("open_issues", "Open issues", current.open_issues, prev.get("open_issues", current.open_issues)),
        ("so_answer_rate", "SO answer rate", current.so_answer_rate, prev.get("so_answer_rate", current.so_answer_rate)),
        ("last_commit_days_ago", "Last commit age", current.last_commit_days_ago or 0, prev.get("last_commit_days_ago") or 0),
    ]

    for key, label, curr_val, prev_val in checks:
        delta = _pct_change(prev_val, curr_val)
        direction = _direction(delta)
        if direction == "stable":
            continue
        severity = _severity(key, direction)
        arrow = "↑" if direction == "up" else "↓"
        signals.append(DecaySignal(
            metric=key,
            previous=prev_val,
            current=curr_val,
            delta_pct=delta,
            direction=direction,
            severity=severity,
            message=f"{label} {arrow} {abs(delta):.1f}% since {captured_at[:10]} ({prev_val:,} → {curr_val:,})",
        ))

    return signals


def persist_snapshot(report: HealthReport):
    from dataclasses import asdict
    save_snapshot(report.library, asdict(report))
