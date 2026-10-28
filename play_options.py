"""Optional app rules, separate from the frozen autonomous AI benchmark."""
from backend import bridge


def neues_spiel(flughafen="MUC", karten_json="[]", timed=True):
    if type(timed) is not bool:
        raise ValueError("Zeitlimit muss ein Wahrheitswert sein.")
    bridge.neues_spiel(flughafen, karten_json)
    if not timed:
        # Removing the module also disables future deadlines after round end,
        # save/resume and undo. The rest of the route and its cards stay intact.
        bridge._spiel.cockpit.module.discard("realtime")
        bridge._spiel.zusatz.deadline = None
    return bridge.zustand()
