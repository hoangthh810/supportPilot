from __future__ import annotations

import ast
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infrastructure/migrations/support/versions/0002_db001a_core_support.py"
)


def migration_function(name: str) -> ast.FunctionDef:
    module = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    return next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def operation_names(function: ast.FunctionDef) -> list[str]:
    return [
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
    ]


def test_db001a_upgrade_is_an_in_place_forward_migration() -> None:
    operations = operation_names(migration_function("upgrade"))

    assert "create_table" not in operations
    assert "drop_table" not in operations
    assert "add_column" in operations
    assert "alter_column" in operations
    assert "create_foreign_key" in operations
    assert "create_check_constraint" in operations


def test_db001a_downgrade_does_not_replace_skeleton_tables() -> None:
    operations = operation_names(migration_function("downgrade"))

    assert "create_table" not in operations
    assert "drop_table" not in operations
    assert "drop_column" in operations
    assert "drop_constraint" in operations


def test_db001a_migration_has_no_deferred_or_attachment_columns() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "attachment" not in source.lower()
    assert "_cipher" not in source
    assert "_lookup_hash" not in source
