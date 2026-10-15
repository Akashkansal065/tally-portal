"""Backup restore extracts archives member by member and refuses anything that could write outside the folder."""
import io
import stat
import zipfile

import pytest

from backup_module.storage import UnsafeArchiveError, safe_extract_zip


def _zip(tmp_path, members):
    path = tmp_path / "b.zip"
    with zipfile.ZipFile(path, "w") as z:
        for item in members:
            if isinstance(item, zipfile.ZipInfo):
                z.writestr(item, "x")
            else:
                z.writestr(item[0], item[1])
    return path


def test_normal_backup_extracts(tmp_path):
    z = _zip(tmp_path, [("a.json", "1"), ("sub/b.json", "2")])
    out = safe_extract_zip(z, tmp_path / "out")
    assert (out / "a.json").read_text() == "1"
    assert (out / "sub" / "b.json").read_text() == "2"


@pytest.mark.parametrize("name", ["../evil.txt", "a/../../evil.txt", "/abs/evil.txt", "C:/evil.txt", "..\\evil.txt"])
def test_unsafe_paths_are_rejected_and_nothing_written(tmp_path, name):
    z = _zip(tmp_path, [("ok.json", "1"), (name, "boom")])
    out = tmp_path / "out"
    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(z, out)
    assert not (tmp_path / "evil.txt").exists()
    assert not (out / "ok.json").exists()


def test_symlink_member_is_rejected(tmp_path):
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(_zip(tmp_path, [info]), tmp_path / "out")


def test_member_count_and_size_caps(tmp_path):
    z = _zip(tmp_path, [("a", "1"), ("b", "2"), ("c", "3")])
    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(z, tmp_path / "o1", max_members=2)
    with pytest.raises(UnsafeArchiveError):
        safe_extract_zip(_zip(tmp_path, [("big", "x" * 100)]), tmp_path / "o2", max_total_bytes=10)
