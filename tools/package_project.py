#!/usr/bin/env python3
"""
Create a clean project zip without local runtime state or secrets.

Usage:
    python tools/package_project.py --dry-run
    python tools/package_project.py
"""

from __future__ import annotations

import argparse
import os
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
ZIP_PATH = DIST_DIR / "crypto_technical_advisor_clean.zip"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "outputs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    ".cta_storage_test",
    "brain",
    "backups",
}

EXCLUDED_NAMES = {
    ".env",
    ".streamlit/secrets.toml",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".bak",
    ".zip",
    ".rar",
    ".7z",
}

TEXT_SUFFIXES = {".py", ".sh", ".bat", ".md", ".yaml", ".yml", ".toml", ".txt", ".env", ".example"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?secret|secret[_-]?key|token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-/.+=]{20,})"
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _has_secret_assignment(path: Path) -> bool:
    if path.name == ".env.example":
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env":
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for match in SECRET_ASSIGNMENT_RE.finditer(text):
        value = match.group(1).strip()
        if value and value.lower() not in {"tu_api_key", "tu_api_secret", "your_api_key", "your_secret"}:
            return True
    return False


def classify_path(path: Path) -> tuple[bool, str]:
    rel = _relative(path)
    parts = set(path.relative_to(ROOT).parts)

    if parts.intersection(EXCLUDED_DIRS):
        return False, "excluded directory"
    if any(part.startswith("pytest-cache-files-") for part in path.relative_to(ROOT).parts):
        return False, "pytest cache temp"
    if rel in EXCLUDED_NAMES or path.name.endswith(".env"):
        return False, "secret/env file"
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False, "runtime/build artifact"
    if path.name.startswith("~") or path.name.endswith(".swp"):
        return False, "temporary file"
    if _has_secret_assignment(path):
        return False, "possible hardcoded secret"
    return True, "included"


def collect_files() -> tuple[list[Path], list[tuple[Path, str]]]:
    included: list[Path] = []
    excluded: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        kept_dirnames = []
        for dirname in dirnames:
            if dirname in EXCLUDED_DIRS or dirname.startswith("pytest-cache-files-"):
                excluded.append((current / dirname, "excluded directory"))
            else:
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
        for filename in sorted(filenames):
            path = current / filename
            if not path.is_file():
                continue
            include, reason = classify_path(path)
            if include:
                included.append(path)
            else:
                excluded.append((path, reason))
    return included, excluded


def create_zip(files: list[Path], zip_path: Path = ZIP_PATH) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, _relative(path))
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a clean project zip.")
    parser.add_argument("--dry-run", action="store_true", help="List included/excluded files without creating a zip.")
    args = parser.parse_args()

    included, excluded = collect_files()

    if args.dry_run:
        print("Included files:")
        for path in included:
            print(f"  + {_relative(path)}")
        print("\nExcluded files:")
        for path, reason in excluded:
            print(f"  - {_relative(path)} ({reason})")
        print(f"\nWould include {len(included)} files.")
        return 0

    zip_path = create_zip(included)
    print(f"Clean zip created: {zip_path}")
    print(f"Included files: {len(included)}")
    print(f"Excluded files: {len(excluded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
