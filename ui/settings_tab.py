import os
import customtkinter as ctk
import multiprocessing
import sqlite3
import datetime
import logging
import tkinter.filedialog as filedialog
from ui.messagebox import CTkMessagebox
from sqlalchemy import select, or_

# Local imports
from models import GoogleDriveSettings, DB_PATH, get_setting, set_setting
from google_drive import GoogleDriveClient
from ui import theme

# Configure logging
logger = logging.getLogger(__name__)


class SettingsTab:
    """UI for the Settings tab"""

    def __init__(self, parent, tab_view, db_session, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.Session = session_factory

        # Setup the settings tab UI
        self.setup_settings_tab(tab_view)

    def setup_settings_tab(self, tab_view):
        settings_tab = tab_view.tab("Settings")
        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkScrollableFrame(settings_tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        # ------------------------------------------------------ performance
        perf = self._section(main_frame, 0, "Performance")
        row = self._setting_row(
            perf, 1, "Files copied at once",
            "More is faster on SSDs. Lower it if your computer feels slow during a backup.")

        saved_workers = int(get_setting(self.db_session, "max_workers",
                                         max(1, multiprocessing.cpu_count() - 1)))
        self.cpu_count_var = ctk.IntVar(value=saved_workers)
        slider_frame = ctk.CTkFrame(row, fg_color="transparent")
        slider_frame.grid(row=0, column=1, rowspan=2, sticky="e")
        cpu_slider = ctk.CTkSlider(
            slider_frame, from_=1, to=multiprocessing.cpu_count(), width=220,
            variable=self.cpu_count_var,
            number_of_steps=max(1, multiprocessing.cpu_count() - 1),
        )
        cpu_slider.grid(row=0, column=0, padx=(0, 12))
        self.cpu_label = ctk.CTkLabel(slider_frame, text=str(self.cpu_count_var.get()),
                                      font=theme.FONT_H2, width=28, anchor="e")
        self.cpu_label.grid(row=0, column=1)
        cpu_slider.configure(command=self.on_cpu_change)

        # ------------------------------------------------------- appearance
        appearance = self._section(main_frame, 1, "Appearance")
        row = self._setting_row(appearance, 1, "Theme",
                                "System follows your Windows light or dark setting.")
        saved_appearance = get_setting(self.db_session, "appearance_mode", "dark")
        self.appearance_mode_var = ctk.StringVar(value=saved_appearance.capitalize())
        ctk.CTkSegmentedButton(
            row, values=["Dark", "Light", "System"], variable=self.appearance_mode_var,
            command=self.change_appearance_mode, font=theme.FONT_BODY_BOLD, height=theme.CONTROL_H,
            corner_radius=theme.RADIUS_SM,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # ----------------------------------------------------- google drive
        gdrive_frame = self._section(main_frame, 2, "Google Drive")
        row = self._setting_row(
            gdrive_frame, 1, "Connection",
            "Uses an OAuth credentials file from Google Cloud. See GOOGLE_DRIVE_SETUP.md.")
        self.auth_status_label = theme.badge(row, "Not connected", kind="warning")
        self.auth_status_label.grid(row=0, column=1, rowspan=2, sticky="e")

        cred_row = ctk.CTkFrame(gdrive_frame, fg_color="transparent")
        cred_row.grid(row=2, column=0, padx=theme.PAD, pady=(4, theme.PAD), sticky="ew")
        cred_row.grid_columnconfigure(0, weight=1)
        theme.field_label(cred_row, "Credentials file").grid(
            row=0, column=0, columnspan=3, pady=(0, 4), sticky="w")

        self.credentials_path_var = ctk.StringVar()
        theme.entry(cred_row, textvariable=self.credentials_path_var, font=theme.FONT_MONO,
                    placeholder_text="client_secret.json").grid(
            row=1, column=0, padx=(0, 8), sticky="ew")
        theme.secondary_button(
            cred_row, text="Browse", width=88, command=self.browse_credentials_file,
        ).grid(row=1, column=1, padx=(0, 8))
        self.auth_button = theme.secondary_button(
            cred_row, text="Connect", width=110, command=self.authenticate_google_drive)
        self.auth_button.grid(row=1, column=2)

        # Load Google Drive settings
        self.load_google_drive_settings()

        # --------------------------------------------------------- database
        db = self._section(main_frame, 3, "Database")
        row = self._setting_row(
            db, 1, "Save a copy of the database",
            "Your jobs, batches, and file history. Safe to run while a backup is going.")
        theme.secondary_button(row, text="Save copy…", width=130,
                               command=self.backup_database).grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkFrame(db, fg_color=theme.LINE, height=1, corner_radius=0).grid(
            row=2, column=0, padx=theme.PAD, sticky="ew")
        row = self._setting_row(
            db, 3, "Remove leftover records",
            "Deletes file history that belongs to jobs which no longer exist.")
        theme.danger_button(row, text="Clean up…", width=130,
                            command=self.clean_database).grid(row=0, column=1, rowspan=2, sticky="e")

        # ------------------------------------------------------------ about
        about = theme.card(main_frame)
        about.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="ew")
        ctk.CTkLabel(about, text="Smart Backup Tool 1.0", font=theme.FONT_H2, anchor="w").grid(
            row=0, column=0, padx=theme.PAD, pady=(16, 0), sticky="w")
        theme.hint_label(about, "Copies only what changed, so repeat backups are quick.").grid(
            row=1, column=0, padx=theme.PAD, pady=(0, 16), sticky="w")

    def _section(self, parent, index, title):
        """A titled card holding one group of settings."""
        frame = theme.card(parent)
        frame.grid(row=index, column=0, padx=12, pady=(12 if index == 0 else 0, 12), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        theme.section_label(frame, title).grid(
            row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 6), sticky="w")
        return frame

    def _setting_row(self, section, row_index, title, hint):
        """Label + explanation on the left; the caller puts a control in column 1."""
        row = ctk.CTkFrame(section, fg_color="transparent")
        row.grid(row=row_index, column=0, padx=theme.PAD, pady=(8, 14), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text=title, font=theme.FONT_BODY_BOLD, anchor="w").grid(
            row=0, column=0, sticky="w")
        theme.hint_label(row, hint, wraplength=520).grid(row=1, column=0, padx=(0, 24), sticky="w")
        return row

    def on_cpu_change(self, value):
        workers = int(value)
        self.cpu_label.configure(text=str(workers))
        set_setting(self.db_session, "max_workers", workers)
        self.parent.backup_engine.max_workers = workers

    def clean_database(self):
        """Delete file metadata whose job row no longer exists."""
        FileMetadata = self.parent.FileMetadata
        BackupJob = self.parent.BackupJob

        session = self.Session()
        try:
            # "Orphaned" == dangling FK, NOT "job is soft-deleted".
            # Soft-deleted jobs are restorable; their metadata is still valid.
            existing_ids = select(BackupJob.id).scalar_subquery()
            orphan_filter = or_(
                FileMetadata.job_id.is_(None),          # NOT IN never matches NULL
                FileMetadata.job_id.notin_(existing_ids),
            )

            # Count first, confirm with the real number, then delete.
            count = session.query(FileMetadata).filter(orphan_filter).count()
            if count == 0:
                self.parent.toast("Nothing to clean up", kind="info")
                return

            confirm = CTkMessagebox(
                title="Remove leftover records",
                message=f"Permanently delete {count:,} records from deleted jobs? "
                        f"Your backed-up files are not touched.",
                icon="question", option_1="Cancel", option_2="Delete records",
            ).get()
            if confirm != "Delete records":
                return

            deleted = session.query(FileMetadata).filter(orphan_filter).delete(
                synchronize_session=False)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error cleaning database: {e}", exc_info=True)
            CTkMessagebox(title="Error", message=f"Error cleaning database: {e}",
                          icon="cancel")
            return
        finally:
            session.close()

        # The long-lived UI session still holds deleted rows in its identity map.
        self.db_session.expire_all()

        self.parent.toast(f"Removed {deleted:,} leftover records")

    def backup_database(self):
        """Backup the SQLite database file using the online-backup API.

        A plain file copy can produce a torn snapshot if a write is in
        flight; sqlite3.Connection.backup() is safe against concurrent
        writers.
        """
        target = filedialog.asksaveasfilename(
            title="Save database backup",
            defaultextension=".db",
            initialfile=f"backup_app_backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.db",
            filetypes=[("SQLite database", "*.db")],
        )
        if not target:
            return
        try:
            src = sqlite3.connect(str(DB_PATH))
            dst = sqlite3.connect(target)
            with dst:
                src.backup(dst)
            dst.close()
            src.close()

            self.parent.toast(f"Database copy saved to {os.path.basename(target)}")

        except Exception as e:
            logger.error(f"Error backing up database: {e}", exc_info=True)
            CTkMessagebox(
                title="Error",
                message=f"Error backing up database: {str(e)}",
                icon="cancel"
            )

    def change_appearance_mode(self, new_appearance_mode):
        """Change the app's appearance mode"""
        mode = new_appearance_mode.lower()
        ctk.set_appearance_mode(mode)
        set_setting(self.db_session, "appearance_mode", mode)

    def browse_credentials_file(self):
        """Open file dialog to select Google Drive credentials file"""
        file_path = filedialog.askopenfilename(
            title="Select Google Drive Credentials File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if file_path:
            self.credentials_path_var.set(file_path)

    def load_google_drive_settings(self):
        """Load Google Drive settings from the database"""
        try:
            # Get Google Drive settings
            settings = self.db_session.query(GoogleDriveSettings).first()

            if settings:
                # Update UI with settings
                if settings.credentials_file:
                    self.credentials_path_var.set(settings.credentials_file)

                if settings.is_authenticated:
                    theme.set_badge(self.auth_status_label, "Connected", kind="success")
                else:
                    theme.set_badge(self.auth_status_label, "Not connected", kind="warning")
            else:
                # Create default settings if none exist
                settings = GoogleDriveSettings()
                self.db_session.add(settings)
                self.db_session.commit()

        except Exception as e:
            logger.error(f"Error loading Google Drive settings: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error loading Google Drive settings: {str(e)}",
                icon="cancel"
            )

    def authenticate_google_drive(self):
        """Authenticate with Google Drive"""
        credentials_file = self.credentials_path_var.get()

        if not credentials_file or not os.path.exists(credentials_file):
            self.parent.toast("Choose your credentials .json file first.", kind="error")
            return

        try:
            # Save credentials file path to database
            settings = self.db_session.query(GoogleDriveSettings).first()
            if not settings:
                settings = GoogleDriveSettings()
                self.db_session.add(settings)

            settings.credentials_file = credentials_file
            self.db_session.commit()

            # Create Google Drive client and authenticate
            gdrive = GoogleDriveClient(credentials_file=credentials_file)

            # Show a message to the user
            CTkMessagebox(
                title="Google Drive Authentication",
                message="Your browser will open so you can sign in to Google and allow access. Come back here when you're done.",
                icon="info"
            )

            # Attempt to authenticate
            success = gdrive.authenticate()

            if success:
                # Update settings in database
                settings.is_authenticated = True
                settings.last_authenticated = datetime.datetime.now()
                settings.token_file = gdrive.token_file
                self.db_session.commit()

                # Update UI
                theme.set_badge(self.auth_status_label, "Connected", kind="success")

                self.parent.toast("Connected to Google Drive")
            else:
                CTkMessagebox(
                    title="Error",
                    message="Google Drive didn't connect. Check that the credentials file is for a Desktop app, then try again.",
                    icon="cancel"
                )

        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error authenticating with Google Drive: {str(e)}",
                icon="cancel"
            )