"""
Google Drive Backup Engine for the File Backup GUI application.
Extends the BackupEngine to support Google Drive as a backup destination.
"""

import time
import datetime
import threading
import logging

# Local imports
from backup_engine import BackupEngine
from models import BackupJob, FileMetadata, DestinationType
from file_scanner import FileScanner, needs_backup
from google_drive import GoogleDriveClient

# Configure logging
logger = logging.getLogger(__name__)


class GoogleDriveBackupEngine(BackupEngine):
    """Handles backup operations to Google Drive"""

    def __init__(self, db_session, credentials_file=None, token_file=None, session_factory=None):
        """Initialize the Google Drive backup engine"""
        super().__init__(db_session, session_factory)
        self.google_drive = GoogleDriveClient(credentials_file, token_file)
        self.authenticated = False

    def authenticate(self):
        """Authenticate with Google Drive"""
        return self.google_drive.authenticate()

    def backup_file_to_drive(self, file_data, folder_id, source_base):
        """Backup a single file to Google Drive"""
        try:
            source_path = file_data['path']
            
            # Upload the file to Google Drive
            result = self.google_drive.upload_file(
                file_path=source_path,
                parent_id=folder_id,
                preserve_path=True,
                base_path=source_base
            )
            
            if result:
                return {
                    'success': True,
                    'source': source_path,
                    'destination': f"Google Drive: {result.get('name', 'Unknown')}",
                    'file_data': file_data,
                    'drive_file_id': result.get('id')
                }
            else:
                return {
                    'success': False,
                    'source': source_path,
                    'error': "Failed to upload to Google Drive"
                }
                
        except Exception as e:
            logger.error(f"Error backing up file {file_data['path']} to Google Drive: {e}")
            return {
                'success': False,
                'source': file_data['path'],
                'error': str(e)
            }

    def process_drive_file_list(self, file_list, job_id, source_base, folder_id):
        """Process a list of files for backup to Google Drive"""
        results = []
        
        # Process files sequentially for Google Drive
        for file_data in file_list:
            if not self.running or self.paused:
                break
                
            self.current_file = file_data['path']
            result = self.backup_file_to_drive(file_data, folder_id, source_base)
            results.append(result)
            self.processed_files += 1
            
            # If backup was successful, update the database
            if result['success'] and not self.paused:
                self._update_file_metadata(job_id, file_data, result['source'])
        
        return results

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
            destination_type = job.destination_type

            # Scan for files to backup
            files_to_backup = []
            scanned_files, scan_errors = FileScanner.scan_directory(source_path)
            if scan_errors:
                logger.warning(f"{len(scan_errors)} paths could not be read during scan")

            # Check which files need to be backed up
            for file_data in scanned_files:
                file_meta = session.query(FileMetadata).filter_by(
                    job_id=job_id,
                    file_path=file_data['path']
                ).first()

                if needs_backup(file_meta, file_data, dest_file=None):
                    files_to_backup.append(file_data)

            self.total_files = len(files_to_backup)

            # Close the session before starting the backup process
            session.close()

            # If no files need backup, we're done
            if not files_to_backup:
                self.running = False
                if callback:
                    callback(True, "No files need backup")
                return True

            # Start the backup process in a separate thread
            if destination_type == DestinationType.GOOGLE_DRIVE:
                # For Google Drive, we need to authenticate first
                if not self.google_drive.authenticated:
                    if not self.google_drive.authenticate():
                        self.running = False
                        if callback:
                            callback(False, "Failed to authenticate with Google Drive")
                        return False
                
                # Start Google Drive backup thread
                threading.Thread(
                    target=self._run_drive_backup_thread,
                    args=(files_to_backup, job_id, source_path, job.google_drive_folder_id, callback),
                    daemon=True
                ).start()
            else:
                # For local backup, use the parent class method
                threading.Thread(
                    target=self._run_backup_thread,
                    args=(files_to_backup, job_id, source_path, destination_path, callback),
                    daemon=True
                ).start()

            return True

        except Exception as e:
            logger.error(f"Error starting backup job: {e}")
            session.close()
            self.running = False
            if callback:
                callback(False, str(e))
            return False

    def _run_drive_backup_thread(self, files_list, job_id, source_path, folder_id, callback):
        """Run the Google Drive backup process in a separate thread"""
        try:
            # Process files for Google Drive
            results = self.process_drive_file_list(files_list, job_id, source_path, folder_id)

            # Count successes and failures
            successes = sum(1 for r in results if r['success'])
            failures = len(results) - successes

            # Update job's last backup time
            session = self.Session()
            job = session.get(BackupJob, job_id)
            if job:
                job.last_backup = datetime.datetime.now()
                session.commit()
            session.close()

            # Call the callback with results
            if callback:
                callback(True, f"Google Drive backup completed: {successes} files backed up, {failures} failures")

        except Exception as e:
            logger.error(f"Error in Google Drive backup thread: {e}")
            if callback:
                callback(False, str(e))
        finally:
            self.running = False
