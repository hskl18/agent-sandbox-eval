from agent_sandbox_eval.cli import main


def test_validate_tasks_command(capsys) -> None:  # type: ignore[no-untyped-def]
    main(["validate-tasks", "--benchmark", "mcp_like"])

    output = capsys.readouterr().out
    assert "validated 3 task manifests" in output
    assert "update-status-001" in output

