"""Play a terminal game with your checkpoint while the AI hand stays hidden."""
import argparse
from pathlib import Path

from .actions import ACTIONS, SLOTS
from .agents import HeuristicAgent, ModelAgent
from .environment import CrewEnv


def show_board(view):
    print(f"\nRunde {view['round']} | Höhe {view['height']} | Entfernung {view['distance']} | "
          f"Fluglage {view['attitude']:+d} | Kaffee {view['coffee']} | Neuwürfe {view['reroll_tokens']}")
    print("Deine Würfel: " + ", ".join(f"{i + 1}={value}" for i, value in enumerate(view["own_dice"]) if value))
    print(f"Partner: {view['partner_remaining']} verdeckte Würfel")
    print("Verkehr: " + ", ".join(f"Entf. {c['distance']}: {c['planes']}" for c in view["track"]))
    print("Fortschritt: Fahrwerk", view["gear"], "| Klappen", view["flaps"], "| Bremsen", view["brake_progress"])
    print("Belegt: " + "; ".join(f"{slot.label}={field['value']}" for slot, field in zip(SLOTS, view["board"]) if field))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkpoint", type=Path)
    source.add_argument("--baseline", choices=("heuristic",))
    parser.add_argument("--role", choices=("pilot", "kopilot"), default="pilot", help="Deine Rolle")
    parser.add_argument("--airport", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--stochastic", action="store_true")
    args = parser.parse_args()
    config = {}
    if args.checkpoint:
        import torch
        from .checkpoints import load_checkpoint
        torch.set_num_threads(1)
        model, payload = load_checkpoint(args.checkpoint)
        config = payload.get("train_config", {})
        agent = ModelAgent(model, deterministic=not args.stochastic)
    else:
        agent = HeuristicAgent()
    import secrets
    env = CrewEnv(args.airport or config.get("airport", "MUC"), max_steps=config.get("max_steps", 256))
    _, info = env.reset(seed=args.seed if args.seed is not None else secrets.randbits(64))
    print(f"Du spielst {args.role}. Aktionsnummer eingeben; q beendet die Partie.")
    try:
        while not env.done:
            if env.current_role == args.role:
                show_board(env.view(args.role))
                for i, valid in enumerate(info["action_mask"]):
                    if valid:
                        print(f"  {i:3d}: {ACTIONS[i].label()}")
                while True:
                    raw = input("Aktion: ").strip()
                    if raw.lower() in ("q", "quit", "exit"):
                        return
                    try:
                        selected = int(raw)
                    except ValueError:
                        continue
                    if 0 <= selected < len(ACTIONS) and info["action_mask"][selected]:
                        break
                    print("Bitte eine der angezeigten Aktionsnummern eingeben.")
            else:
                selected = agent.select(env.view(), info["action_mask"])
                action = ACTIONS[selected]
                suffix = f" [Wert {env.view()['own_dice'][action.die]}]" if action.kind == "place" else ""
                print(f"KI: {action.label()}{suffix}")
            _, _, _, _, info = env.step(selected)
    except (KeyboardInterrupt, EOFError):
        print("\nPartie beendet.")
        return
    show_board(env.view(args.role))
    print(f"\nErgebnis: {info['status']}; Grund: {info['reason'] or 'sicher gelandet'}")


if __name__ == "__main__":
    main()
