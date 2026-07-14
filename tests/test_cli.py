import pytest

from agent_sandbox_eval.cli import main


def test_validate_tasks_command(capsys) -> None:  # type: ignore[no-untyped-def]
    main(["validate-tasks", "--benchmark", "mcp_like"])

    output = capsys.readouterr().out
    assert "validated 3 task manifests" in output
    assert "update-status-001" in output


def test_version_command_reads_package_metadata(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    assert capsys.readouterr().out.strip() == "ase 0.2.0"
