"""Sheet removal-readiness test.

Guarantees the legacy Google Sheets dependency is contained: no module outside
the removable legacy layer may import the google sheets client or the legacy
writeback service, and core routes/services must not reference sheet-coupled
columns (`sheet_row`, `synced_hash`). Deleting the legacy layer must not
require changes to core business logic.

`app.models`/`app.schemas` may reference the columns (they describe the DB
schema shape), and `app.main` is the documented deletion point where the legacy
subscriber is registered.
"""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

LEGACY_MODULES = (
    "app.services.legacy",
    "app.services.sheets",
    "app.workers.sync_worker",
)

MAIN_ALLOWED = ("app.main",)
SCHEMA_ALLOWED = ("app.models", "app.schemas")

FORBIDDEN_IMPORTS = ("app.services.sheets", "app.services.legacy.writeback")
FORBIDDEN_ATTRS = ("sheet_row", "synced_hash")


def _dotted(path: Path) -> str:
    rel = path.relative_to(BACKEND).as_posix().removesuffix(".py")
    return ".".join(part for part in rel.split("/") if part)


def _is_legacy(dotted: str) -> bool:
    return any(dotted == m or dotted.startswith(m + ".") for m in LEGACY_MODULES)


def _import_roots(tree: ast.AST):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_legacy_sheets_dependency_is_contained():
    app_dir = BACKEND / "app"
    violations = []

    for py in sorted(app_dir.rglob("*.py")):
        if py.name == "__init__.py" or "tests" in py.parts:
            continue
        dotted = _dotted(py)
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))

        # 1) No forbidden sheet imports outside the legacy layer.
        if not (_is_legacy(dotted) or dotted in MAIN_ALLOWED):
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    else:
                        names = [node.module or ""]
                    for name in names:
                        if any(name == f or name.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                            violations.append(f"{dotted}: forbidden import {name}")

        # 2) No sheet-coupled attribute references in core routes/services.
        if not (_is_legacy(dotted) or dotted in MAIN_ALLOWED or dotted.startswith(SCHEMA_ALLOWED)):
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                    violations.append(f"{dotted}: references .{node.attr}")

    assert not violations, "Sheet dependency leaked outside the legacy layer:\n" + "\n".join(violations)


def test_legacy_layer_present_and_localized():
    # The legacy pieces must exist so their removal is a single, reviewable act.
    assert (BACKEND / "app/services/legacy/sheet_adapter.py").exists()
    assert (BACKEND / "app/services/legacy/subscriber.py").exists()
    assert (BACKEND / "app/services/legacy/writeback.py").exists()
    assert (BACKEND / "app/services/legacy/guard.py").exists()
    assert (BACKEND / "app/services/sheets.py").exists()