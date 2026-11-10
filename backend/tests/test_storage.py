import pytest

from app.storage import LocalFileStorage


def test_local_storage_save_load_delete(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    storage.save("documents/1/v1/a.txt", b"hello")

    assert storage.load("documents/1/v1/a.txt") == b"hello"
    storage.delete("documents/1/v1/a.txt")
    assert not (tmp_path / "documents/1/v1/a.txt").exists()


def test_local_storage_rejects_path_outside_root(tmp_path):
    storage = LocalFileStorage(str(tmp_path / "root"))
    with pytest.raises(ValueError):
        storage.save("../outside.txt", b"x")
