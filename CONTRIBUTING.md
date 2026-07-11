# Contributing to Data Viewer

## Before starting

Read `AGENTS.md`, `docs/PRODUCT_SPEC.md`, `ARCHITECTURE.md`, and the documents linked by your task.

Choose exactly one task from `tasks/todo.md`. If the task is too large for one focused change, split the task in the plan before editing source.

## Development environments

The current repository still uses the legacy `requirements.txt`. Phase 0 will replace it with reproducible runtime and development dependency sets. Until Phase 0 is complete, do not treat a locally working environment as proof of reproducibility.

Legacy setup on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Legacy setup on Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Target commands

Phase 0 must make these commands authoritative and identical on Windows and Linux:

```bash
python -m pip install -r requirements-dev.txt
python -m data_viewer
python -m pytest -q
python -m pytest tests/unit -q
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python -m pytest tests/gui -q
python -m ruff check .
python -m mypy data_viewer
python -m coverage run -m pytest
python -m coverage report --fail-under=85
```

Packaging commands after migration:

```bash
python build.py --clean --test --windows
python build.py --clean --test --linux
```

## Change workflow

1. Select a task ID.
2. Write or update the contract test.
3. Confirm the test fails for the intended reason.
4. Implement the smallest complete vertical slice.
5. Run targeted tests.
6. Run relevant integration and GUI tests.
7. Run the full quality gate.
8. Update docs, task status, and changelog.
9. Review the diff for scope creep and dead code.

## Code organization

New target code belongs under `data_viewer/`. Do not add new architecture to the legacy root packages unless the task is explicitly a compatibility bridge.

Use these dependency directions:

```text
ui -> application -> domain
                 -> sources -> domain
                 -> plugins -> domain
infrastructure -> domain contracts
domain -> Python standard library and NumPy types only
```

The domain layer must not import PyQt widgets, h5py, pandas, matplotlib, nibabel, openpyxl, or plugin implementations.

## Style

- Python 3.11+ syntax, compatible with Python 3.12 release builds.
- Type all public functions and dataclass fields.
- Prefer dataclasses, enums, and Protocols for stable contracts.
- Use `pathlib.Path` and canonical URI helpers for paths.
- Use structured exceptions from `data_viewer.domain.errors`.
- Keep GUI event handlers thin; application services own orchestration.
- Do not access another component's private attributes.
- Comments explain invariants and trade-offs, not obvious statements.

Example:

```python
from dataclasses import dataclass
from enum import StrEnum


class DataDomain(StrEnum):
    ARRAY = "array"
    TABLE = "table"
    VOLUME = "volume"


@dataclass(frozen=True, slots=True)
class ResourceId:
    source_uri: str
    node_path: str
```

## Tests

- Test behavior, not private implementation.
- Use deterministic fixtures with explicit dtype, shape, and values.
- Use temporary directories for all writable tests.
- Never write user config or repository `config.json` during tests.
- Test malformed and adversarial inputs for every parser.
- Test cancellation and stale-result handling for every background task.
- Use golden numeric inputs for statistics and comparison plugins.
- Render Qt GUI tests with `QT_QPA_PLATFORM=offscreen` in CI.

## Dependencies

Adding a dependency requires:

1. a documented capability gap;
2. official source and maintenance review;
3. Windows/Linux wheel availability;
4. license compatibility review;
5. security and deserialization review;
6. update to `docs/DEPENDENCIES.md`;
7. human approval.

## Pull requests

A reviewable change should normally modify no more than about five product files plus related tests and docs. The description must state:

- task ID;
- behavior changed;
- contract or ADR followed;
- commands run and platforms tested;
- known limitations;
- migration impact.

## Release rule

No release is allowed unless the same commit passes the Windows and Linux acceptance matrices and both packaged artifacts pass smoke tests.
