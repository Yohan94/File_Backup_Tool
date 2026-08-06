import datetime, os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, BackupJob, FileMetadata
from backup_engine import BackupEngine
from file_scanner import FileScanner, needs_backup


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_needs_backup_new_file():
    fd = {'path': 'x', 'modified_time': datetime.datetime.now(), 'size': 10}
    assert needs_backup(None, fd, None) is True


def test_needs_backup_size_change():
    now = datetime.datetime.now()
    meta = type('M', (), {'size': 10, 'modified_time': now})()
    assert needs_backup(meta, {'path': 'x', 'modified_time': now, 'size': 20}, None)


def test_needs_backup_within_mtime_tolerance():
    now = datetime.datetime.now()
    meta = type('M', (), {'size': 10, 'modified_time': now})()
    fd = {'path': 'x', 'modified_time': now + datetime.timedelta(seconds=1), 'size': 10}
    assert needs_backup(meta, fd, None) is False


def test_needs_backup_mtime_moved_backward():
    now = datetime.datetime.now()
    meta = type('M', (), {'size': 10, 'modified_time': now})()
    fd = {'path': 'x', 'modified_time': now - datetime.timedelta(days=1), 'size': 10}
    assert needs_backup(meta, fd, None) is True


def test_needs_backup_destination_missing(tmp_path):
    now = datetime.datetime.now()
    meta = type('M', (), {'size': 10, 'modified_time': now})()
    fd = {'path': 'x', 'modified_time': now, 'size': 10}
    missing_dest = str(tmp_path / "does-not-exist.txt")
    assert needs_backup(meta, fd, missing_dest) is True


def test_scan_reports_errors(tmp_path):
    files, errors = FileScanner.scan_directory(tmp_path / "does-not-exist")
    assert files == [] and errors  # must not silently return empty


def test_end_to_end_copy(tmp_path, session_factory):
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "sub").mkdir(parents=True); dst.mkdir()
    (src / "a.txt").write_text("hello")
    (src / "sub" / "b.txt").write_text("world")

    s = session_factory()
    job = BackupJob(name="t", source_path=str(src), destination_path=str(dst))
    s.add(job); s.commit()
    job_id = job.id; s.close()

    done = []
    eng = BackupEngine(session_factory(), session_factory)
    eng.run_backup_job(job_id, callback=lambda ok, msg: done.append((ok, msg)))

    import time
    for _ in range(100):
        if done: break
        time.sleep(0.1)

    assert done and done[0][0] is True
    assert (dst / "a.txt").read_text() == "hello"
    assert (dst / "sub" / "b.txt").read_text() == "world"

    s = session_factory()
    assert s.query(FileMetadata).filter_by(job_id=job_id).count() == 2


def test_second_run_needs_no_backup(tmp_path, session_factory):
    src, dst = tmp_path / "src2", tmp_path / "dst2"
    src.mkdir(); dst.mkdir()
    (src / "a.txt").write_text("hello")

    s = session_factory()
    job = BackupJob(name="t2", source_path=str(src), destination_path=str(dst))
    s.add(job); s.commit()
    job_id = job.id; s.close()

    import time

    done = []
    eng = BackupEngine(session_factory(), session_factory)
    eng.run_backup_job(job_id, callback=lambda ok, msg: done.append((ok, msg)))
    for _ in range(100):
        if done: break
        time.sleep(0.1)
    assert done and done[0][0] is True

    done2 = []
    eng2 = BackupEngine(session_factory(), session_factory)
    eng2.run_backup_job(job_id, callback=lambda ok, msg: done2.append((ok, msg)))
    for _ in range(100):
        if done2: break
        time.sleep(0.1)

    assert done2 and done2[0][0] is True
    assert "No files need backup" in done2[0][1]


def test_cancelled_run_reports_failure_path(tmp_path, session_factory):
    src, dst = tmp_path / "src3", tmp_path / "dst3"
    src.mkdir(); dst.mkdir()
    for i in range(20):
        (src / f"f{i}.txt").write_text("x" * 1000)

    s = session_factory()
    job = BackupJob(name="t3", source_path=str(src), destination_path=str(dst))
    s.add(job); s.commit()
    job_id = job.id; s.close()

    import time

    done = []
    eng = BackupEngine(session_factory(), session_factory)
    eng.run_backup_job(job_id, callback=lambda ok, msg: done.append((ok, msg)))
    eng.cancel_backup()
    for _ in range(100):
        if done: break
        time.sleep(0.1)

    assert done
    # Either it finished before cancellation was observed, or it reports cancellation honestly.
    assert done[0][0] is True or "cancel" in done[0][1].lower()
