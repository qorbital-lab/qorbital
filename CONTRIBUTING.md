# Contributing to qOrbital

See [SetupGuide.md](SetupGuide.md) for repository conventions, hardware run logs, and CI expectations (no IonQ jobs in CI).

## Local setup

```bash
git clone https://github.com/qorbital-lab/qorbital.git
cd qorbital
uv sync --dev
```

## Checks before a PR

```bash
uv run pytest
uv run ruff check qorbital tests
uv run ruff format --check qorbital tests
```

Open a PR using the template; link issues with `Closes #NNN` where applicable.
