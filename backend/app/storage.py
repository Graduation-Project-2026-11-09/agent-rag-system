"""資料の原本ファイルの保存先。AWS では S3、開発環境ではローカルのフォルダを使う。"""

from pathlib import Path
from typing import Protocol

from flask import current_app


class FileStorage(Protocol):
    """原本ファイルの保存先が持つ操作。"""

    def save(self, key: str, data: bytes) -> None:
        """key の場所に data を保存する（同じ key があれば上書きする）。"""
        ...

    def load(self, key: str) -> bytes:
        """key の場所のファイルの内容を返す。"""
        ...

    def delete(self, key: str) -> None:
        """key の場所のファイルを削除する。なければ何もしない。"""
        ...


class LocalFileStorage:
    """ローカルのフォルダに保存する（開発環境・テスト用）。"""

    def __init__(self, root: str) -> None:
        """root: 保存先のフォルダ。"""
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        """key を保存先のフォルダの中のパスにする。"""
        path = (self._root / key).resolve()
        # キーに「..」を含めて保存先の外を読み書きされないようにする
        if not path.is_relative_to(self._root):
            raise ValueError(f"不正な保存先のキーです: {key}")
        return path

    def save(self, key: str, data: bytes) -> None:
        """FileStorage.save と同じ。"""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        """FileStorage.load と同じ。"""
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        """FileStorage.delete と同じ。"""
        self._path(key).unlink(missing_ok=True)


class S3FileStorage:
    """S3 のバケットに保存する（AWS 用）。暗号化とバージョニングはバケット側で設定している。"""

    def __init__(self, bucket: str, region: str | None = None) -> None:
        """bucket: 保存先のバケット名。region: バケットのリージョン。"""
        import boto3

        self._bucket = bucket
        self._client = boto3.client("s3", region_name=region or None)

    def save(self, key: str, data: bytes) -> None:
        """FileStorage.save と同じ。"""
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def load(self, key: str) -> bytes:
        """FileStorage.load と同じ。"""
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        """FileStorage.delete と同じ（S3 は存在しないキーを削除してもエラーにならない）。"""
        self._client.delete_object(Bucket=self._bucket, Key=key)


def get_storage() -> FileStorage:
    """設定に応じた保存先を返す。

    Returns:
        DOCUMENTS_BUCKET が設定されていれば S3、なければ DOCUMENTS_DIR のフォルダ。
    """
    config = current_app.config
    if config["DOCUMENTS_BUCKET"]:
        return S3FileStorage(config["DOCUMENTS_BUCKET"], config["AWS_REGION"])
    return LocalFileStorage(config["DOCUMENTS_DIR"])
