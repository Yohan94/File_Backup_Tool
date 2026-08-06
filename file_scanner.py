# file_scanner.py
import os
import hashlib
import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

# FAT/exFAT store mtime at 2-second granularity; network shares round too.
MTIME_TOLERANCE = datetime.timedelta(seconds=2)


def needs_backup(file_meta, file_data, dest_file):
    """Single source of truth for 'does this file need copying?'"""
    if file_meta is None:
        return True                                   # never backed up
    if file_meta.size != file_data['size']:
        return True                                   # size changed
    if file_meta.modified_time is None:
        return True
    if abs(file_meta.modified_time - file_data['modified_time']) > MTIME_TOLERANCE:
        return True                                   # mtime moved either way
    if dest_file is not None and not os.path.exists(dest_file):
        return True                                   # destination lost the file
    return False


class FileScanner:
    """Handles file scanning and comparison operations"""

    @staticmethod
    def get_file_hash(file_path):
        """Calculate MD5 hash of a file"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                chunk = f.read(8192)
                while chunk:
                    file_hash.update(chunk)
                    chunk = f.read(8192)
            return file_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    @staticmethod
    def scan_directory(directory_path):
        """Scan a directory and return (files_data, errors).

        Callers MUST report a non-empty errors list — otherwise a permission
        error or a directory os.walk can't open silently shrinks the backup
        set with no user-visible sign.
        """
        files_data, errors = [], []
        for root, _, files in os.walk(directory_path, onerror=lambda e: errors.append(str(e))):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    files_data.append({
                        'path': file_path,
                        'modified_time': datetime.datetime.fromtimestamp(stat.st_mtime),
                        'size': stat.st_size
                    })
                except OSError as e:
                    errors.append(f"{file_path}: {e}")
        return files_data, errors
