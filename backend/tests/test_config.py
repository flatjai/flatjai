import pytest

from flatjai.config import load_profile


def test_local_profile_loads(tmp_path):
    f = tmp_path / "models.yaml"
    f.write_text("models:\n  local: {base_url: 'http://localhost:11434/v1', model: 'qwen3:8b'}\n")
    assert load_profile("local", f).model == "qwen3:8b"


def test_tacc_profile_reads_url_file(tmp_path):
    (tmp_path / "url.txt").write_text("http://10-0-1-10:8000/v1\n")
    f = tmp_path / "models.yaml"
    f.write_text("models:\n  tacc: {base_url_file: url.txt, model: Qwen3.8-27B, max_concurrency: 4}\n")
    p = load_profile("tacc", f)
    assert p.base_url == "http://10-0-1-10:8000/v1" and p.max_concurrency == 4


def test_tacc_without_url_file_explains_what_to_do(tmp_path):
    f = tmp_path / "models.yaml"
    f.write_text("models:\n  tacc: {base_url_file: missing.txt, model: q}\n")
    with pytest.raises(FileNotFoundError, match="SERVICE_BASE_URL"):
        load_profile("tacc", f)
