import os
import time
import customtkinter as ctk
import logging
from logging.handlers import RotatingFileHandler
from ui.messagebox import CTkMessagebox
import queue
import multiprocessing

# Import local modules
from models import (init_database, BackupJob, FileMetadata, BatchJob, BatchItem,
                     GoogleDriveSettings, DestinationType, get_setting, get_app_data_dir)
from backup_engine import BackupEngine
from google_drive_backup_engine import GoogleDriveBackupEngine
from ui.backup_tab import BackupTab
from ui.jobs_tab import JobsTab
from ui.modified_files_tab import ModifiedFilesTab
from ui.batch_jobs_tab import BatchJobsTab
from ui.settings_tab import SettingsTab
from ui import theme

# Set up logging
_log_handler = RotatingFileHandler(
    get_app_data_dir() / "backup_app.log",
    maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
_log_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("BACKUP_DEBUG") else logging.INFO,
    handlers=[_log_handler]
)
logger = logging.getLogger(__name__)

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class BackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Make model classes available to all tabs
        self.BackupJob = BackupJob
        self.FileMetadata = FileMetadata
        self.BatchJob = BatchJob
        self.BatchItem = BatchItem
        self.GoogleDriveSettings = GoogleDriveSettings
        self.DestinationType = DestinationType

        # Initialize the database session and backup engine
        self.engine, self.Session = init_database()
        self.db_session = self.Session()

        # Initialize Google Drive settings
        self.init_google_drive_settings()

        # Create backup engine based on Google Drive authentication status
        self.backup_engine = self.create_backup_engine()

        # Apply persisted settings (worker count, theme) before building the UI
        self.backup_engine.max_workers = int(
            get_setting(self.db_session, "max_workers",
                        max(1, multiprocessing.cpu_count() - 1)))
        ctk.set_appearance_mode(get_setting(self.db_session, "appearance_mode", "dark"))

        # Configure window
        self.title("Smart Backup Tool")
        self.geometry("1100x700")
        self.minsize(950, 620)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Reference for the log_text widget (will be set by backup_tab)
        self.log_text = None

        # Thread-safe queue of callables to run on the Tk main thread
        self._ui_queue = queue.Queue()
        self._closing = False
        self._tick = 0

        # Initialize UI components
        self.setup_ui()

        # Start UI update timer
        self.start_ui_update_timer()

    def post_to_ui(self, fn):
        """Thread-safe: schedule `fn` to run on the Tk main thread."""
        self._ui_queue.put(fn)

    def _drain_ui_queue(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception:
                logger.exception("Error in queued UI callback")

    def setup_ui(self):
        # Create main frame
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.setup_header()

        # Create main tabs
        self.tab_view = ctk.CTkTabview(
            self,
            corner_radius=theme.RADIUS,
            fg_color=theme.SURFACE_ALT,
            segmented_button_fg_color=theme.SURFACE_ALT,
            segmented_button_selected_color=theme.ACCENT,
            segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            segmented_button_unselected_color=theme.SURFACE_ALT,
            segmented_button_unselected_hover_color=theme.BORDER,
            text_color=("#111827", "#F3F5F8"),
        )
        self.tab_view.grid(row=1, column=0, padx=14, pady=(10, 6), sticky="nsew")
        self.tab_view._segmented_button.configure(font=theme.FONT_BODY_BOLD)

        # Add tabs
        self.tab_view.add("Backup")
        self.tab_view.add("Jobs")
        self.tab_view.add("Modified Files")
        self.tab_view.add("Batch Jobs")
        self.tab_view.add("Settings")

        # Configure tab grids
        for tab_name in ["Backup", "Jobs", "Modified Files", "Batch Jobs", "Settings"]:
            self.tab_view.tab(tab_name).grid_columnconfigure(0, weight=1)
            self.tab_view.tab(tab_name).grid_rowconfigure(0, weight=1)

        # Setup tabs with their respective classes
        # Pass the Session factory to tabs that need it for threading
        self.backup_tab = BackupTab(self, self.tab_view, self.db_session, self.backup_engine, self.Session)
        self.jobs_tab = JobsTab(self, self.tab_view, self.db_session, self.Session)
        self.modified_files_tab = ModifiedFilesTab(self, self.tab_view, self.db_session, self.Session)
        self.batch_jobs_tab = BatchJobsTab(self, self.tab_view, self.db_session, self.backup_engine, self.Session)
        self.settings_tab = SettingsTab(self, self.tab_view, self.db_session, self.Session)

        # Add copyright footer
        self.footer_label = ctk.CTkLabel(
            self,
            text="",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED,
        )
        self.footer_label.grid(row=2, column=0, pady=(0, 8), sticky="se", padx=16)

        # Load backup jobs
        self.load_backup_jobs()

    def setup_header(self):
        """Branded title bar shown above the tabs."""
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.HEADER_BG, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        logo = ctk.CTkLabel(
            header, text="SB", font=(theme.FONT_FAMILY, 16, "bold"),
            fg_color=theme.ACCENT, text_color="#FFFFFF",
            corner_radius=theme.RADIUS_SM, width=38, height=38,
        )
        logo.grid(row=0, column=0, padx=(18, 12), pady=13)

        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="w", pady=8)

        ctk.CTkLabel(
            text_frame, text="Smart Backup Tool", font=theme.FONT_TITLE,
            text_color=theme.HEADER_TEXT,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_frame, text="Local & cloud file backup, automated",
            font=theme.FONT_SUBTITLE, text_color=theme.HEADER_SUBTEXT,
        ).grid(row=1, column=0, sticky="w")

    def load_backup_jobs(self):
        """Load existing backup jobs from the database - this calls the jobs_tab method"""
        self.jobs_tab.load_backup_jobs()

    def log_message(self, message):
        """Add a message to the log display"""
        logger.info(message)
        self.post_to_ui(lambda: self._append_log(message))

    def _append_log(self, message):
        if not self.log_text:
            return
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except Exception:
            logger.exception("Error appending to log widget")

    def start_ui_update_timer(self):
        """Start a timer to update the UI periodically"""
        if self._closing:
            return
        self._drain_ui_queue()          # every 100 ms — keeps the log responsive
        self._tick += 1
        if self._tick % 10 == 0:        # every ~1 s
            self.update_ui()
        self.after(100, self.start_ui_update_timer)

    def update_ui(self):
        """Update the UI based on the current state"""
        # Update backup tab UI
        self.backup_tab.update_ui()

    def init_google_drive_settings(self):
        """Initialize Google Drive settings"""
        try:
            # Check if Google Drive settings exist
            settings = self.db_session.query(GoogleDriveSettings).first()
            if not settings:
                # Create default settings
                settings = GoogleDriveSettings()
                self.db_session.add(settings)
                self.db_session.commit()
        except Exception as e:
            logger.error(f"Error initializing Google Drive settings: {e}")

    def create_backup_engine(self):
        """Create the appropriate backup engine based on Google Drive authentication status"""
        try:
            # Check if Google Drive is authenticated
            settings = self.db_session.query(GoogleDriveSettings).first()

            if settings and settings.is_authenticated and settings.credentials_file and settings.token_file:
                # Create Google Drive backup engine
                return GoogleDriveBackupEngine(
                    self.db_session,
                    credentials_file=settings.credentials_file,
                    token_file=settings.token_file,
                    session_factory=self.Session
                )
            else:
                # Create standard backup engine
                return BackupEngine(self.db_session, self.Session)
        except Exception as e:
            logger.error(f"Error creating backup engine: {e}")
            # Fallback to standard backup engine
            return BackupEngine(self.db_session, self.Session)

    def on_closing(self):
        """Handle application closing"""
        if self.backup_engine.running:
            if CTkMessagebox(title="Backup in progress",
                             message="A backup is still running. Cancel it and exit?",
                             icon="question", option_1="Keep running",
                             option_2="Cancel and exit").get() != "Cancel and exit":
                return

        self._closing = True
        try:
            if self.backup_engine.running:
                self.backup_engine.cancel_backup()
                # Give in-flight work a moment to notice the flag (see backup_engine's
                # process_file_list, which checks self.running between files).
                deadline = time.time() + 5
                while self.backup_engine.running and time.time() < deadline:
                    time.sleep(0.1)
                if self.backup_engine.running:
                    logger.warning("Backup did not stop within 5s; forcing shutdown")
        except Exception:
            logger.exception("Error cancelling backup during shutdown")
        finally:
            try:
                self.db_session.close()
            except Exception:
                logger.exception("Error closing DB session")
            self.destroy()


if __name__ == "__main__":
    app = BackupApp()
    app.mainloop()