from pathlib import Path

from tools import package_project


def test_packager_excludes_runtime_and_secrets():
    included, excluded = package_project.collect_files()
    included_rel = {path.relative_to(package_project.ROOT).as_posix() for path in included}
    excluded_rel = {path.relative_to(package_project.ROOT).as_posix() for path, _ in excluded}

    assert ".env.example" in included_rel
    assert all(not rel.startswith(".git/") for rel in included_rel)
    assert all(not rel.startswith(".venv/") for rel in included_rel)
    assert all(not rel.startswith("outputs/") for rel in included_rel)
    assert all(not rel.endswith(".pyc") for rel in included_rel)
    assert "start_paper.sh" in included_rel
    assert "start_paper.bat" in included_rel
    assert "outputs" in excluded_rel or any(rel.startswith("outputs/") for rel in excluded_rel)


def test_secret_assignment_detector_allows_examples():
    assert package_project._has_secret_assignment(package_project.ROOT / ".env.example") is False
    assert package_project.classify_path(package_project.ROOT / "start_paper.sh")[0] is True


def main():
    test_packager_excludes_runtime_and_secrets()
    test_secret_assignment_detector_allows_examples()
    print("PACKAGE PROJECT TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
