import os, io
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from nvme_models.storage import NVMeStorageManager, SecurityException

def _cfg(tmp_path):
    return {
        "storage": {"nvme_path": str(tmp_path), "require_mount": False, "min_free_space_gb": 50},
        "providers": {}
    }

def test_download_atomic_respects_space_and_boundaries(tmp_path, monkeypatch):
    m = NVMeStorageManager(_cfg(tmp_path))
    # Mock handler
    fake = SimpleNamespace(
        estimate_model_size=lambda model_id: 1,  # 1 GB estimate
        download_to_path=lambda model_id, p: Path(p).mkdir(parents=True, exist_ok=True) or (Path(p) / "weights.bin").write_bytes(b"x"*16)
    )
    monkeypatch.setattr("nvme_models.models.get_provider_handler", lambda provider, cfg: fake)
    # Avoid real locking
    monkeypatch.setattr(m, "_acquire_lock", lambda: 3)
    monkeypatch.setattr(m, "_release_lock", lambda fd: None)
    # Ensure reservation returns a path (simulate success)
    monkeypatch.setattr(m, "_reserve_disk_space", lambda size_gb: tmp_path / ".reserve")
    monkeypatch.setattr(m, "_release_disk_reservation", lambda rf: None)

    tgt = Path(tmp_path) / "models" / "hf" / "tiny" / "weights"
    out = m.download_atomic("huggingface", "org/tiny", tgt)
    assert tgt.exists()
    # Idempotence: re-run should not explode
    out2 = m.download_atomic("huggingface", "org/tiny", tgt)
    assert out2.exists()

def test_download_atomic_low_space_rejected(tmp_path, monkeypatch):
    m = NVMeStorageManager(_cfg(tmp_path))
    # Force reservation to fail (simulate low space)
    monkeypatch.setattr(m, "_reserve_disk_space", lambda size_gb: None)
    monkeypatch.setattr(m, "_acquire_lock", lambda: 3)
    monkeypatch.setattr(m, "_release_lock", lambda fd: None)

    fake = SimpleNamespace(estimate_model_size=lambda model_id: 100, download_to_path=lambda *a, **k: None)
    monkeypatch.setattr("nvme_models.models.get_provider_handler", lambda provider, cfg: fake)
    with pytest.raises(IOError):
        m.download_atomic("huggingface", "org/tiny", Path(tmp_path) / "models" / "hf" / "tiny")

def test_target_path_validation(tmp_path, monkeypatch):
    m = NVMeStorageManager(_cfg(tmp_path))
    monkeypatch.setattr("nvme_models.models.get_provider_handler", lambda provider, cfg: SimpleNamespace(
        estimate_model_size=lambda model_id: 1,
        download_to_path=lambda model_id, p: Path(p).mkdir(parents=True, exist_ok=True)
    ))
    monkeypatch.setattr(m, "_acquire_lock", lambda: 3)
    monkeypatch.setattr(m, "_release_lock", lambda fd: None)
    # Try to escape base
    bad = Path(tmp_path).parent / "escape"
    with pytest.raises(SecurityException):
        m.download_atomic("huggingface", "org/tiny", bad)