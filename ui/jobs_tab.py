import os
import customtkinter as ctk
import logging
import tkinter as tk
from tkinter import filedialog
from ui.messagebox import CTkMessagebox

# Local imports
from models import DestinationType, GoogleDriveSettings
from google_drive import GoogleDriveClient
from ui import theme

# Configure logging
logger = logging.getLogger(__name__)


class JobsTab:
    """UI for the Jobs tab"""

    def __init__(self, parent, tab_view, db_session, session_factory):
        self.parent = parent
        self.db_session = db_session
        self.Session = session_factory
        self.current_editing_job_id = None

        # Setup the jobs tab UI
        self.setup_jobs_tab(tab_view)

    def setup_jobs_tab(self, tab_view):
        jobs_tab = tab_view.tab("Jobs")
        jobs_tab.grid_columnconfigure(0, weight=5, uniform="jobs")
        jobs_tab.grid_columnconfigure(1, weight=6, uniform="jobs")
        jobs_tab.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------------ left: list
        list_card = theme.card(jobs_tab)
        list_card.grid(row=0, column=0, padx=(12, theme.GAP // 2), pady=12, sticky="nsew")
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(2, weight=1)

        list_header = ctk.CTkFrame(list_card, fg_color="transparent")
        list_header.grid(row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 2), sticky="ew")
        list_header.grid_columnconfigure(0, weight=1)
        self.list_title = theme.section_label(list_header, "Your jobs")
        self.list_title.grid(row=0, column=0, sticky="w")

        self.run_all_button = theme.secondary_button(
            list_header, text="Run all jobs",
            command=lambda: self.parent.batch_jobs_tab.run_all_jobs()
        )
        self.run_all_button.grid(row=0, column=1, sticky="e")

        theme.hint_label(list_card, "Select a job to edit it.").grid(
            row=1, column=0, padx=theme.PAD, pady=(0, 8), sticky="w")

        jobs_list_frame = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        jobs_list_frame.grid(row=2, column=0, padx=(theme.PAD - 8, 8), pady=(0, 12), sticky="nsew")
        jobs_list_frame.grid_columnconfigure(0, weight=1)
        self.jobs_list_frame = jobs_list_frame
        self.job_rows = {}

        # ------------------------------------------------------ right: form
        job_edit_frame = theme.card(jobs_tab)
        job_edit_frame.grid(row=0, column=1, padx=(theme.GAP // 2, 12), pady=12, sticky="nsew")
        job_edit_frame.grid_columnconfigure(0, weight=1)
        job_edit_frame.grid_rowconfigure(10, weight=1)

        self.form_title = theme.section_label(job_edit_frame, "New job")
        self.form_title.grid(row=0, column=0, padx=theme.PAD, pady=(theme.PAD, 2), sticky="w")
        self.form_hint = theme.hint_label(
            job_edit_frame, "Pick a folder to protect and a folder to copy it into.")
        self.form_hint.grid(row=1, column=0, padx=theme.PAD, pady=(0, 18), sticky="w")

        # Job name
        theme.field_label(job_edit_frame, "Name").grid(
            row=2, column=0, padx=theme.PAD, pady=(0, 4), sticky="w")
        self.job_name_var = ctk.StringVar()
        self.job_name_entry = theme.entry(
            job_edit_frame, textvariable=self.job_name_var,
            placeholder_text="e.g. Photos to external drive")
        self.job_name_entry.grid(row=3, column=0, padx=theme.PAD, pady=(0, 14), sticky="ew")

        # Source path
        theme.field_label(job_edit_frame, "Folder to back up").grid(
            row=4, column=0, padx=theme.PAD, pady=(0, 4), sticky="w")
        source_path_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        source_path_frame.grid(row=5, column=0, padx=theme.PAD, pady=(0, 14), sticky="ew")
        source_path_frame.grid_columnconfigure(0, weight=1)

        self.source_path_var = ctk.StringVar()
        theme.entry(source_path_frame, textvariable=self.source_path_var,
                    font=theme.FONT_MONO).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        theme.secondary_button(
            source_path_frame, text="Browse", width=88,
            command=lambda: self.browse_directory(self.source_path_var)
        ).grid(row=0, column=1)

        # Destination type
        theme.field_label(job_edit_frame, "Copy to").grid(
            row=6, column=0, padx=theme.PAD, pady=(0, 4), sticky="w")

        self.dest_type_var = ctk.StringVar(value="Local Directory")
        dest_type_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        dest_type_frame.grid(row=7, column=0, padx=theme.PAD, pady=(0, 8), sticky="ew")

        ctk.CTkRadioButton(
            dest_type_frame, text="A folder on this computer or a drive",
            font=theme.FONT_BODY, variable=self.dest_type_var, value="Local Directory",
            command=self.toggle_destination_type, radiobutton_width=18, radiobutton_height=18,
        ).grid(row=0, column=0, padx=(0, 18), pady=4, sticky="w")

        # Google Drive support is not wired up in this build (see
        # REMEDIATION_PLAN.md Phase 6) — disable rather than leave it broken.
        ctk.CTkRadioButton(
            dest_type_frame, text="Google Drive (coming soon)", font=theme.FONT_BODY,
            variable=self.dest_type_var, value="Google Drive",
            command=self.toggle_destination_type, state="disabled",
            radiobutton_width=18, radiobutton_height=18,
        ).grid(row=0, column=1, pady=4, sticky="w")

        # Local destination frame
        self.local_dest_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        self.local_dest_frame.grid(row=8, column=0, padx=theme.PAD, pady=(0, 14), sticky="ew")
        self.local_dest_frame.grid_columnconfigure(0, weight=1)

        self.dest_path_var = ctk.StringVar()
        theme.entry(self.local_dest_frame, textvariable=self.dest_path_var,
                    font=theme.FONT_MONO).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        theme.secondary_button(
            self.local_dest_frame, text="Browse", width=88,
            command=lambda: self.browse_directory(self.dest_path_var)
        ).grid(row=0, column=1)

        # Google Drive destination frame
        self.gdrive_dest_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        self.gdrive_dest_frame.grid(row=8, column=0, padx=theme.PAD, pady=(0, 14), sticky="ew")
        self.gdrive_dest_frame.grid_columnconfigure(1, weight=1)

        self.gdrive_folder_var = ctk.StringVar(value="root")
        self.gdrive_folder_id_var = ctk.StringVar(value="root")

        theme.field_label(self.gdrive_dest_frame, "Folder").grid(
            row=0, column=0, padx=(0, 8), pady=5, sticky="w")
        self.gdrive_folder_display = ctk.CTkLabel(
            self.gdrive_dest_frame, textvariable=self.gdrive_folder_var, font=theme.FONT_BODY_BOLD)
        self.gdrive_folder_display.grid(row=0, column=1, pady=5, sticky="w")
        theme.secondary_button(
            self.gdrive_dest_frame, text="Choose folder", width=120,
            command=self.select_google_drive_folder
        ).grid(row=0, column=2, pady=5)

        # Hide Google Drive frame by default
        self.gdrive_dest_frame.grid_remove()

        # Buttons: primary action first, destructive action last and apart
        buttons_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        buttons_frame.grid(row=9, column=0, padx=theme.PAD, pady=(8, theme.PAD), sticky="ew")
        buttons_frame.grid_columnconfigure(2, weight=1)

        self.save_job_button = theme.primary_button(
            buttons_frame, text="Create job", width=130, command=self.save_job)
        self.save_job_button.grid(row=0, column=0, padx=(0, 8))

        self.new_job_button = theme.secondary_button(
            buttons_frame, text="Clear form", width=110, command=self.new_job)
        self.new_job_button.grid(row=0, column=1)

        self.delete_job_button = theme.danger_button(
            buttons_frame, text="Delete job", width=110, command=self.delete_job)
        self.delete_job_button.grid(row=0, column=3, sticky="e")

        # Enter saves from anywhere in the form
        for widget in (self.job_name_entry,):
            widget.bind("<Return>", lambda _e: self.save_job())

        # Initialize editing state
        self.new_job()

    def load_backup_jobs(self):
        """Load existing backup jobs from the database"""
        try:
            # Clear existing jobs list
            for widget in self.jobs_list_frame.winfo_children():
                widget.destroy()
            self.job_rows = {}

            # Get all active jobs
            BackupJob = self.parent.BackupJob
            jobs = self.db_session.query(BackupJob).filter_by(is_active=True).order_by(BackupJob.name).all()

            # Keep the Backup page's selector in sync
            self.parent.backup_tab.set_jobs(jobs)
            self.list_title.configure(text=f"Your jobs ({len(jobs)})" if jobs else "Your jobs")
            theme.set_enabled(self.run_all_button, bool(jobs))

            if not jobs:
                theme.hint_label(
                    self.jobs_list_frame,
                    "No jobs yet. Fill in the form on the right to create your first one.",
                    wraplength=300,
                ).grid(row=0, column=0, padx=8, pady=20, sticky="w")

            for i, job in enumerate(jobs):
                row = ctk.CTkFrame(self.jobs_list_frame, fg_color=theme.RAISED,
                                   corner_radius=theme.RADIUS_SM)
                row.grid(row=i, column=0, padx=0, pady=4, sticky="ew")
                row.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(row, text=job.name, font=theme.FONT_H2, anchor="w").grid(
                    row=0, column=0, padx=14, pady=(12, 0), sticky="w")
                ctk.CTkLabel(row, text=theme.shorten_path(job.source_path, 44),
                             font=theme.FONT_MONO, text_color=theme.TEXT_MUTED, anchor="w").grid(
                    row=1, column=0, padx=14, pady=0, sticky="w")

                last_backup = ("Never backed up" if not job.last_backup
                               else f"Last backup {job.last_backup:%d %b %Y, %H:%M}")
                theme.hint_label(row, last_backup, text_color=theme.TEXT_FAINT).grid(
                    row=2, column=0, padx=14, pady=(0, 12), sticky="w")

                theme.make_clickable(row, lambda j=job: self.edit_job(j))
                self.job_rows[job.id] = row

            self._highlight_editing_row()

        except Exception as e:
            logger.error(f"Error loading backup jobs: {e}")
            self.parent.log_message(f"Error loading backup jobs: {e}")

    def _highlight_editing_row(self):
        for job_id, row in self.job_rows.items():
            selected = job_id == self.current_editing_job_id
            theme.set_row_base(row, theme.RAISED_HOVER if selected else theme.RAISED)
            row.configure(border_width=1 if selected else 0, border_color=theme.LINE_STRONG)

    def browse_directory(self, string_var):
        """Open directory browser and update the StringVar"""
        directory = filedialog.askdirectory(parent=self.parent)
        if directory:
            string_var.set(directory)

    def toggle_destination_type(self):
        """Toggle between local and Google Drive destination types"""
        dest_type = self.dest_type_var.get()

        if dest_type == "Local Directory":
            self.local_dest_frame.grid()
            self.gdrive_dest_frame.grid_remove()
        else:  # Google Drive
            self.local_dest_frame.grid_remove()
            self.gdrive_dest_frame.grid()

            # Check if Google Drive is authenticated
            settings = self.db_session.query(GoogleDriveSettings).first()
            if not settings or not settings.is_authenticated:
                CTkMessagebox(
                    title="Google Drive Not Authenticated",
                    message="Please authenticate with Google Drive in the Settings tab first.",
                    icon="warning"
                )
                # Switch back to local directory
                self.dest_type_var.set("Local Directory")
                self.toggle_destination_type()

    def select_google_drive_folder(self):
        """Open a dialog to select a Google Drive folder"""
        # Check if Google Drive is authenticated
        settings = self.db_session.query(GoogleDriveSettings).first()
        if not settings or not settings.is_authenticated:
            CTkMessagebox(
                title="Google Drive Not Authenticated",
                message="Please authenticate with Google Drive in the Settings tab first.",
                icon="warning"
            )
            return

        try:
            # Create Google Drive client
            gdrive = GoogleDriveClient(
                credentials_file=settings.credentials_file,
                token_file=settings.token_file
            )

            # Authenticate
            if not gdrive.authenticate():
                CTkMessagebox(
                    title="Authentication Failed",
                    message="Failed to authenticate with Google Drive.",
                    icon="cancel"
                )
                return

            # Create a simple folder selection dialog
            folder_window = ctk.CTkToplevel(self.parent)
            folder_window.title("Select Google Drive Folder")
            folder_window.geometry("400x500")
            folder_window.transient(self.parent)
            folder_window.grab_set()

            # Current folder ID and path
            current_folder_id = "root"
            folder_path = ["root"]

            # Function to list folders and update the listbox
            def list_folders(folder_id):
                nonlocal current_folder_id
                current_folder_id = folder_id

                # Clear the listbox
                folder_listbox.delete(0, tk.END)

                # Add parent folder option if not at root
                if folder_id != "root":
                    folder_listbox.insert(tk.END, "..")

                # Get folders from Google Drive
                folders = gdrive.list_folders(folder_id)

                # Add folders to listbox
                for folder in folders:
                    folder_listbox.insert(tk.END, folder["name"])

                # Update path display
                path_var.set(" / ".join(folder_path))

            # Function to handle folder selection
            def on_folder_select(event):
                selection = folder_listbox.curselection()
                if not selection:
                    return

                index = selection[0]
                folder_name = folder_listbox.get(index)

                if folder_name == "..":
                    # Go up one level
                    if len(folder_path) > 1:
                        folder_path.pop()
                        parent_id = "root" if len(folder_path) == 1 else folder_ids[len(folder_path) - 1]
                        list_folders(parent_id)
                else:
                    # Get selected folder ID
                    folders = gdrive.list_folders(current_folder_id)
                    selected_folder = next((f for f in folders if f["name"] == folder_name), None)

                    if selected_folder:
                        # Store folder ID for path navigation
                        folder_ids.append(selected_folder["id"])
                        folder_path.append(folder_name)
                        list_folders(selected_folder["id"])

            # Function to select the current folder
            def select_current_folder():
                self.gdrive_folder_var.set(folder_path[-1] if folder_path else "root")
                self.gdrive_folder_id_var.set(current_folder_id)
                folder_window.destroy()

            # Create UI elements
            path_var = ctk.StringVar(value="root")
            path_label = ctk.CTkLabel(folder_window, textvariable=path_var)
            path_label.pack(padx=10, pady=10, fill="x")

            # Folder listbox
            folder_frame = ctk.CTkFrame(folder_window)
            folder_frame.pack(padx=10, pady=10, fill="both", expand=True)

            folder_listbox = tk.Listbox(folder_frame, bg="#262626", fg="#F2F2F2", selectbackground="#474747",
                                        borderwidth=0, highlightthickness=0, font=theme.FONT_BODY)
            folder_listbox.pack(padx=10, pady=10, fill="both", expand=True)
            folder_listbox.bind("<Double-Button-1>", on_folder_select)

            # Buttons
            button_frame = ctk.CTkFrame(folder_window)
            button_frame.pack(padx=10, pady=10, fill="x")

            select_button = ctk.CTkButton(
                button_frame,
                text="Select This Folder",
                command=select_current_folder
            )
            select_button.pack(side="left", padx=10, pady=10)

            cancel_button = ctk.CTkButton(
                button_frame,
                text="Cancel",
                command=folder_window.destroy
            )
            cancel_button.pack(side="right", padx=10, pady=10)

            # Store folder IDs for path navigation
            folder_ids = []

            # Initial folder listing
            list_folders("root")

        except Exception as e:
            logger.error(f"Error selecting Google Drive folder: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error selecting Google Drive folder: {str(e)}",
                icon="cancel"
            )

    def save_job(self):
        """Save the current job being edited"""
        name = self.job_name_var.get().strip()
        source_path = self.source_path_var.get().strip()
        dest_type = self.dest_type_var.get()

        # Get destination based on type
        if dest_type == "Local Directory":
            dest_path = self.dest_path_var.get().strip()
            google_drive_folder_id = None
            destination_type = DestinationType.LOCAL
        else:  # Google Drive
            dest_path = f"Google Drive: {self.gdrive_folder_var.get()}"
            google_drive_folder_id = self.gdrive_folder_id_var.get()
            destination_type = DestinationType.GOOGLE_DRIVE

        if not name or not source_path:
            self.parent.toast("Add a name and a folder to back up.", kind="error")
            return

        if not os.path.isdir(source_path):
            self.parent.toast("The folder to back up doesn't exist. Choose it with Browse.", kind="error")
            return

        # Validate destination based on type
        if dest_type == "Local Directory":
            if not dest_path:
                self.parent.toast("Choose where to copy the files.", kind="error")
                return

            if not os.path.isdir(dest_path):
                self.parent.toast("The destination folder doesn't exist. Connect the drive or choose another folder.", kind="error")
                return
        else:  # Google Drive
            if not google_drive_folder_id:
                CTkMessagebox(
                    title="Error",
                    message="Please select a Google Drive folder",
                    icon="cancel"
                )
                return

            # Check if Google Drive is authenticated
            settings = self.db_session.query(GoogleDriveSettings).first()
            if not settings or not settings.is_authenticated:
                CTkMessagebox(
                    title="Error",
                    message="Please authenticate with Google Drive in the Settings tab first",
                    icon="cancel"
                )
                return

        try:
            BackupJob = self.parent.BackupJob

            # Check uniqueness among active jobs on both create and edit — a
            # rename could otherwise collide with another active job, and a
            # soft-deleted job's name would stay reserved forever.
            clash = self.db_session.query(BackupJob).filter(
                BackupJob.name == name,
                BackupJob.is_active.is_(True),
                BackupJob.id != (self.current_editing_job_id or -1),
            ).first()
            if clash:
                self.parent.toast(f"A job named \"{name}\" already exists. Pick another name.", kind="error")
                return

            if self.current_editing_job_id is not None:
                # Updating existing job
                job = self.db_session.get(BackupJob, self.current_editing_job_id)
                if job:
                    job.name = name
                    job.source_path = source_path
                    job.destination_path = dest_path
                    job.destination_type = destination_type
                    job.google_drive_folder_id = google_drive_folder_id
                    self.db_session.commit()
                    self.parent.toast("Changes saved")
            else:
                # Creating new job
                job = BackupJob(
                    name=name,
                    source_path=source_path,
                    destination_path=dest_path,
                    destination_type=destination_type,
                    google_drive_folder_id=google_drive_folder_id,
                    is_active=True
                )
                self.db_session.add(job)
                self.db_session.commit()
                self.parent.toast(f"Job created: {name}")

            # Refresh the jobs list, keeping an edited job open in the form
            editing = self.current_editing_job_id is not None
            self.load_backup_jobs()
            if editing:
                self.edit_job(job)
            else:
                self.new_job()

        except Exception as e:
            logger.error(f"Error saving job: {e}")
            CTkMessagebox(
                title="Error",
                message=f"Error saving job: {str(e)}",
                icon="cancel"
            )

    def new_job(self):
        """Clear the job form for a new job"""
        self.current_editing_job_id = None
        self.job_name_var.set("")
        self.source_path_var.set("")
        self.dest_path_var.set("")
        self.dest_type_var.set("Local Directory")
        self.gdrive_folder_var.set("root")
        self.gdrive_folder_id_var.set("root")

        # Show local destination frame, hide Google Drive frame
        self.local_dest_frame.grid()
        self.gdrive_dest_frame.grid_remove()

        self.save_job_button.configure(text="Create job")
        theme.set_enabled(self.delete_job_button, False)
        self.form_title.configure(text="New job")
        self.form_hint.configure(text="Pick a folder to protect and a folder to copy it into.")
        self._highlight_editing_row()

    def edit_job(self, job):
        """Load a job into the edit form"""
        self.current_editing_job_id = job.id
        self.job_name_var.set(job.name)
        self.source_path_var.set(job.source_path)

        # Set destination type and show appropriate frame
        if job.destination_type == DestinationType.GOOGLE_DRIVE:
            self.dest_type_var.set("Google Drive")
            self.local_dest_frame.grid_remove()
            self.gdrive_dest_frame.grid()

            # Extract folder name from destination path
            folder_name = job.destination_path.replace("Google Drive: ", "")
            self.gdrive_folder_var.set(folder_name)
            self.gdrive_folder_id_var.set(job.google_drive_folder_id or "root")
        else:
            self.dest_type_var.set("Local Directory")
            self.local_dest_frame.grid()
            self.gdrive_dest_frame.grid_remove()
            self.dest_path_var.set(job.destination_path)

        self.save_job_button.configure(text="Save changes")
        theme.set_enabled(self.delete_job_button, True)
        self.form_title.configure(text=f"Edit {job.name}")
        self.form_hint.configure(text="Changes apply the next time this job runs.")
        self._highlight_editing_row()

        # Switch to Jobs tab
        self.parent.show_page("Jobs")

    def delete_job(self):
        """Delete the current job"""
        if self.current_editing_job_id is None:
            return

        # Show confirmation dialog
        messagebox = CTkMessagebox(
            title="Confirm Deletion",
            message=f"Delete \"{self.job_name_var.get()}\"? Files already backed up stay where they are.",
            icon="question",
            option_1="Cancel",
            option_2="Delete job"
        )
        response = messagebox.get()

        if response == "Delete job":
            try:
                BackupJob = self.parent.BackupJob
                job = self.db_session.get(BackupJob, self.current_editing_job_id)
                if job:
                    # Mark as inactive instead of deleting permanently
                    job.is_active = False
                    self.db_session.commit()

                    self.parent.toast(f"Job deleted: {job.name}")

                    # Refresh jobs list and clear form
                    self.load_backup_jobs()
                    self.new_job()

            except Exception as e:
                logger.error(f"Error deleting job: {e}")
                CTkMessagebox(
                    title="Error",
                    message=f"Error deleting job: {str(e)}",
                    icon="cancel"
                )