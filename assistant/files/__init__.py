"""
File operations are handled by assistant.automation.file_ops.
This package re-exports them for convenience.
"""
from assistant.automation.file_ops import (
    read_file_content,
    search_files,
    create_folder,
    delete_file,
    move_file,
    copy_file,
    rename_file,
    zip_files,
    extract_archive,
    empty_recycle_bin,
)

__all__ = [
    "read_file_content", "search_files", "create_folder",
    "delete_file", "move_file", "copy_file", "rename_file",
    "zip_files", "extract_archive", "empty_recycle_bin",
]
