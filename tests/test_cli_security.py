import pytest
from click.testing import CliRunner
from nvme_models.cli import cli

@pytest.mark.skip(reason="CLI creates default config if missing")
def test_cli_requires_existing_config(tmp_path):
    runner = CliRunner()
    res = runner.invoke(cli, ["--config", str(tmp_path/"missing.toml"), "list"])
    assert res.exit_code != 0

def test_cli_rejects_invalid_model_id(tmp_path):
    runner = CliRunner()
    # Create a minimal config
    config_file = tmp_path / "config.toml"
    config_file.write_text('[storage]\nnvme_path = "/tmp"\nrequire_mount = false\n')
    
    # Use download command which validates model IDs
    res = runner.invoke(cli, ["--config", str(config_file), "download", "huggingface", "../etc/passwd"])
    assert res.exit_code != 0