from pathlib import Path
import py_compile
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IGNORED_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "dist", ".cta_storage_test", "outputs"}
FORBIDDEN_PACKAGE_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "outputs"}
FORBIDDEN_PACKAGE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".bak", ".zip", ".rar", ".7z"}
RUNTIME_SUFFIXES = {".csv", ".md", ".json", ".log"}
TEMP_SUFFIXES = {".tmp", ".bak", ".swp", ".pyc", ".pyo"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?secret|secret[_-]?key|token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-/.+=]{20,})"
)

MAIN_PY_FILES = [
    "app.py",
    "cli.py",
    "scanner.py",
    "validator.py",
    "signal_tracker.py",
    "cycle_runner.py",
    "paper_cycle.py",
    "paper_trader.py",
    "diagnostics.py",
    "technical_analyzer.py",
    "backtester.py",
    "data_provider.py",
    "rate_limiter.py",
    "storage.py",
    "strategy_engine.py",
    "indicators.py",
    "support_resistance.py",
    "report_builder.py",
    "utils.py",
    "config.py",
    "rate_limiter.py",
    "storage.py",
    "strategy_engine.py",
]

REQUIRED_FILES = [
    "app.py",
    "cli.py",
    "scanner.py",
    "validator.py",
    "signal_tracker.py",
    "cycle_runner.py",
    "paper_cycle.py",
    "paper_trader.py",
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
    ".env.example",
    ".streamlit/config.toml",
    "check_deploy_ready.py",
    "tools/package_project.py",
    "tools/import_csv_to_sqlite.py",
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
    return []


def _find_clean_package_issues() -> list:
    issues = []
    try:
        from tools import package_project
    except Exception as exc:
        return [f"Cannot import tools/package_project.py: {exc}"]

    included, _ = package_project.collect_files()
    for path in included:
        rel_path = path.relative_to(ROOT)
        rel = rel_path.as_posix()
        parts = set(rel_path.parts)
        if parts.intersection(FORBIDDEN_PACKAGE_DIRS):
            issues.append(f"Forbidden path would be packaged: {rel}")
        if path.name == ".env" or path.name.endswith(".env"):
            issues.append(f"Env/secrets file would be packaged: {rel}")
        if path.suffix.lower() in FORBIDDEN_PACKAGE_SUFFIXES:
            issues.append(f"Runtime/cache artifact would be packaged: {rel}")
        if _has_absolute_path(path):
            issues.append(f"Absolute local path would be packaged: {rel}")
    return issues


def _has_absolute_path(path: Path) -> bool:
    if path.suffix.lower() not in {".py", ".md", ".toml", ".txt", ".yaml", ".yml"}:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return any(
        pattern in text
        for pattern in (
            "C:" + "/Users/",
            "C:" + "\\" + "Users" + "\\",
            "\\" + "\\" + "Users" + "\\" + "\\",
            "/mnt" + "/data",
        )
    )


def _find_packaging_issues() -> list:
    issues = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in TEMP_SUFFIXES:
            issues.append(f"Temporary/cache file found: {_relative(path)}")
        if path.name.endswith(".env") or path.name == ".env":
            issues.append(f"Env/secrets file found: {_relative(path)}")
    return issues


def _find_hardcoded_secrets() -> list:
    issues = []
    suffixes = {".py", ".sh", ".bat", ".md", ".toml", ".yaml", ".yml", ".txt"}
    allowed_placeholders = {
        "tu_api_key",
        "tu_api_secret",
        "your_api_key",
        "your_api_secret",
    }
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in SECRET_ASSIGNMENT_RE.finditer(text):
            value = match.group(1).strip().strip("'\"")
            if value and value.lower() not in allowed_placeholders:
                issues.append(f"Possible hardcoded secret in {_relative(path)}")
                break
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
    issues.extend(_find_packaging_issues())
    issues.extend(_find_clean_package_issues())
    issues.extend(_find_hardcoded_secrets())
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
