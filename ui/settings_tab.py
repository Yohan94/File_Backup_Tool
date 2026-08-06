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

        # Create main frame
        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(0, weight=1)

        # Create a scrollable frame for settings
        main_frame = ctk.CTkScrollableFrame(settings_tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)

        # Application settings
        theme.section_label(main_frame, "Application Settings").grid(
            row=0, column=0, padx=10, pady=(10, 8), sticky="w"
        )

        # Parallel processing settings
        parallel_frame = theme.card(main_frame)
        parallel_frame.grid(row=1, column=0, padx=10, pady=(0, 20), sticky="ew")
        parallel_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(parallel_frame, text="Parallel Processing", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=0, column=0, padx=16, pady=16, sticky="w"
        )

        saved_workers = int(get_setting(self.db_session, "max_workers",
                                         max(1, multiprocessing.cpu_count() - 1)))
        self.cpu_count_var = ctk.IntVar(value=saved_workers)
        cpu_slider = ctk.CTkSlider(
            parallel_frame,
            from_=1,
            to=multiprocessing.cpu_count(),
            variable=self.cpu_count_var,
            number_of_steps=max(1, multiprocessing.cpu_count() - 1),
            progress_color=theme.ACCENT,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
        )
        cpu_slider.grid(row=0, column=1, padx=10, pady=16, sticky="ew")

        self.cpu_label = ctk.CTkLabel(parallel_frame, text=f"{self.cpu_count_var.get()} CPUs",
                                       font=theme.FONT_BODY_BOLD, width=64)
        self.cpu_label.grid(row=0, column=2, padx=(0, 16), pady=16)

        cpu_slider.configure(command=self.on_cpu_change)

        # Database maintenance
        theme.section_label(main_frame, "Database Maintenance").grid(
            row=2, column=0, padx=10, pady=(0, 8), sticky="w"
        )

        db_buttons_frame = theme.card(main_frame)
        db_buttons_frame.grid(row=3, column=0, padx=10, pady=(0, 20), sticky="ew")

        theme.secondary_button(
            db_buttons_frame,
            text="Clean Orphaned Records",
            command=self.clean_database
        ).grid(row=0, column=0, padx=16, pady=16)

        theme.secondary_button(
            db_buttons_frame,
            text="Backup Database",
            command=self.backup_database
        ).grid(row=0, column=1, padx=(0, 16), pady=16)

        # Google Drive Integration
        theme.section_label(main_frame, "Google Drive Integration").grid(
            row=4, column=0, padx=10, pady=(0, 8), sticky="w"
        )

        gdrive_frame = theme.card(main_frame)
        gdrive_frame.grid(row=5, column=0, padx=10, pady=(0, 20), sticky="ew")
        gdrive_frame.grid_columnconfigure(1, weight=1)

        # Credentials file selection
        ctk.CTkLabel(gdrive_frame, text="Credentials File", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=0, column=0, padx=(16, 10), pady=16, sticky="w"
        )

        self.credentials_path_var = ctk.StringVar()
        credentials_entry = ctk.CTkEntry(
            gdrive_frame,
            textvariable=self.credentials_path_var,
            width=300,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ALT,
            border_color=theme.BORDER,
        )
        credentials_entry.grid(row=0, column=1, padx=10, pady=16, sticky="ew")

        theme.secondary_button(
            gdrive_frame,
            text="Browse",
            command=self.browse_credentials_file,
            width=80
        ).grid(row=0, column=2, padx=(0, 16), pady=16)

        # Authentication status
        ctk.CTkLabel(gdrive_frame, text="Status", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=1, column=0, padx=(16, 10), pady=(0, 16), sticky="w"
        )
        self.auth_status_label = theme.badge(gdrive_frame, "Not authenticated", kind="warning")
        self.auth_status_label.grid(row=1, column=1, padx=10, pady=(0, 16), sticky="w")

        # Authentication button
        self.auth_button = ctk.CTkButton(
            gdrive_frame,
            text="Authenticate",
            command=self.authenticate_google_drive,
            fg_color=theme.GOOGLE_BLUE,
            hover_color=theme.GOOGLE_BLUE_HOVER,
            corner_radius=theme.RADIUS_SM,
            font=theme.FONT_BODY_BOLD,
        )
        self.auth_button.grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 16), sticky="ew")

        # Load Google Drive settings
        self.load_google_drive_settings()

        # Application theme
        theme.section_label(main_frame, "Appearance").grid(
            row=6, column=0, padx=10, pady=(0, 8), sticky="w"
        )

        appearance_frame = theme.card(main_frame)
        appearance_frame.grid(row=7, column=0, padx=10, pady=(0, 20), sticky="ew")

        ctk.CTkLabel(appearance_frame, text="Theme", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=0, column=0, padx=16, pady=16, sticky="w"
        )

        saved_appearance = get_setting(self.db_session, "appearance_mode", "dark")
        self.appearance_mode_var = ctk.StringVar(value=saved_appearance)
        appearance_option = ctk.CTkOptionMenu(
            appearance_frame,
            values=["dark", "light", "system"],
            variable=self.appearance_mode_var,
            command=self.change_appearance_mode,
            font=theme.FONT_BODY,
            fg_color=theme.SURFACE_ALT,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            dropdown_fg_color=theme.SURFACE_ALT,
            corner_radius=theme.RADIUS_SM,
        )
        appearance_option.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="w")

        # About section
        theme.section_label(main_frame, "About").grid(
            row=8, column=0, padx=10, pady=(0, 8), sticky="w"
        )

        about_frame = theme.card(main_frame)
        about_frame.grid(row=9, column=0, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(about_frame, text="Smart Backup Tool v1.0", font=theme.FONT_H2).grid(
            row=0, column=0, padx=16, pady=(16, 2), sticky="w"
        )

        ctk.CTkLabel(about_frame, text="",
                     font=theme.FONT_BODY, text_color=theme.TEXT_MUTED).grid(
            row=1, column=0, padx=16, pady=0, sticky="w"
        )

        ctk.CTkLabel(about_frame, text="A lightweight, efficient backup solution",
                     font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).grid(
            row=2, column=0, padx=16, pady=(0, 16), sticky="w"
        )

    def on_cpu_change(self, value):
        workers = int(value)
        self.cpu_label.configure(text=f"{workers} CPUs")
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
                CTkMessagebox(title="Nothing to do",
                              message="No orphaned records found.", icon="info")
                return

            confirm = CTkMessagebox(
                title="Confirm Cleanup",
                message=f"Permanently delete {count} orphaned file records?",
                icon="question", option_1="Cancel", option_2="Delete",
            ).get()
            if confirm != "Delete":
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

        CTkMessagebox(title="Success",
                      message=f"Removed {deleted} orphaned records.", icon="check")

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

            CTkMessagebox(
                title="Success",
                message=f"Database backed up to:\n{target}",
                icon="check"
            )

        except Exception as e:
            logger.error(f"Error backing up database: {e}", exc_info=True)
            CTkMessagebox(
                title="Error",
                message=f"Error backing up database: {str(e)}",
                icon="cancel"
            )

    def change_appearance_mode(self, new_appearance_mode):
        """Change the app's appearance mode"""
        ctk.set_appearance_mode(new_appearance_mode)
        set_setting(self.db_session, "appearance_mode", new_appearance_mode)

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
                    theme.set_badge(self.auth_status_label, "Authenticated", kind="success")
                else:
                    theme.set_badge(self.auth_status_label, "Not authenticated", kind="warning")
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
            CTkMessagebox(
                title="Error",
                message="Please select a valid credentials file",
                icon="cancel"
            )
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
                message="A browser window will open for authentication. Please follow the instructions and grant access.",
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
                theme.set_badge(self.auth_status_label, "Authenticated", kind="success")

                CTkMessagebox(
                    title="Success",
                    message="Successfully authenticated with Google Drive",
                    icon="check"
                )
            else:
                CTkMessagebox(
                    title="Error",
                    message="Failed to authenticate with Google Drive",
                    icon="cancel"
                )

        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error authenticating with Google Drive: {str(e)}",
                icon="cancel"
            )