"""Read committed training logs in the order selected for notebook analysis."""
from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math


def number(row, key):
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return float("nan")


def read_csv(path):
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                # A training process may currently be writing the final row.
                if None not in row and None not in row.values():
                    yield row


@dataclass
class RunData:
    name: str
    directory: Path
    config: dict
    metrics: list
    episodes: list
    start_step: float
    end_step: float


def load_runs(root, names):
    """Keep cumulative counters; append reset counters after the preceding run.

    Original CSV counters stay intact. ``plot_steps`` is the shared plot axis,
    and ``run_name`` disambiguates updates/seeds repeated in different runs.
    """
    names = [names] if isinstance(names, str) else list(names)
    if not names:
        raise ValueError("RUN_NAMES muss mindestens einen Lauf enthalten.")
    if len(set(names)) != len(names):
        raise ValueError("Jeden Lauf nur einmal in RUN_NAMES angeben.")

    runs = []
    for name in names:
        directory = Path(root) / "runs" / name
        config_path = directory / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        if runs and config.get("airport", "MUC") != runs[0].config.get("airport", "MUC"):
            raise ValueError("Für eine gemeinsame Analyse müssen alle Runs dieselbe Strecke verwenden.")
        metrics = [row for row in read_csv(directory / "metrics.csv")
                   if number(row, "update").is_integer() and number(row, "update") > 0
                   and math.isfinite(number(row, "total_steps")) and number(row, "total_steps") >= 0]
        if not metrics:
            raise RuntimeError(f"Keine vollständigen Metriken unter {directory}. RUN_NAMES prüfen oder Training starten.")
        steps = [number(row, "total_steps") for row in metrics]
        updates = [int(row["update"]) for row in metrics]
        if any(b <= a for a, b in zip(steps, steps[1:])) or any(b <= a for a, b in zip(updates, updates[1:])):
            raise ValueError(f"Schritte und Updates müssen innerhalb von {name} streng ansteigen.")

        # config.json can describe a later resume in the same directory. Its
        # origin then lies after the first logged update and must be ignored.
        origin = number(config, "resumed_from_steps")
        if not math.isfinite(origin) or not 0 <= origin < steps[0]:
            origin = 0.0
        offset = runs[-1].end_step - origin if runs and steps[0] <= runs[-1].end_step else 0.0
        start_step = runs[-1].end_step if runs else origin
        for row, step in zip(metrics, steps):
            row.update(run_name=name, plot_steps=step + offset)

        committed = {int(row["update"]): number(row, "total_steps") for row in metrics}
        episodes_by_key = {}
        for row in read_csv(directory / "episodes.csv"):
            update = number(row, "update")
            if (not update.is_integer() or update not in committed
                    or number(row, "total_steps") != committed[update]
                    or row.get("phase") not in ("train", "eval")
                    or not row.get("status") or not row.get("seed") or not row.get("ai_role")
                    or not number(row, "round").is_integer()
                    or not number(row, "steps").is_integer()
                    or not math.isfinite(number(row, "return"))):
                continue
            row.update(run_name=name, plot_steps=number(row, "total_steps") + offset)
            key = (row["phase"], int(update), row["seed"], row["ai_role"])
            episodes_by_key[key] = row
        episodes = sorted(episodes_by_key.values(), key=lambda row: int(row["update"]))
        runs.append(RunData(name, directory, config, metrics, episodes, start_step, steps[-1] + offset))
    return runs
