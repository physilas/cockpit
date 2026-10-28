"""Optional app rules, separate from the frozen autonomous AI benchmark."""
from backend import bridge


def neues_spiel(flughafen="MUC", karten_json="[]", timed=True, briefing=False):
    if type(timed) is not bool:
        raise ValueError("Zeitlimit muss ein Wahrheitswert sein.")
    if type(briefing) is not bool:
        raise ValueError("Absprache muss ein Wahrheitswert sein.")
    if briefing:
        import json
        from backend.spielplan import Spielplan
        game = Spielplan(flughafen, faehigkeitskarten=json.loads(karten_json))
        game._sammle_neuwurf_plaettchen()
        game._bereite_runde_vor()
        bridge._spiel = game
        bridge._verlauf.clear()
        bridge._revision += 1
        bridge._undo_id += 1
    else:
        bridge.neues_spiel(flughafen, karten_json)
    if not timed:
        # Removing the module also disables future deadlines after round end,
        # save/resume and undo. The rest of the route and its cards stay intact.
        bridge._spiel.cockpit.module.discard("realtime")
        bridge._spiel.zusatz.deadline = None
    return bridge.zustand()
