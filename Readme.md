# Smart Backup Tool

A lightweight desktop backup tool for Windows/Linux/Mac, built with CustomTkinter. Define backup jobs (source → destination), detect what's changed since the last run, and copy only what's needed — one job at a time or as a batch.

## Features

- Job management: create, edit, and delete backup jobs pairing a source directory with a destination
- Change detection: files are compared by size and modified time against stored metadata, so only new or changed files are copied
- A **Modified Files** view listing which active jobs currently have pending changes, with a per-job breakdown of the exact files
- Batch jobs: group multiple backup jobs, reorder them, enable/disable individual jobs, and run them all in sequence — or use "Run All Jobs" to run every active job without building a batch
- Parallel file copying using multiple worker processes
- SQLite-backed metadata store, with a settings screen for worker count, database maintenance, and light/dark theme
- Live progress, elapsed time, and a scrolling log while a backup runs

Google Drive as a backup destination is present in the codebase but disabled in the UI — it isn't fully wired up yet, so the option is greyed out in the Jobs tab.

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/Yohan94/File_Backup_GUI.git
cd File_Backup_GUI

python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
python main.py
```

The app stores its SQLite database and log file in a per-user app-data directory (`%LOCALAPPDATA%\SmartBackupTool` on Windows), not in the project folder.

## Usage

**Create a backup job** — Jobs tab → fill in Job Name, Source Path, and Destination Path → Create Job.

**Run a single job** — Backup tab → select a job → Scan to preview pending changes, or Start Backup to copy them.

**Check what's changed across all jobs** — Modified Files tab → Refresh to scan every active job's source directory; jobs with pending changes are listed with a file count and a View button to see the exact paths.

**Run every job at once** — Jobs tab → Run All Jobs, or group specific jobs into a named batch on the Batch Jobs tab (New Batch → Add to Batch → Run Selected).

**Settings** — worker/CPU count for parallel copying, database maintenance, and appearance (light/dark).

## Project Structure

```
File_Backup_GUI/
├── main.py                    # App entry point, tab wiring, UI event loop
├── models.py                  # SQLAlchemy models and database setup
├── file_scanner.py            # Directory scanning + change detection
├── backup_engine.py           # Parallel local backup engine
├── google_drive.py            # Google Drive API client (not exposed in the UI)
├── google_drive_backup_engine.py
├── ui/
│   ├── backup_tab.py          # Run/scan a single job, progress + log
│   ├── jobs_tab.py            # Create/edit/delete jobs
│   ├── modified_files_tab.py  # Table of jobs with pending changes
│   ├── batch_jobs_tab.py      # Group and run jobs as a batch
│   ├── settings_tab.py        # Worker count, DB maintenance, theme
│   ├── messagebox.py          # Themed message dialog wrapper
│   └── theme.py                # Shared colors, fonts, widget styling
└── requirements.txt
```

## Building an Executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

## License

MIT — see [LICENSE](LICENSE) for details.
