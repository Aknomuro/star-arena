"""Vérifications statiques uniquement : ne charge aucun module du jeu/Pygame."""
import ast
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tomllib


def exported_names(tree: ast.Module) -> set[str]:
    """Déclarations de module uniquement, sans exécuter ses imports."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(item.id for item in ast.walk(target) if isinstance(item, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Écrire le résultat dans docs/PYTHON_STATIC_CHECKS.json")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "src"
    files = [root / "main.py", *sorted((root / "tools").glob("*.py")), *sorted((source / "star_arena").rglob("*.py")),
             *sorted((root / "tests").glob("test_*.py"))]
    errors: list[str] = []
    references = 0
    symbols = 0
    trees: dict[Path, ast.Module] = {}
    for file in files:
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file), feature_version=(3, 11))
        except (SyntaxError, UnicodeError) as error:
            errors.append(f"{file.relative_to(root)} : {error}")
            continue
        trees[file] = tree
    modules: dict[str, set[str]] = {}
    for file, tree in trees.items():
        if file.is_relative_to(source):
            parts = list(file.relative_to(source).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            modules[".".join(parts)] = exported_names(tree)
    for file, tree in trees.items():
        package = file.relative_to(source).parts[:-1] if file.is_relative_to(source) else ()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package) - node.level + 1] if node.level else ()
                names = [".".join((*prefix, node.module or "")).rstrip(".")]
            for name in names:
                if (name == "pygame" or name.startswith("pygame.")) and ("domain" in file.parts or "systems" in file.parts or file.name == "persistence.py"):
                    errors.append(f"Couplage graphique interdit dans {file.name}")
                if name == "star_arena" or name.startswith("star_arena."):
                    target = source.joinpath(*name.split("."))
                    references += 1
                    if not target.with_suffix(".py").is_file() and not (target / "__init__.py").is_file():
                        errors.append(f"Import local introuvable : {name} dans {file.name}")
                    elif isinstance(node, ast.ImportFrom) and name in modules:
                        for alias in node.names:
                            if alias.name == "*":
                                errors.append(f"Import étoile à éviter : {file.name}")
                                continue
                            symbols += 1
                            if alias.name not in modules[name] and f"{name}.{alias.name}" not in modules:
                                errors.append(f"Symbole local introuvable : {name}.{alias.name} dans {file.name}")
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        if project["project"]["scripts"]["star-arena"] != "star_arena.app:main":
            errors.append("Point d'entrée inattendu.")
        if not any(d.startswith("pygame-ce") for d in project["project"]["dependencies"]):
            errors.append("Dépendance Pygame CE absente.")
        requirements = [line.strip() for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#")]
        if sorted(requirements) != sorted(project["project"]["dependencies"]):
            errors.append("requirements.txt et pyproject.toml ne déclarent pas les mêmes dépendances.")
        if "main" not in modules.get("star_arena.app", set()):
            errors.append("Fonction principale absente.")
        package_tree = trees.get(source / "star_arena" / "__init__.py")
        versions = [node.value.value for node in package_tree.body
                    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)] if package_tree else []
        if versions != [project["project"]["version"]]:
            errors.append("La version Python et celle du paquet diffèrent.")
        for file in (root / ".vscode").glob("*.json"):
            configuration = json.loads(file.read_text(encoding="utf-8"))
            if file.name == "launch.json":
                for entry in configuration.get("configurations", []):
                    if entry.get("program") != "${workspaceFolder}/main.py":
                        errors.append("Le lancement VS Code ne cible pas main.py.")
            if file.name == "tasks.json":
                for task in configuration.get("tasks", []):
                    if task.get("runOptions", {}).get("runOn") == "folderOpen":
                        errors.append("Une tâche VS Code se lance automatiquement à l'ouverture.")
    except (OSError, ValueError, KeyError) as error:
        errors.append(f"Configuration invalide : {error}")
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Analyse statique : syntaxe Python 3.11, modules et symboles importés, séparation domaine/rendu, dépendances et configuration VS Code",
        "python_files": len(files), "local_imports": references, "local_symbols": symbols, "errors": errors,
        "files": [str(file.relative_to(root)).replace("\\", "/") for file in files],
        "pygame_imported": False, "game_imported": False, "game_executed": False, "graphics_executed": False,
        "dependencies_installed": False, "runtime_validation": "NON TESTÉ : vérifications statiques uniquement",
    }
    if arguments.report:
        directory = root / "docs"
        directory.mkdir(exist_ok=True)
        (directory / "PYTHON_STATIC_CHECKS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
