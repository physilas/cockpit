"""Validation objective, independent of shaped returns and PPO losses."""
from statistics import mean

OBJECTIVE_VERSION = 1


def evaluation_score(result, *, initial_distance, initial_tasks):
    """One extra win always beats every possible progress tie-break combined.

    All trials must use the same number of validation games. Progress requires
    navigation AND completed preparations; staying put gives zero credit even
    with every preparation complete. Truncated episodes give no progress credit.
    This is only a selection criterion, never a training reward or a win claim.
    """
    if initial_distance <= 0 or initial_tasks <= 0:
        raise ValueError("Die Strecke braucht positive Anfangsentfernung und Aufgabenanzahl.")
    records = result["episodes"]
    if not records or len(records) != result["games"]:
        raise ValueError("Die Bewertung braucht alle Validierungspartien.")
    progress = []
    for record in records:
        navigation = 1 - min(1.0, max(0.0, record["distance_remaining"] / initial_distance))
        preparation = 1 - min(1.0, max(0.0, record["tasks_undone"] / initial_tasks))
        progress.append(navigation * preparation if record["status"] != "truncated" else 0.0)
    wins = sum(record["status"] == "gewonnen" for record in records)
    return {"objective": wins + 0.49 * mean(progress), "progress": mean(progress), "wins": wins,
            "games": len(records), "win_rate": wins / len(records)}
