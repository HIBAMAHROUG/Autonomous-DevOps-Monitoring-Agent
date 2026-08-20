from unittest.mock import MagicMock, patch

from executor.ansible_executor import AnsibleExecutor
from executor.service import ExecutionService
from remediation.models import Action


def test_rejects_unknown_playbook():
    executor = AnsibleExecutor()

    result = executor.execute(
        "a1",
        {"playbook": "delete_everything"},
        dry_run=True,
    )

    assert result.success is False
    assert (
        "non autorisé" in result.message.lower()
        or "inconnu" in result.message.lower()
    )


@patch("executor.ansible_executor.subprocess.run")
def test_dry_run_adds_check_flag(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="ok",
        stderr="",
    )

    executor = AnsibleExecutor()

    result = executor.execute(
        "a1",
        {
            "playbook": "cleanup_disk_space",
            "target_path": "/var/log",
            "older_than_days": 7,
        },
        dry_run=True,
    )

    assert result.success is True

    called_command = mock_run.call_args.args[0]

    assert "--check" in called_command


@patch("executor.ansible_executor.subprocess.run")
def test_real_run_does_not_add_check_flag(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="ok",
        stderr="",
    )

    executor = AnsibleExecutor()

    result = executor.execute(
        "a1",
        {
            "playbook": "restart_service",
            "service_name": "nginx",
        },
        dry_run=False,
    )

    assert result.success is True

    called_command = mock_run.call_args.args[0]

    assert "--check" not in called_command


@patch("executor.ansible_executor.subprocess.run")
def test_ansible_playbook_not_installed_returns_clean_failure(mock_run):
    mock_run.side_effect = FileNotFoundError()

    executor = AnsibleExecutor()

    result = executor.execute(
        "a1",
        {"playbook": "cleanup_disk_space"},
        dry_run=True,
    )

    assert result.success is False
    assert "introuvable" in result.message.lower()


@patch("executor.ansible_executor.subprocess.run")
def test_execution_service_routes_ansible_action(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="ok",
        stderr="",
    )

    service = ExecutionService()

    action = Action(
        action_id="cleanup-1",
        name="cleanup disk",
        type="ansible",
        executor="ansible",
    )

    result = service.execute(
        action,
        params={
            "playbook": "cleanup_disk_space",
            "target_path": "/tmp",
            "older_than_days": 3,
        },
        dry_run=True,
    )

    assert result.success is True
    assert result.executor == "ansible"
