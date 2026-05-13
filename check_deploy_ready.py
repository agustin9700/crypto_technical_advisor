from pathlib import Path
import py_compile
import shutil
import sys


ROOT = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN_PY_FILES = [
    "app.py",
    "cli.py",
    "scanner.py",
    "validator.py",
    "signal_tracker.py",
    "cycle_runner.py",
    "technical_analyzer.py",
    "backtester.py",
    "data_provider.py",
    "indicators.py",
    "support_resistance.py",
    "report_builder.py",
    "utils.py",
    "config.py",
]


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _remove_pycache() -> None:
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)


def _find_absolute_windows_paths() -> list:
    issues = []
    suffixes = {".py", ".md", ".toml", ".txt"}
    ignored_dirs = {".git", ".venv", "venv", "env", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if ("C:" + "/Users/") in text or ("C:" + "\\Users\\") in text:
            issues.append(f"Absolute Windows path found in {_relative(path)}")
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

    required_files = [
        "app.py",
        "requirements.txt",
        ".gitignore",
        ".streamlit/config.toml",
        "outputs/.gitkeep",
    ]
    for filename in required_files:
        if not (ROOT / filename).exists():
            issues.append(f"Missing file: {filename}")

    if (ROOT / ".env").exists():
        issues.append(".env file found. Do not deploy secrets.")
    if (ROOT / ".streamlit/secrets.toml").exists():
        issues.append(".streamlit/secrets.toml found. Do not commit secrets.")

    issues.extend(_find_absolute_windows_paths())
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
