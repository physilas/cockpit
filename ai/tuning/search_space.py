"""Small, editable search space. Keep reward shaping fixed within one study."""

ARCHITECTURES = {
    "2x128": {"hidden_size": 128, "hidden_layers": 2},
    "2x256": {"hidden_size": 256, "hidden_layers": 2},
    "3x256": {"hidden_size": 256, "hidden_layers": 3},
    "2x512": {"hidden_size": 512, "hidden_layers": 2},
}
LR_RANGE = (3e-5, 1e-3)
ENTROPY_RANGE = (0.001, 0.03)


def sample_parameters(trial, mode):
    architecture = trial.suggest_categorical("architecture", list(ARCHITECTURES))
    parameters = {**ARCHITECTURES[architecture], "lr": 3e-4, "entropy_coef": 0.01}
    if mode == "search":
        parameters["lr"] = trial.suggest_float("lr", *LR_RANGE, log=True)
        parameters["entropy_coef"] = trial.suggest_float("entropy_coef", *ENTROPY_RANGE, log=True)
    return parameters


def initial_trials(mode):
    names = list(ARCHITECTURES) if mode == "architecture" else ["2x128", "2x256"]
    return [{"architecture": name, **({"lr": 3e-4, "entropy_coef": 0.01} if mode == "search" else {})}
            for name in names]
