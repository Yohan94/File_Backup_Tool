"""
Google Drive integration module for the File Backup GUI application.
Handles authentication and file operations with Google Drive.
"""

import os
import pickle
import logging
import mimetypes
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from models import get_app_data_dir

# Configure logging
logger = logging.getLogger(__name__)

# Define the scopes needed for Google Drive access
# Using read/write scope to allow file uploads
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveClient:
    """Client for interacting with Google Drive API"""
    
    def __init__(self, credentials_file=None, token_file=None):
        """
        Initialize the Google Drive client.
        
        Args:
            credentials_file (str): Path to the credentials.json file
            token_file (str): Path to store the token.pickle file
        """
        self.credentials_file = credentials_file or 'credentials.json'
        self.token_file = token_file or str(get_app_data_dir() / 'token.pickle')
        self.credentials = None
        self.service = None
        self.authenticated = False
    
    def authenticate(self):
        """
        Authenticate with Google Drive API.
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        try:
            # Check if we have a token.pickle file with credentials
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    self.credentials = pickle.load(token)
            
            # If credentials don't exist or are invalid, get new ones
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    # Refresh credentials if expired
                    self.credentials.refresh(Request())
                else:
                    # Get new credentials if none exist
                    if not os.path.exists(self.credentials_file):
                        logger.error(f"Credentials file not found: {self.credentials_file}")
                        return False
                    
                    # Create the flow using the client secrets file
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(self.token_file, 'wb') as token:
                    pickle.dump(self.credentials, token)
            
            # Build the Drive service
            self.service = build('drive', 'v3', credentials=self.credentials)
            self.authenticated = True
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            self.authenticated = False
            return False
    
    def list_folders(self, parent_id='root'):
        """
        List folders in Google Drive.
        
        Args:
            parent_id (str): ID of the parent folder to list contents from
            
        Returns:
            list: List of folder dictionaries with 'id' and 'name' keys
        """
        if not self.authenticated:
            if not self.authenticate():
                return []
        
        try:
            # Query for folders
            query = f"mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            return results.get('files', [])
        
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []
    
    def create_folder(self, folder_name, parent_id='root'):
        """
        Create a folder in Google Drive.
        
        Args:
            folder_name (str): Name of the folder to create
            parent_id (str): ID of the parent folder
            
        Returns:
            str: ID of the created folder, or None if failed
        """
        if not self.authenticated:
            if not self.authenticate():
                return None
        
        try:
            # Create folder metadata
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            # Create the folder
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
        
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return None
    
    def upload_file(self, file_path, parent_id='root', preserve_path=False, base_path=None):
        """
        Upload a file to Google Drive.
        
        Args:
            file_path (str): Path to the file to upload
            parent_id (str): ID of the parent folder
            preserve_path (bool): Whether to preserve the directory structure
            base_path (str): Base path to use for relative path calculation
            
        Returns:
            dict: File metadata if successful, None otherwise
        """
        if not self.authenticated:
            if not self.authenticate():
                return None
        
        try:
            file_path = Path(file_path)
            
            # If preserving path structure, create necessary folders
            if preserve_path and base_path:
                parent_id = self._ensure_path_exists(file_path, parent_id, base_path)
            
            # Get the MIME type of the file
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # Create file metadata
            file_metadata = {
                'name': file_path.name,
                'parents': [parent_id]
            }
            
            # Create media
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload the file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType, size'
            ).execute()
            
            return file
        
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            return None
    
    def _ensure_path_exists(self, file_path, parent_id, base_path):
        """
        Ensure the directory structure exists in Google Drive.
        
        Args:
            file_path (Path): Path to the file
            parent_id (str): ID of the parent folder
            base_path (str): Base path to use for relative path calculation
            
        Returns:
            str: ID of the deepest folder in the path
        """
        # Calculate relative path
        base_path = Path(base_path)
        rel_path = file_path.relative_to(base_path).parent
        
        # If no subdirectories, return the parent_id
        if str(rel_path) == '.':
            return parent_id
        
        # Create each directory in the path if it doesn't exist
        current_parent_id = parent_id
        for part in rel_path.parts:
            # Check if folder exists
            folders = self.list_folders(current_parent_id)
            folder_exists = False
            
            for folder in folders:
                if folder['name'] == part:
                    current_parent_id = folder['id']
                    folder_exists = True
                    break
            
            # Create folder if it doesn't exist
            if not folder_exists:
                new_id = self.create_folder(part, current_parent_id)
                if new_id:
                    current_parent_id = new_id
                else:
                    # If folder creation fails, return the last valid parent
                    return current_parent_id
        
        return current_parent_id
