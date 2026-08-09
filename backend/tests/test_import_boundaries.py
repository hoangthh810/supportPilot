import ast
from pathlib import Path


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_support_api_has_no_mock_commerce_runtime_imports() -> None:
    support_api_root = Path("backend/apps/support_api")
    forbidden_segments = {"mock_commerce_api", "commerce.models", "commerce.repositories"}
    violations: list[str] = []

    for path in support_api_root.rglob("*.py"):
        for module in imported_modules(path):
            if any(segment in module for segment in forbidden_segments):
                violations.append(f"{path}: {module}")

    assert violations == []


def test_public_skeleton_router_does_not_import_fake_implementations() -> None:
    router_path = Path("backend/apps/support_api/walking_skeleton/router.py")
    modules = imported_modules(router_path)

    assert "backend.apps.support_api.walking_skeleton.adapters" not in modules


def test_mock_commerce_has_no_support_runtime_imports() -> None:
    mock_commerce_root = Path("backend/apps/mock_commerce_api")
    violations: list[str] = []

    for path in mock_commerce_root.rglob("*.py"):
        for module in imported_modules(path):
            if module.startswith("backend.apps.support_api"):
                violations.append(f"{path}: {module}")

    assert violations == []
