import pytest
from nvme_models.validators import SecurityValidator, Validator, ValidationError

def test_model_id_rejects_traversal_and_schemes():
    for bad in ["../etc/passwd", "/abs/path", "http://evil/x", "file:///x"]:
        ok, msg = SecurityValidator.validate_model_id(bad, "huggingface")
        assert not ok
        assert msg

def test_validate_path_base_enforced(tmp_path):
    v = Validator()
    safe = tmp_path/"a"/"b"
    safe2 = v.validate_path(safe, base_path=tmp_path)
    assert str(safe2).startswith(str(tmp_path))
    outside = tmp_path.parent / "z"
    with pytest.raises(ValidationError):
        v.validate_path(outside, base_path=tmp_path)