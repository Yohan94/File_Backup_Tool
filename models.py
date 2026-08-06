# models.py
#
# Session ownership:
#   * `BackupApp.db_session` belongs to the Tk main thread. Only UI code touches it.
#   * Any worker thread MUST create its own session via `self.Session()` and
#     close it in a `finally`.
#   * ORM instances never cross a thread boundary — pass primary keys instead.
import datetime
import os
import shutil
import logging
from pathlib import Path
from sqlalchemy import (create_engine, Column, Integer, String, DateTime, Boolean,
                         ForeignKey, Enum, UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

logger = logging.getLogger(__name__)

# Create declarative base using updated import path
Base = declarative_base()


class DestinationType(enum.Enum):
    """Enum for backup destination types"""
    LOCAL = "local"
    GOOGLE_DRIVE = "google_drive"


class BackupJob(Base):
    __tablename__ = 'backup_jobs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    source_path = Column(String(1024), nullable=False)
    destination_path = Column(String(1024), nullable=False)
    destination_type = Column(Enum(DestinationType), default=DestinationType.LOCAL, nullable=False)
    google_drive_folder_id = Column(String(255), nullable=True)
    last_backup = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    files = relationship("FileMetadata", back_populates="job", cascade="all, delete-orphan")
    batch_items = relationship("BatchItem", back_populates="job", cascade="all, delete-orphan")


class FileMetadata(Base):
    __tablename__ = 'file_metadata'
    __table_args__ = (
        UniqueConstraint('job_id', 'file_path', name='uq_file_metadata_job_path'),
    )

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('backup_jobs.id'))
    file_path = Column(String(1024), nullable=False)
    file_hash = Column(String(64), nullable=True)
    modified_time = Column(DateTime, nullable=False)
    size = Column(Integer, nullable=False)
    last_backup = Column(DateTime, nullable=True)

    job = relationship("BackupJob", back_populates="files")


class BatchJob(Base):
    __tablename__ = 'batch_jobs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    created_date = Column(DateTime, nullable=False, default=datetime.datetime.now)
    last_run = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    items = relationship("BatchItem", back_populates="batch", cascade="all, delete-orphan")


class BatchItem(Base):
    __tablename__ = 'batch_items'

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('batch_jobs.id'))
    job_id = Column(Integer, ForeignKey('backup_jobs.id'))
    is_enabled = Column(Boolean, default=True)
    order = Column(Integer, default=0)

    batch = relationship("BatchJob", back_populates="items")
    job = relationship("BackupJob", back_populates="batch_items")


class GoogleDriveSettings(Base):
    """Settings for Google Drive integration"""
    __tablename__ = 'google_drive_settings'

    id = Column(Integer, primary_key=True)
    credentials_file = Column(String(1024), nullable=True)
    token_file = Column(String(1024), nullable=True)
    is_authenticated = Column(Boolean, default=False)
    last_authenticated = Column(DateTime, nullable=True)


class AppSetting(Base):
    """Simple key/value store for persisted app settings (theme, worker count, ...)"""
    __tablename__ = 'app_settings'

    key = Column(String(64), primary_key=True)
    value = Column(String(1024), nullable=True)


def get_setting(session, key, default=None):
    row = session.get(AppSetting, key)
    return row.value if row and row.value is not None else default


def set_setting(session, key, value):
    row = session.get(AppSetting, key)
    if row:
        row.value = str(value)
    else:
        session.add(AppSetting(key=key, value=str(value)))
    session.commit()


def get_app_data_dir() -> Path:
    """Per-user writable directory, stable across cwd and frozen (PyInstaller) builds.

    Do NOT use Path(__file__).parent instead — under --onefile that resolves
    into the temporary extraction directory, which is deleted on exit.
    """
    base = os.environ.get("LOCALAPPDATA") or Path.home()
    d = Path(base) / "SmartBackupTool"
    d.mkdir(parents=True, exist_ok=True)
    return d


DB_PATH = get_app_data_dir() / "backup_app.db"


# Database setup
def init_database():
    # One-time move so existing users (whose db lived next to the script,
    # cwd-relative) keep their history.
    legacy = Path.cwd() / "backup_app.db"
    if legacy.exists() and not DB_PATH.exists():
        try:
            shutil.move(str(legacy), str(DB_PATH))
            logger.info(f"Migrated database from {legacy} to {DB_PATH}")
        except OSError as e:
            logger.error(f"Could not migrate legacy database: {e}")

    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
