from app.services.workspace_history import (
    compare_snapshot, create_snapshot, restore_snapshot_file,
)


def test_snapshot_reports_and_restores_added_modified_and_deleted_files(tmp_path):
    (tmp_path / "keep.txt").write_text("before\n", encoding="utf-8")
    (tmp_path / "remove.txt").write_text("remove me\n", encoding="utf-8")
    snapshot = create_snapshot(tmp_path, "before task")

    (tmp_path / "keep.txt").write_text("after\n", encoding="utf-8")
    (tmp_path / "remove.txt").unlink()
    (tmp_path / "new.txt").write_text("new file\n", encoding="utf-8")

    diff = compare_snapshot(tmp_path, snapshot["id"])
    assert diff["summary"] == {"changed": 3, "added": 1, "modified": 1, "deleted": 1}
    assert {item["path"] for item in diff["files"]} == {
        "keep.txt", "remove.txt", "new.txt"
    }

    restore_snapshot_file(tmp_path, snapshot["id"], "keep.txt")
    restore_snapshot_file(tmp_path, snapshot["id"], "remove.txt")
    restore_snapshot_file(tmp_path, snapshot["id"], "new.txt")
    assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "before\n"
    assert (tmp_path / "remove.txt").read_text(encoding="utf-8") == "remove me\n"
    assert not (tmp_path / "new.txt").exists()


def test_snapshot_excludes_its_own_storage_and_symlinks(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    snapshot = create_snapshot(tmp_path)
    diff = compare_snapshot(tmp_path, snapshot["id"])
    assert diff["summary"]["changed"] == 0
    assert "src/main.py" in (tmp_path / ".omnidev" / "history" / "snapshots" / f"{snapshot['id']}.json").read_text(encoding="utf-8")
