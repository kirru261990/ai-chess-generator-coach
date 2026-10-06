import importlib.metadata as md
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_licence_is_the_full_agpl_3_text_and_the_project_files_declare_it():
    text = (ROOT / "LICENSE").read_text()
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in text and "Version 3, 19 November 2007" in text
    assert "13. Remote Network Interaction" in text and len(text.splitlines()) > 600
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    assert pyproject["project"]["license"] == "AGPL-3.0-or-later"
    assert json.loads((ROOT / "web" / "package.json").read_text())["license"] == "AGPL-3.0-or-later"


def _names_in(requirement_list):
    return {re.split(r"[<>=\[ ;]", r, maxsplit=1)[0].lower() for r in requirement_list}


def test_every_direct_dependency_is_listed_in_third_party():
    third = (ROOT / "THIRD_PARTY.md").read_text().lower()
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    python = _names_in(pyproject["project"]["dependencies"]) | _names_in(pyproject["dependency-groups"]["dev"])
    package = json.loads((ROOT / "web" / "package.json").read_text())
    web = set(package.get("dependencies", {})) | set(package.get("devDependencies", {}))
    missing = [n for n in sorted(python | web) if n not in third and not (n == "chess" and "python-chess" in third)]
    assert missing == [], f"add a row to THIRD_PARTY.md for: {missing}"  # ADR 0001 rule 1


def test_no_installed_python_package_is_copyleft_except_python_chess():
    copyleft = set()
    for dist in md.distributions():
        meta = dist.metadata
        lic = (meta.get("License-Expression") or meta.get("License") or "").splitlines()[:1]
        classifiers = " ".join(c for c in meta.get_all("Classifier", []) if c.startswith("License"))
        text = f"{' '.join(lic)} {classifiers}".upper()
        if "GPL" in text and "LGPL" not in text:
            copyleft.add(meta["Name"].lower())
    # A new copyleft dependency needs a decision and a row in THIRD_PARTY.md, not a silent addition.
    assert copyleft == {"chess"}, copyleft


def test_runtime_imports_are_declared_as_runtime_dependencies():
    # httpx was imported by the Chess.com sync but only declared as a dev dependency.
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    runtime = _names_in(pyproject["project"]["dependencies"])
    for module, package in (("httpx", "httpx"), ("dotenv", "python-dotenv"), ("chess", "chess"), ("fastapi", "fastapi")):
        used = any(f"import {module}" in f.read_text() or f"from {module}" in f.read_text()
                   for f in (ROOT / "backend" / "app").rglob("*.py"))
        assert not used or package in runtime, f"{package} is imported by app/ but is not a runtime dependency"
