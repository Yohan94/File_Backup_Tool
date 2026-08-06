# Google Drive Backup Integration - Step by Step Guide

## Overview
This guide explains how to integrate Google Drive backup into your File Backup GUI application. The system allows you to backup files directly to Google Drive instead of (or in addition to) local destinations.

---

## Step 1: Prerequisites & Setup

### 1.1 Install Required Python Packages
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

These packages are needed for:
- `google-auth`: Authentication with Google
- `google-auth-oauthlib`: OAuth 2.0 flow
- `google-api-python-client`: Google Drive API client

### 1.2 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project" or select existing project
3. Give it a name (e.g., "File Backup App")
4. Click "Create"

### 1.3 Enable Google Drive API

1. In Google Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google Drive API"
3. Click on it and press "Enable"

### 1.4 Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - User Type: External (for testing) or Internal (for organization)
   - App name: "File Backup GUI"
   - User support email: Your email
   - Developer contact: Your email
   - Click "Save and Continue"
   - Scopes: Click "Add or Remove Scopes" and add:
     - `https://www.googleapis.com/auth/drive.file`
   - Test users: Add your Google account email
   - Click "Save and Continue"

4. Back to Credentials:
   - Application type: "Desktop app"
   - Name: "File Backup GUI Desktop"
   - Click "Create"

5. Download the credentials:
   - Click the download icon (⬇) next to your OAuth 2.0 Client
   - Save as `credentials.json` in your project root directory

---

## Step 2: Understanding the Code Architecture

### 2.1 Key Files

```
File_Backup_GUI/
├── google_drive.py           # Google Drive API client wrapper
├── google_drive_backup_engine.py  # Backup engine for Google Drive
├── models.py                  # Database models (includes GoogleDriveSettings)
├── main.py                    # Main app (switches between engines)
└── ui/
    └── settings_tab.py        # UI for Google Drive authentication
```

### 2.2 How It Works

```
User Flow:
1. User uploads credentials.json via Settings tab
2. User clicks "Authenticate with Google Drive"
3. Browser opens for OAuth consent
4. User authorizes the app
5. Token is saved for future use
6. User creates a backup job with destination_type = GOOGLE_DRIVE
7. Backup engine uploads files to Google Drive instead of local folder
```

---

## Step 3: Database Models (Already Implemented)

### 3.1 GoogleDriveSettings Table
Located in `models.py`:

```python
class GoogleDriveSettings(Base):
    __tablename__ = 'google_drive_settings'

    id = Column(Integer, primary_key=True)
    credentials_file = Column(String(1024), nullable=True)  # Path to credentials.json
    token_file = Column(String(1024), nullable=True)        # Path to token.pickle
    is_authenticated = Column(Boolean, default=False)       # Auth status
    last_authenticated = Column(DateTime, nullable=True)    # Last auth time
```

### 3.2 BackupJob Table Enhancement
```python
class BackupJob(Base):
    __tablename__ = 'backup_jobs'

    # ... existing fields ...
    destination_type = Column(Enum(DestinationType), default=DestinationType.LOCAL)
    google_drive_folder_id = Column(String(255), nullable=True)  # Google Drive folder ID
```

---

## Step 4: Google Drive Client (google_drive.py)

### 4.1 Key Methods

**`authenticate()`**
- Checks if token.pickle exists (contains saved credentials)
- If expired, refreshes the token
- If no token, runs OAuth flow (opens browser)
- Saves token for next time

**`create_folder(folder_name, parent_id='root')`**
- Creates a folder in Google Drive
- Returns folder ID

**`upload_file(file_path, parent_id='root', preserve_path=False, base_path=None)`**
- Uploads a file to Google Drive
- If `preserve_path=True`, recreates the directory structure
- Returns file metadata

**`list_folders(parent_id='root')`**
- Lists folders in Google Drive
- Used to check if folder already exists

### 4.2 Authentication Flow

```python
from google_drive import GoogleDriveClient

# Initialize client
client = GoogleDriveClient(
    credentials_file='credentials.json',
    token_file='token.pickle'
)

# Authenticate (opens browser first time)
if client.authenticate():
    print("Authenticated successfully!")

    # Create a backup folder
    folder_id = client.create_folder("My Backups")

    # Upload a file
    result = client.upload_file(
        'C:/path/to/file.txt',
        parent_id=folder_id
    )
```

---

## Step 5: Google Drive Backup Engine

### 5.1 How It Extends BackupEngine

`GoogleDriveBackupEngine` inherits from `BackupEngine` and overrides file operations:

```python
class GoogleDriveBackupEngine(BackupEngine):
    def __init__(self, db_session, credentials_file=None, token_file=None, session_factory=None):
        super().__init__(db_session, session_factory)
        self.google_drive = GoogleDriveClient(credentials_file, token_file)
        self.authenticated = False

    def backup_file_to_drive(self, file_data, folder_id, source_base):
        # Upload file to Google Drive instead of copying to local folder
        result = self.google_drive.upload_file(
            file_data['path'],
            parent_id=folder_id,
            preserve_path=True,
            base_path=source_base
        )
        return result
```

### 5.2 Main Difference from Standard BackupEngine

| Standard BackupEngine | GoogleDriveBackupEngine |
|----------------------|-------------------------|
| Uses `shutil.copy2()` to copy files | Uses `google_drive.upload_file()` |
| Destination is local path | Destination is Google Drive folder ID |
| Fast (local disk) | Slower (network upload) |

---

## Step 6: Settings Tab UI (Already Implemented)

### 6.1 Authentication UI Elements

Located in `ui/settings_tab.py`:

1. **Upload Credentials Button**: User selects credentials.json file
2. **Authenticate Button**: Triggers OAuth flow
3. **Status Label**: Shows authentication status
4. **Test Connection Button**: Verifies Google Drive access

### 6.2 Authentication Process

```python
def authenticate_google_drive(self):
    # Get settings from database
    settings = self.db_session.query(GoogleDriveSettings).first()

    # Initialize Google Drive client
    client = GoogleDriveClient(
        credentials_file=settings.credentials_file,
        token_file=settings.token_file
    )

    # Authenticate (opens browser)
    if client.authenticate():
        # Update database
        settings.is_authenticated = True
        settings.last_authenticated = datetime.datetime.now()
        self.db_session.commit()

        # Show success message
        messagebox.showinfo("Success", "Authenticated with Google Drive!")
```

---

## Step 7: Creating a Google Drive Backup Job

### 7.1 In the Jobs Tab

When creating a new backup job:

1. **Destination Type Dropdown**: Choose "Google Drive" instead of "Local"
2. **Destination Folder**: Instead of browsing local path, select/create Google Drive folder
3. **Folder Picker**: Shows folders from Google Drive using `list_folders()`

### 7.2 Code Example

```python
# In jobs_tab.py (when creating job)
job = BackupJob(
    name="My Documents Backup",
    source_path="C:/Users/Me/Documents",
    destination_type=DestinationType.GOOGLE_DRIVE,  # Instead of LOCAL
    google_drive_folder_id="1xAbC...xyz",  # Google Drive folder ID
    is_active=True
)
db_session.add(job)
db_session.commit()
```

---

## Step 8: Running a Google Drive Backup

### 8.1 Engine Selection in main.py

```python
def create_backup_engine(self):
    settings = self.db_session.query(GoogleDriveSettings).first()

    if settings and settings.is_authenticated:
        # Use Google Drive engine
        return GoogleDriveBackupEngine(
            self.db_session,
            credentials_file=settings.credentials_file,
            token_file=settings.token_file,
            session_factory=self.Session
        )
    else:
        # Use standard local engine
        return BackupEngine(self.db_session, self.Session)
```

### 8.2 Backup Process

1. User clicks "Start Backup"
2. App checks job's `destination_type`
3. If `GOOGLE_DRIVE`:
   - Uses `GoogleDriveBackupEngine`
   - For each file, calls `backup_file_to_drive()`
   - Uploads to Google Drive folder
4. If `LOCAL`:
   - Uses `BackupEngine`
   - Copies files to local destination

---

## Step 9: Testing the Integration

### 9.1 Test Checklist

1. ✅ Install dependencies
2. ✅ Create Google Cloud project
3. ✅ Enable Google Drive API
4. ✅ Download credentials.json
5. ✅ Upload credentials via Settings tab
6. ✅ Click "Authenticate" (browser opens)
7. ✅ Grant permissions
8. ✅ Verify authentication status shows "Connected"
9. ✅ Create a test backup job with Google Drive destination
10. ✅ Run backup and verify files appear in Google Drive

### 9.2 Troubleshooting

**Problem: "credentials.json not found"**
- Solution: Make sure you uploaded the file via Settings tab

**Problem: "Authentication failed"**
- Check credentials.json is valid
- Ensure Google Drive API is enabled
- Verify OAuth consent screen is configured

**Problem: "Token expired"**
- The app auto-refreshes tokens
- If still fails, re-authenticate via Settings tab

**Problem: "Files not uploading"**
- Check internet connection
- Verify Google Drive storage quota
- Check logs in backup_app.log

---

## Step 10: Advanced Features

### 10.1 Folder Structure Preservation

```python
# Upload with directory structure
client.upload_file(
    'C:/Users/Me/Documents/Work/Report.pdf',
    parent_id=folder_id,
    preserve_path=True,  # Creates Work/ folder in Google Drive
    base_path='C:/Users/Me/Documents'
)
```

### 10.2 Checking File Existence

Before uploading, check if file already exists in Google Drive:

```python
def file_exists_in_drive(self, file_name, folder_id):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = self.service.files().list(q=query, fields='files(id)').execute()
    return len(results.get('files', [])) > 0
```

### 10.3 Progress Tracking

The `MediaFileUpload` supports resumable uploads for large files:

```python
media = MediaFileUpload(
    file_path,
    mimetype=mime_type,
    resumable=True,
    chunksize=1024*1024  # 1MB chunks
)

request = self.service.files().create(
    body=file_metadata,
    media_body=media,
    fields='id'
)

response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        progress = int(status.progress() * 100)
        print(f"Upload progress: {progress}%")
```

---

## Step 11: Security Best Practices

### 11.1 Credentials Storage

- ✅ `credentials.json`: Store in secure location, don't commit to Git
- ✅ `token.pickle`: Auto-generated, contains access tokens
- ✅ Add to `.gitignore`:
  ```
  credentials.json
  token.pickle
  ```

### 11.2 Scopes

Currently using minimal scope:
- `https://www.googleapis.com/auth/drive.file` - Only access files created by this app

For full access (read all files):
- `https://www.googleapis.com/auth/drive` - Full Drive access (not recommended)

### 11.3 Token Refresh

Tokens automatically refresh when expired. The flow:
1. Access token expires (1 hour)
2. App uses refresh token to get new access token
3. New access token saved to token.pickle
4. User doesn't need to re-authenticate

---

## Summary

**What you have:**
- ✅ Google Drive API client (`google_drive.py`)
- ✅ Google Drive backup engine (`google_drive_backup_engine.py`)
- ✅ Database models for settings
- ✅ Settings UI for authentication

**What you need to do:**
1. Get credentials.json from Google Cloud Console
2. Install Google API packages
3. Upload credentials via Settings tab
4. Authenticate with Google
5. Create backup jobs with Google Drive destination
6. Run backups!

**Key Concepts:**
- OAuth 2.0 for authentication
- Token-based access (auto-refresh)
- Folder IDs instead of file paths
- Resumable uploads for large files
- Directory structure preservation
