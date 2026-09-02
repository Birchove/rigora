"""AST-only import graph checks for the architecture's dependency boundaries."""

import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[1] / "src" / "research_mentor"


def _module_parts(path: Path) -> tuple[str, ...]:
    relative = path.relative_to(SOURCE_ROOT.parent).with_suffix("")
    parts = relative.parts
    return parts[:-1] if parts[-1] == "__init__" else parts


def _import_targets(path: Path) -> list[str]:
    module = _module_parts(path)
    package = module if path.name == "__init__.py" else module[:-1]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _import_targets_from_tree(tree, package)


def _import_targets_from_tree(tree: ast.AST, package: tuple[str, ...]) -> list[str]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
            else:
                base = ()
            if node.module:
                resolved = (*base, *node.module.split("."))
                module_name = ".".join(resolved)
                targets.append(module_name)
                targets.extend(
                    f"{module_name}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
            else:
                targets.extend(
                    ".".join((*base, alias.name))
                    for alias in node.names
                    if alias.name != "*"
                )
    return targets


def _matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _boundary_violations(module: str, imports: list[str]) -> list[str]:
    violations: list[str] = []
    if _matches(module, "research_mentor.domain"):
        forbidden = (
            "research_mentor.agents",
            "research_mentor.harness",
            "research_mentor.ports",
            "research_mentor.adapters",
        )
        violations.extend(
            f"{module} imports {target}"
            for target in imports
            if any(_matches(target, prefix) for prefix in forbidden)
        )
    if _matches(module, "research_mentor.agents") and module.endswith(".runner"):
        violations.extend(
            f"{module} imports repository {target}"
            for target in imports
            if target.startswith("research_mentor.") and "repository" in target.split(".")
        )
    if _matches(module, "research_mentor.agents"):
        parts = module.split(".")
        current_agent = parts[2] if len(parts) >= 3 else None
        for target in imports:
            target_parts = target.split(".")
            if (
                len(target_parts) >= 4
                and target_parts[:2] == ["research_mentor", "agents"]
                and target_parts[2] not in {current_agent, "common"}
                and target_parts[3] in {"runner", "prompting"}
            ):
                violations.append(f"{module} imports another agent runtime {target}")
            if any(
                _matches(target, prefix)
                for prefix in (
                    "research_mentor.adapters",
                    "research_mentor.application",
                    "research_mentor.harness.orchestrator",
                    "research_mentor.harness.orchestration",
                    "research_mentor.harness.state",
                )
            ):
                violations.append(
                    f"{module} imports provider, repository, or harness state {target}"
                )
            if "repository" in target_parts:
                violations.append(f"{module} imports repository {target}")
    if _matches(module, "research_mentor.adapters"):
        violations.extend(
            f"{module} imports orchestrator {target}"
            for target in imports
            if _matches(target, "research_mentor.harness.orchestrator")
            or _matches(target, "research_mentor.harness.orchestration")
        )
    return violations


def test_architecture_import_boundaries() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        module = ".".join(_module_parts(path))
        imports = _import_targets(path)
        violations.extend(_boundary_violations(module, imports))

    assert violations == []


def test_relative_import_resolution_and_boundary_segment_matching() -> None:
    domain_imports = _import_targets_from_tree(
        ast.parse("from .. import ports"), ("research_mentor", "domain")
    )
    runner_imports = _import_targets_from_tree(
        ast.parse("from research_mentor.adapters.memory import repository"),
        ("research_mentor", "agents", "idea_review"),
    )

    assert domain_imports == ["research_mentor.ports"]
    assert _boundary_violations("research_mentor.domain.example", domain_imports)
    assert runner_imports == [
        "research_mentor.adapters.memory",
        "research_mentor.adapters.memory.repository",
    ]
    assert _boundary_violations("research_mentor.agents.idea_review.runner", runner_imports)
    assert _boundary_violations(
        "research_mentor.domain.example", ["research_mentor.adapters_extra"]
    ) == []
