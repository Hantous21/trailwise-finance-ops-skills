"""Dependency-free critical-path and delay-impact analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace
from heapq import heappop, heappush


@dataclass(frozen=True)
class Activity:
    activity_id: str
    duration_days: int
    predecessors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.activity_id.strip():
            raise ValueError("activity_id is required")
        if self.duration_days < 0:
            raise ValueError("duration_days cannot be negative")
        if self.activity_id in self.predecessors:
            raise ValueError("an activity cannot depend on itself")
        if len(set(self.predecessors)) != len(self.predecessors):
            raise ValueError("duplicate predecessors are not allowed")


def analyze(activities: list[Activity]) -> dict[str, object]:
    """Calculate CPM dates using day zero and finish-to-start relationships."""
    if not activities:
        raise ValueError("at least one activity is required")
    by_id = {activity.activity_id: activity for activity in activities}
    if len(by_id) != len(activities):
        raise ValueError("activity IDs must be unique")
    missing = sorted({pred for activity in activities for pred in activity.predecessors if pred not in by_id})
    if missing:
        raise ValueError(f"missing predecessor activities: {', '.join(missing)}")

    successors: dict[str, list[str]] = {activity_id: [] for activity_id in by_id}
    indegree = {activity_id: len(activity.predecessors) for activity_id, activity in by_id.items()}
    for activity in activities:
        for predecessor in activity.predecessors:
            successors[predecessor].append(activity.activity_id)

    ready: list[str] = []
    for activity_id, degree in indegree.items():
        if degree == 0:
            heappush(ready, activity_id)
    order: list[str] = []
    while ready:
        activity_id = heappop(ready)
        order.append(activity_id)
        for successor in sorted(successors[activity_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heappush(ready, successor)
    if len(order) != len(activities):
        raise ValueError("schedule contains a dependency cycle")

    early_start: dict[str, int] = {}
    early_finish: dict[str, int] = {}
    for activity_id in order:
        activity = by_id[activity_id]
        early_start[activity_id] = max((early_finish[p] for p in activity.predecessors), default=0)
        early_finish[activity_id] = early_start[activity_id] + activity.duration_days
    project_duration = max(early_finish.values())

    late_finish: dict[str, int] = {}
    late_start: dict[str, int] = {}
    for activity_id in reversed(order):
        activity = by_id[activity_id]
        late_finish[activity_id] = min((late_start[s] for s in successors[activity_id]), default=project_duration)
        late_start[activity_id] = late_finish[activity_id] - activity.duration_days

    rows = []
    for activity_id in order:
        total_float = late_start[activity_id] - early_start[activity_id]
        rows.append({
            "activity_id": activity_id,
            "duration_days": by_id[activity_id].duration_days,
            "early_start": early_start[activity_id],
            "early_finish": early_finish[activity_id],
            "late_start": late_start[activity_id],
            "late_finish": late_finish[activity_id],
            "total_float": total_float,
            "critical": total_float == 0,
        })
    return {
        "project_duration_days": project_duration,
        "critical_path": [row["activity_id"] for row in rows if row["critical"]],
        "activities": rows,
    }


def simulate_delay(activities: list[Activity], activity_id: str, delay_days: int) -> dict[str, object]:
    """Model a delay as added duration and compare it with the baseline schedule."""
    if delay_days < 0:
        raise ValueError("delay_days cannot be negative")
    if activity_id not in {activity.activity_id for activity in activities}:
        raise ValueError(f"unknown activity: {activity_id}")
    baseline = analyze(activities)
    adjusted = [
        replace(activity, duration_days=activity.duration_days + delay_days)
        if activity.activity_id == activity_id else activity
        for activity in activities
    ]
    scenario = analyze(adjusted)
    impact = int(scenario["project_duration_days"]) - int(baseline["project_duration_days"])
    return {
        "activity_id": activity_id,
        "input_delay_days": delay_days,
        "baseline_duration_days": baseline["project_duration_days"],
        "adjusted_duration_days": scenario["project_duration_days"],
        "project_impact_days": impact,
        "absorbed_by_float_days": delay_days - impact,
        "baseline_critical_path": baseline["critical_path"],
        "adjusted_critical_path": scenario["critical_path"],
    }
