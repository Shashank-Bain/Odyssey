import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobClient, ContainerClient
from flask import Flask

logger = logging.getLogger(__name__)


@dataclass
class BlobSqliteSync:
    database_uri: str
    local_db_path: Path
    blob_client: BlobClient
    sync_interval_seconds: float = 5.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._last_uploaded_mtime = 0.0
        self._last_uploaded_at = 0.0

    def ensure_local_from_blob(self) -> None:
        """Download the DB from blob only when local file is not present."""
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.local_db_path.exists():
            return

        try:
            with self.local_db_path.open("wb") as local_file:
                stream = self.blob_client.download_blob()
                stream.readinto(local_file)
            logger.info("Downloaded SQLite DB from Azure Blob: %s", self.blob_client.blob_name)
        except ResourceNotFoundError:
            logger.info("Blob DB not found yet; a new local SQLite DB will be created.")

    def upload_if_changed(self, force: bool = False) -> bool:
        if not self.local_db_path.exists():
            return False

        with self._lock:
            mtime = self.local_db_path.stat().st_mtime
            now = time.time()

            if not force:
                if mtime <= self._last_uploaded_mtime:
                    return False
                if now - self._last_uploaded_at < self.sync_interval_seconds:
                    return False

            with self.local_db_path.open("rb") as db_file:
                self.blob_client.upload_blob(db_file, overwrite=True)

            self._last_uploaded_mtime = mtime
            self._last_uploaded_at = now
            logger.info("Uploaded SQLite DB to Azure Blob: %s", self.blob_client.blob_name)
            return True


def _build_local_sqlite_path() -> Path:
    configured_path = os.getenv("ODYSSEY_LOCAL_DB_PATH", "").strip()
    if configured_path:
        return Path(configured_path)

    if os.name == "nt":
        return Path.cwd() / ".data" / "odyssey.db"

    # Azure App Service on Linux has persistent storage under /home.
    return Path("/home/odyssey-data/odyssey.db")


def build_blob_sqlite_sync(app: Flask) -> BlobSqliteSync | None:
    connection_string = os.getenv("ODYSSEY_BLOB_CONNECTION_STRING", "").strip()
    container = os.getenv("ODYSSEY_BLOB_CONTAINER", "").strip()
    blob_name = os.getenv("ODYSSEY_BLOB_NAME", "odyssey.db").strip() or "odyssey.db"

    if not connection_string or not container:
        return None

    local_db_path = _build_local_sqlite_path()
    blob_client = BlobClient.from_connection_string(
        conn_str=connection_string,
        container_name=container,
        blob_name=blob_name,
    )
    container_client = ContainerClient.from_connection_string(
        conn_str=connection_string,
        container_name=container,
    )
    try:
        container_client.create_container()
        app.logger.info("Created Azure Blob container: %s", container)
    except ResourceExistsError:
        pass

    sync_interval = os.getenv("ODYSSEY_BLOB_SYNC_INTERVAL_SECONDS", "5").strip()
    try:
        sync_interval_seconds = float(sync_interval)
    except ValueError:
        sync_interval_seconds = 5.0

    app.logger.info(
        "Using Blob-backed SQLite DB. container=%s blob=%s local_path=%s",
        container,
        blob_name,
        local_db_path,
    )

    return BlobSqliteSync(
        database_uri=f"sqlite:///{local_db_path.as_posix()}",
        local_db_path=local_db_path,
        blob_client=blob_client,
        sync_interval_seconds=sync_interval_seconds,
    )
