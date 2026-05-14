from pathlib import Path
import py_compile
import shutil
import sys


ROOT = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IGNORED_DIRS = {".git", ".venv", "venv", "env", "__pycache__"}

MAIN_PY_FILES = [
    "app.py",
    "cli.py",
    "scanner.py",
    "validator.py",
    "signal_tracker.py",
    "cycle_runner.py",
    "diagnostics.py",
    "technical_analyzer.py",
    "backtester.py",
    "data_provider.py",
    "indicators.py",
    "support_resistance.py",
    "report_builder.py",
    "utils.py",
    "config.py",
]

REQUIRED_FILES = [
    "app.py",
    "cli.py",
    "scanner.py",
    "validator.py",
    "signal_tracker.py",
    "cycle_runner.py",
    "diagnostics.py",
    "data_provider.py",
    "technical_analyzer.py",
    "backtester.py",
    "indicators.py",
    "support_resistance.py",
    "report_builder.py",
    "utils.py",
    "config.py",
    "requirements.txt",
    "README.md",
    "README_RENDER.md",
    "render.yaml",
    ".gitignore",
    ".streamlit/config.toml",
    "check_deploy_ready.py",
    "outputs/.gitkeep",
]


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _remove_pycache() -> None:
    for path in ROOT.rglob("__pycache__"):
        relative_parts = set(path.relative_to(ROOT).parts)
        if path.is_dir() and not relative_parts.intersection(IGNORED_DIRS - {"__pycache__"}):
            shutil.rmtree(path)


def _find_absolute_paths() -> list:
    issues = []
    suffixes = {".py", ".md", ".toml", ".txt", ".yaml", ".yml"}
    patterns = [
        ("C:" + "/Users/", "Absolute Windows path found"),
        ("C:" + "\\" + "Users" + "\\", "Absolute Windows path found"),
        ("\\" + "\\" + "Users" + "\\" + "\\", "Absolute Windows path found"),
        ("/mnt" + "/data", "Absolute mounted data path found"),
    ]

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, message in patterns:
            if pattern in text:
                issues.append(f"{message} in {_relative(path)}")
                break
    return issues


def _find_runtime_outputs() -> list:
    output_dir = ROOT / "outputs"
    if not output_dir.exists():
        return []

    issues = []
    runtime_suffixes = {".csv", ".md", ".json", ".log"}
    for path in output_dir.iterdir():
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() in runtime_suffixes:
            issues.append(f"Runtime output file found: {_relative(path)}")
    return issues


def _compile_main_files() -> list:
    issues = []
    tmp_path = ROOT / ".deploy_check_pycache"
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(exist_ok=True)
    try:
        for filename in MAIN_PY_FILES:
            path = ROOT / filename
            if not path.exists():
                issues.append(f"Missing Python file: {filename}")
                continue
            try:
                py_compile.compile(
                    str(path),
                    cfile=str(tmp_path / f"{path.stem}.pyc"),
                    doraise=True,
                )
            except Exception as exc:
                issues.append(f"Syntax error in {filename}: {exc}")
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
    return issues


def check_deploy_ready() -> int:
    issues = []

    _remove_pycache()

    for filename in REQUIRED_FILES:
        if not (ROOT / filename).exists():
            issues.append(f"Missing file: {filename}")

    if (ROOT / ".env").exists():
        issues.append(".env file found. Do not deploy secrets.")
    if (ROOT / ".streamlit/secrets.toml").exists():
        issues.append(".streamlit/secrets.toml found. Do not commit secrets.")

    issues.extend(_find_absolute_paths())
    issues.extend(_find_runtime_outputs())
    issues.extend(_compile_main_files())

    _remove_pycache()

    if not issues:
        print("DEPLOY READY ✅")
        return 0

    print("Deployment issues found:")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_deploy_ready())
