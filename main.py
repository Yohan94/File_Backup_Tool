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
theme.apply_ctk_theme()


class PageStack(ctk.CTkFrame):
    """Minimal stand-in for CTkTabview without its tab strip: the tabs build
    into .tab(name), and .set(name) shows that page. Navigation is the sidebar."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._pages = {}

    def add(self, name):
        page = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        self._pages[name] = page
        return page

    def tab(self, name):
        return self._pages[name]

    def set(self, name):
        for page_name, page in self._pages.items():
            if page_name == name:
                page.grid()
            else:
                page.grid_remove()


class BackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        theme.load_fonts(self)

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
        self.geometry("1200x760")
        self.minsize(1040, 660)
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

    # Sidebar label -> (internal tab name, page subtitle)
    PAGES = [
        ("Backup", "Backup", "Run a job and follow its progress."),
        ("Jobs", "Jobs", "Choose what gets backed up, and where it goes."),
        ("Pending changes", "Modified Files", "Files that changed since each job last ran."),
        ("Batches", "Batch Jobs", "Group jobs to run one after another."),
        ("Settings", "Settings", "Performance, Google Drive, and appearance."),
    ]

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_sidebar()

        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        # Page header: title + one line saying what the page is for
        page_header = ctk.CTkFrame(content, fg_color="transparent")
        page_header.grid(row=0, column=0, padx=28, pady=(24, 4), sticky="ew")
        self.page_title = ctk.CTkLabel(page_header, text="", font=theme.FONT_PAGE_TITLE,
                                       text_color=theme.INK, anchor="w")
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_subtitle = theme.hint_label(page_header, "", font=theme.FONT_BODY)
        self.page_subtitle.grid(row=1, column=0, sticky="w")

        # Pages are stacked in one cell; the sidebar raises the active one.
        self.tab_view = PageStack(content)
        self.tab_view.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        for _label, tab_name, _sub in self.PAGES:
            self.tab_view.add(tab_name)

        # Setup tabs with their respective classes
        # Pass the Session factory to tabs that need it for threading
        self.backup_tab = BackupTab(self, self.tab_view, self.db_session, self.backup_engine, self.Session)
        self.jobs_tab = JobsTab(self, self.tab_view, self.db_session, self.Session)
        self.modified_files_tab = ModifiedFilesTab(self, self.tab_view, self.db_session, self.Session)
        self.batch_jobs_tab = BatchJobsTab(self, self.tab_view, self.db_session, self.backup_engine, self.Session)
        self.settings_tab = SettingsTab(self, self.tab_view, self.db_session, self.Session)

        # Ctrl+1..5 jumps between pages
        for i, (_label, tab_name, _sub) in enumerate(self.PAGES, start=1):
            self.bind_all(f"<Control-Key-{i}>", lambda _e, t=tab_name: self.show_page(t))

        self._toast = None
        self.show_page("Backup")

        # Load backup jobs
        self.load_backup_jobs()

    def setup_sidebar(self):
        """Navigation plus a live backup status that's visible from every page."""
        sidebar = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        # Hairline separating sidebar from content
        ctk.CTkFrame(self, fg_color=theme.LINE, corner_radius=0, width=1).grid(
            row=0, column=0, sticky="nse")

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=20, pady=(24, 28), sticky="ew")
        ctk.CTkLabel(brand, text="Smart Backup", font=theme.FONT_WORDMARK,
                     text_color=theme.INK, anchor="w").grid(row=0, column=0, sticky="w")
        theme.hint_label(brand, "Local file backups").grid(row=1, column=0, sticky="w")

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, padx=(8, 12), sticky="ew")
        nav.grid_columnconfigure(1, weight=1)

        self.nav_buttons = {}
        self.nav_markers = {}
        for i, (label, tab_name, _sub) in enumerate(self.PAGES):
            marker = ctk.CTkFrame(nav, width=3, height=20, corner_radius=2, fg_color="transparent")
            marker.grid(row=i, column=0, padx=(0, 6), pady=2)
            button = ctk.CTkButton(
                nav, text=label, anchor="w", font=theme.FONT_NAV, height=38,
                fg_color="transparent", hover_color=theme.RAISED, text_color=theme.TEXT_MUTED,
                corner_radius=theme.RADIUS_SM, command=lambda t=tab_name: self.show_page(t),
            )
            button.grid(row=i, column=1, pady=2, sticky="ew")
            self.nav_buttons[tab_name] = button
            self.nav_markers[tab_name] = marker

        # Live status well, pinned to the bottom of the sidebar
        status = ctk.CTkFrame(sidebar, fg_color=theme.RAISED, corner_radius=theme.RADIUS)
        status.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="ew")
        status.grid_columnconfigure(0, weight=1)
        self.status_title = ctk.CTkLabel(status, text="Idle", font=theme.FONT_BODY_BOLD,
                                         text_color=theme.INK, anchor="w")
        self.status_title.grid(row=0, column=0, padx=14, pady=(12, 0), sticky="w")
        self.status_detail = theme.hint_label(status, "No backup running")
        self.status_detail.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")
        self.status_bar = theme.ProgressBar(status, height=4, corner_radius=2,
                                             fg_color=theme.LINE, progress_color=theme.INK)
        self.status_bar.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.status_bar.set(0)

        theme.hint_label(sidebar, "Ctrl+1 to Ctrl+5 switch pages",
                         text_color=theme.TEXT_FAINT).grid(
            row=4, column=0, padx=20, pady=(0, 16), sticky="w")

    def show_page(self, tab_name):
        """Switch pages and keep the sidebar + page header in sync."""
        self.tab_view.set(tab_name)
        for label, name, subtitle in self.PAGES:
            selected = name == tab_name
            self.nav_buttons[name].configure(
                fg_color=theme.RAISED if selected else "transparent",
                text_color=theme.INK if selected else theme.TEXT_MUTED,
                font=(theme.FONT_FAMILY, 14, "bold") if selected else theme.FONT_NAV,
            )
            self.nav_markers[name].configure(fg_color=theme.INK if selected else "transparent")
            if selected:
                self.page_title.configure(text=label)
                self.page_subtitle.configure(text=subtitle)

    def toast(self, message, kind="success", duration=2800):
        """A small non-blocking confirmation in the bottom-right corner.
        Used instead of a modal dialog when there's nothing to decide."""
        if self._toast is not None and self._toast.winfo_exists():
            self._toast.destroy()
        glyph = {"success": "\u2713", "error": "!", "info": "\u25cf"}.get(kind, "\u25cf")
        toast = ctk.CTkFrame(self, fg_color=theme.INK, corner_radius=theme.RADIUS_SM)
        label = ctk.CTkLabel(toast, text=f"{glyph}   {message}", font=theme.FONT_BODY_BOLD,
                             text_color=theme.ON_INK, anchor="w", wraplength=380,
                             justify="left")
        label.pack(padx=16, pady=10)
        toast.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
        toast.lift()
        for w in (toast, label):
            w.bind("<Button-1>", lambda _e: toast.winfo_exists() and toast.destroy())
        self._toast = toast
        if kind == "error":
            duration += 1500
        self.after(duration, lambda: toast.winfo_exists() and toast.destroy())

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
        self.update_status_well()

    def update_status_well(self):
        """Mirror the running backup into the sidebar, visible from any page."""
        engine = self.backup_engine
        if engine.running and engine.total_files > 0:
            progress = engine.processed_files / engine.total_files
            self.status_title.configure(text=f"Backing up  {int(progress * 100)}%")
            self.status_detail.configure(
                text=f"{engine.processed_files:,} of {engine.total_files:,} files")
            self.status_bar.set(progress)
        elif engine.running or self.backup_tab._backup_active:
            self.status_title.configure(text="Backing up")
            self.status_detail.configure(text="Looking for changed files")
            self.status_bar.set(0)
        else:
            self.status_title.configure(text="Idle")
            self.status_detail.configure(text="No backup running")
            self.status_bar.set(0)

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