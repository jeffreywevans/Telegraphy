from __future__ import annotations

import subprocess

from telegraphy.scripts import run_coverage_workflow


def _completed(rc: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=rc)


def test_main_returns_combine_return_code(monkeypatch):
    monkeypatch.setattr(run_coverage_workflow.glob, "glob", lambda _pattern: [".coverage.123"])

    return_codes = iter([0, 9, 0, 0])

    def fake_run(_args):
        return _completed(next(return_codes))

    monkeypatch.setattr(run_coverage_workflow.subprocess, "run", fake_run)

    assert run_coverage_workflow.main() == 9


def test_main_returns_xml_return_code(monkeypatch):
    monkeypatch.setattr(run_coverage_workflow.glob, "glob", lambda _pattern: [])

    return_codes = iter([0, 4, 0])

    def fake_run(_args):
        return _completed(next(return_codes))

    monkeypatch.setattr(run_coverage_workflow.subprocess, "run", fake_run)

    assert run_coverage_workflow.main() == 4


def test_main_prioritizes_pytest_failure(monkeypatch):
    monkeypatch.setattr(run_coverage_workflow.glob, "glob", lambda _pattern: [".coverage.123"])

    return_codes = iter([5, 7, 3, 2])

    def fake_run(_args):
        return _completed(next(return_codes))

    monkeypatch.setattr(run_coverage_workflow.subprocess, "run", fake_run)

    assert run_coverage_workflow.main() == 5


def test_main_uses_subcommand_rcfile_flag_order(monkeypatch):
    monkeypatch.setattr(run_coverage_workflow.glob, "glob", lambda _pattern: [".coverage.123"])

    calls: list[list[str]] = []

    def fake_run(args):
        calls.append(args)
        return _completed(0)

    monkeypatch.setattr(run_coverage_workflow.subprocess, "run", fake_run)

    assert run_coverage_workflow.main() == 0
    rcfile_args = [call[4] for call in calls[1:4]]
    assert calls[1][3] == "combine"
    assert calls[2][3] == "xml"
    assert calls[3][3] == "report"
    for rcfile_arg in rcfile_args:
        assert rcfile_arg.startswith("--rcfile=")
        assert rcfile_arg.endswith("tox.ini")
