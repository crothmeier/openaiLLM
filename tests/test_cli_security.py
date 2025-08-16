import pytest
from click.testing import CliRunner
from nvme_models.cli import cli

def test_cli_requires_existing_config(tmp_path):
    runner = CliRunner()
    res = runner.invoke(cli, ["--config", str(tmp_path/"missing.toml"), "list"])
    assert res.exit_code != 0

def test_cli_rejects_invalid_model_id(monkeypatch):
    runner = CliRunner()
    # Assume subcommand 'delete' triggers validate_model_id inside
    res = runner.invoke(cli, ["delete", "../etc/passwd"])
    assert res.exit_code != 0
    assert "invalid" in (res.output.lower() or "")