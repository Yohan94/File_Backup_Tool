# backup_engine.py
import os
import shutil
import time
import datetime
import threading
import multiprocessing
from multiprocessing import Pool
import logging

# Local imports
from models import FileMetadata, BackupJob
from file_scanner import FileScanner, needs_backup

# Configure logging
logger = logging.getLogger(__name__)


def _long_path(p):
    """Work around shutil.copy2 failing past MAX_PATH (260 chars) on Windows."""
    p = os.path.abspath(p)
    if os.name == "nt" and not p.startswith("\\\\?\\"):
        return "\\\\?\\" + p
    return p


def _backup_file_worker(args):
    """Module-level so it pickles cleanly under Windows spawn."""
    file_data, destination_base, source_base = args
    source_path = file_data['path']
    try:
        rel_path = os.path.relpath(source_path, source_base)
        dest_path = os.path.join(destination_base, rel_path)
        os.makedirs(_long_path(os.path.dirname(dest_path)), exist_ok=True)
        shutil.copy2(_long_path(source_path), _long_path(dest_path))
        return {'success': True, 'source': source_path,
                'destination': dest_path, 'file_data': file_data}
    except Exception as e:
        return {'success': False, 'source': source_path,
                'file_data': file_data, 'error': str(e)}


class BackupEngine:
    """Handles the backup process using parallel processing"""

    def __init__(self, db_session, session_factory=None):
        self.db_session = db_session
        self.running = False
        self.paused = False
        self.total_files = 0
        self.scanned_files_count = 0
        self.processed_files = 0
        self.current_file = ""
        self.start_time = None
        self.max_workers = max(1, multiprocessing.cpu_count() - 1)
        self.verify_copies = False

        # Store the session factory for creating new sessions in threads
        if session_factory is None:
            from models import init_database
            _, self.Session = init_database()
        else:
            self.Session = session_factory

    def process_file_list(self, file_list, job_id, source_base, destination_base):
        """Process a list of files for backup with multiprocessing"""
        results = []
        args_list = [(fd, destination_base, source_base) for fd in file_list]
        workers = max(1, min(self.max_workers, len(args_list)))

        pool = Pool(processes=workers)
        try:
            for result in pool.imap_unordered(_backup_file_worker, args_list, chunksize=8):
                results.append(result)
                self.processed_files += 1
                self.current_file = result['source']

                if result['success']:
                    self._update_file_metadata(job_id, result['file_data'],
                                               result['destination'])
                else:
                    logger.error(f"Backup failed for {result['source']}: "
                                 f"{result.get('error')}")

                while self.paused and self.running:
                    time.sleep(0.2)
                if not self.running:            # cancelled
                    logger.info("Backup cancelled by user")
                    break
        finally:
            pool.terminate()                    # kills workers on both paths
            pool.join()
        return results

    def _update_file_metadata(self, job_id, file_data, destination_path):
        """Update file metadata in the database"""
        session = self.Session()
        try:
            # Check if file already exists in database
            file_meta = session.query(FileMetadata).filter_by(
                job_id=job_id,
                file_path=file_data['path']
            ).first()

            file_hash = FileScanner.get_file_hash(destination_path) if self.verify_copies else None

            if file_meta:
                # Update existing record
                file_meta.modified_time = file_data['modified_time']
                file_meta.size = file_data['size']
                file_meta.file_hash = file_hash
                file_meta.last_backup = datetime.datetime.now()
            else:
                # Create new record
                file_meta = FileMetadata(
                    job_id=job_id,
                    file_path=file_data['path'],
                    file_hash=file_hash,
                    modified_time=file_data['modified_time'],
                    size=file_data['size'],
                    last_backup=datetime.datetime.now()
                )
                session.add(file_meta)

            # Update job last backup time
            job = session.get(BackupJob, job_id)
            if job:
                job.last_backup = datetime.datetime.now()

            session.commit()
        except Exception as e:
            logger.error(f"Error updating file metadata: {e}")
            session.rollback()
        finally:
            session.close()

    def run_backup_job(self, job_id, callback=None):
        """Run a backup job with the given ID"""
        if self.running:
            return False

        self.running = True
        self.paused = False
        self.processed_files = 0
        self.current_file = ""
        self.start_time = time.time()

        session = self.Session()
        try:
            # Get job details
            job = session.get(BackupJob, job_id)
            if not job:
                logger.error(f"Backup job with ID {job_id} not found")
                self.running = False
                if callback:
                    callback(False, f"Backup job {job_id} not found")
                return False

            source_path = job.source_path
            destination_path = job.destination_path

            # Check if source directory exists
            if not os.path.exists(source_path):
                logger.error(f"Source directory not found: {source_path}")
                self.running = False
                if callback:
                    callback(False, f"Error: Source directory not found: {source_path}")
                return False

            # Check if destination directory is available
            if not os.path.exists(destination_path):
                logger.error(f"Destination directory not available: {destination_path}")
                self.running = False
                if callback:
                    callback(False, f"Error: Destination directory not available. Please ensure the external drive is connected.")
                return False

            # Scan for files to backup
            scanned_files, scan_errors = FileScanner.scan_directory(source_path)
            if scan_errors:
                logger.warning(f"{len(scan_errors)} paths could not be read during scan")
                for err in scan_errors[:10]:
                    logger.warning(f"  scan error: {err}")

            self.scanned_files_count = len(scanned_files)

            # Check which files need to be backed up
            files_to_backup = []
            for file_data in scanned_files:
                file_meta = session.query(FileMetadata).filter_by(
                    job_id=job_id,
                    file_path=file_data['path']
                ).first()

                rel_path = os.path.relpath(file_data['path'], source_path)
                dest_file = os.path.join(destination_path, rel_path)

                if needs_backup(file_meta, file_data, dest_file):
                    files_to_backup.append(file_data)

            self.total_files = len(files_to_backup)   # the progress denominator

            # If no files need backup, we're done
            if not files_to_backup:
                self.running = False
                if callback:
                    msg = "No files need backup"
                    if scan_errors:
                        msg += f" (warning: {len(scan_errors)} paths unreadable — see backup_app.log)"
                    callback(True, msg)
                return True

            # Start the backup process in a separate thread
            threading.Thread(
                target=self._run_backup_thread,
                args=(files_to_backup, job_id, source_path, destination_path, callback, scan_errors),
                daemon=True
            ).start()

            return True

        except Exception as e:
            logger.error(f"Error starting backup job: {e}")
            self.running = False
            if callback:
                callback(False, str(e))
            return False
        finally:
            session.close()

    def _run_backup_thread(self, files_list, job_id, source_path, destination_path, callback, scan_errors=None):
        """Run the backup process in a separate thread"""
        try:
            # Process files in parallel
            results = self.process_file_list(files_list, job_id, source_path, destination_path)

            # Count successes and failures
            successes = sum(1 for r in results if r['success'])
            failures = len(results) - successes

            for r in [r for r in results if not r['success']][:10]:
                logger.error(f"  failed: {r['source']}: {r.get('error')}")

            # Update job's last backup time
            session = self.Session()
            try:
                job = session.get(BackupJob, job_id)
                if job:
                    job.last_backup = datetime.datetime.now()
                    session.commit()
            finally:
                session.close()

            cancelled = not self.running and self.processed_files < self.total_files
            warning_suffix = ""
            if scan_errors:
                warning_suffix = f" ({len(scan_errors)} paths unreadable during scan — see backup_app.log)"

            if cancelled:
                summary = (f"Backup cancelled: {successes} copied, {failures} failed, "
                           f"{self.total_files - self.processed_files} skipped")
            elif failures:
                summary = f"Backup finished with errors: {successes} copied, {failures} failed"
            else:
                summary = f"Backup completed: {successes} files backed up"
            summary += warning_suffix

            # Call the callback with results
            if callback:
                callback(failures == 0 and not cancelled, summary)

        except Exception as e:
            logger.error(f"Error in backup thread: {e}")
            if callback:
                callback(False, str(e))
        finally:
            self.running = False

    def pause_backup(self):
        """Pause the current backup operation"""
        self.paused = True

    def resume_backup(self):
        """Resume the current backup operation"""
        self.paused = False

    def cancel_backup(self):
        """Cancel the current backup operation"""
        self.running = False
        self.paused = False
