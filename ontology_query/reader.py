from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class VaultReader(Protocol):
    def read_file(self, path: str) -> str: ...
    def list_files(self, folder: str) -> list[str]: ...
    def file_exists(self, path: str) -> bool: ...


class LocalVaultReader:
    def __init__(self, vault_path: Path) -> None:
        self._root = vault_path

    def read_file(self, path: str) -> str:
        return (self._root / path).read_text(encoding="utf-8")

    def list_files(self, folder: str) -> list[str]:
        folder_path = self._root / folder
        if not folder_path.is_dir():
            return []
        return sorted(
            str(p.relative_to(self._root))
            for p in folder_path.iterdir()
            if p.is_file() and p.suffix == ".md"
        )

    def file_exists(self, path: str) -> bool:
        return (self._root / path).is_file()


class S3VaultReader:
    """Production reader — reads vault from S3. Requires boto3 s3_client injection."""

    def __init__(self, s3_client, bucket: str, prefix: str = "ontology/_base") -> None:
        self._s3 = s3_client
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")

    def _key(self, path: str) -> str:
        return f"{self._prefix}/{path}"

    def read_file(self, path: str) -> str:
        resp = self._s3.get_object(Bucket=self._bucket, Key=self._key(path))
        return resp["Body"].read().decode("utf-8")

    def list_files(self, folder: str) -> list[str]:
        prefix = f"{self._key(folder)}/"
        paginator = self._s3.get_paginator("list_objects_v2")
        files: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".md"):
                    rel = key[len(self._prefix) + 1 :]
                    files.append(rel)
        return sorted(files)

    def file_exists(self, path: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=self._key(path))
            return True
        except self._s3.exceptions.ClientError:
            return False
