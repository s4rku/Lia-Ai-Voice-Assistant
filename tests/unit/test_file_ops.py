"""
Unit tests for file operations.
Uses tmp_path (pytest fixture) – no real system paths modified.
"""
import zipfile
import pytest
from pathlib import Path

from assistant.automation.file_ops import (
    create_folder, delete_file, move_file, copy_file,
    rename_file, search_files, zip_files, extract_archive,
)


@pytest.mark.asyncio
async def test_create_folder(tmp_path):
    target = tmp_path / "test_dir" / "nested"
    result = await create_folder(str(target))
    assert target.exists()
    assert "created" in result.lower() or str(target) in result


@pytest.mark.asyncio
async def test_delete_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    result = await delete_file(str(f))
    assert not f.exists()
    assert "deleted" in result.lower()


@pytest.mark.asyncio
async def test_delete_file_not_found(tmp_path):
    result = await delete_file(str(tmp_path / "nonexistent.txt"))
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_move_file(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("data")
    await move_file(str(src), str(dst))
    assert not src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_copy_file(tmp_path):
    src = tmp_path / "orig.txt"
    dst = tmp_path / "copy.txt"
    src.write_text("data")
    await copy_file(str(src), str(dst))
    assert src.exists()
    assert dst.exists()


@pytest.mark.asyncio
async def test_rename_file(tmp_path):
    src = tmp_path / "old.txt"
    src.write_text("x")
    await rename_file(str(src), "new.txt")
    assert (tmp_path / "new.txt").exists()
    assert not src.exists()


@pytest.mark.asyncio
async def test_search_files(tmp_path):
    (tmp_path / "hello_world.txt").write_text("hi")
    (tmp_path / "other.txt").write_text("other")
    result = await search_files("hello_world", str(tmp_path))
    assert "hello_world" in result


@pytest.mark.asyncio
async def test_zip_and_extract(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("zip me")
    archive = str(tmp_path / "out.zip")
    await zip_files([str(f)], archive)
    assert Path(archive).exists()

    extract_dir = tmp_path / "extracted"
    await extract_archive(archive, str(extract_dir))
    assert (extract_dir / "file.txt").exists()
