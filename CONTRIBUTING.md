# Contributing to qOrbital

See [SetupGuide.md](SetupGuide.md) for repository conventions, hardware run logs, and CI expectations (no IonQ jobs in CI).

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks before a PR

```bash
pytest
ruff check qorbital tests
ruff format --check qorbital tests
```

Open a PR using the template; link issues with `Closes #NNN` where applicable.
