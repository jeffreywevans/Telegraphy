from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CLI_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class RunOptions:
    seed: int | None = None
    date: str | None = None
    timeout_seconds: float = DEFAULT_CLI_TIMEOUT_SECONDS


@dataclass(frozen=True)
class RunOptionsValidationError:
    message: str


def resolve_run_options(
    *,
    seed_text: str,
    date_text: str,
    current_options: RunOptions,
) -> RunOptions | RunOptionsValidationError:
    normalized_seed_text = seed_text.strip()
    normalized_date_text = date_text.strip()

    seed_value = current_options.seed
    if normalized_seed_text:
        try:
            seed_value = int(normalized_seed_text)
        except ValueError:
            return RunOptionsValidationError(
                f"Invalid seed: {normalized_seed_text!r}. Enter an integer."
            )

    date_value = normalized_date_text or current_options.date
    return RunOptions(
        seed=seed_value,
        date=date_value,
        timeout_seconds=current_options.timeout_seconds,
    )
