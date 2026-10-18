"""The files kept for records, behind a small interface (dependency inversion).

`file_store()` is what the attachments module saves and reads with; `set_store_factory(...)` stands in
for the disk in tests. See `store` for where a self-hosted deployment keeps the files, and why.
"""

from .store import FileStore, FileStoreError, LocalFileStore, file_store, set_store_factory

__all__ = ["FileStore", "FileStoreError", "LocalFileStore", "file_store", "set_store_factory"]
