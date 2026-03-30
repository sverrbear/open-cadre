"""Tests for project detection."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from cadre.detect import detect_project


def test_detect_empty_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = detect_project(Path(tmpdir))
        assert result.project_type == "generic"
        assert result.ci_platform == "none"


def test_detect_dbt_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        dbt_project = Path(tmpdir) / "dbt_project.yml"
        dbt_project.write_text(yaml.dump({"name": "analytics", "version": "1.0.0"}))

        result = detect_project(Path(tmpdir))
        assert result.project_type == "dbt"
        assert result.project_name == "analytics"


def test_detect_github_actions():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / ".github" / "workflows").mkdir(parents=True)

        result = detect_project(Path(tmpdir))
        assert result.ci_platform == "github_actions"


def test_detect_gitlab_ci():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / ".gitlab-ci.yml").touch()

        result = detect_project(Path(tmpdir))
        assert result.ci_platform == "gitlab_ci"
