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

        # Create frames
        jobs_tab.grid_columnconfigure(0, weight=1)
        jobs_tab.grid_rowconfigure(0, weight=1)

        # Main frame
        main_frame = ctk.CTkFrame(jobs_tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=2)
        main_frame.grid_rowconfigure(1, weight=1)

        # Run All button, above the jobs list
        jobs_controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        jobs_controls_frame.grid(row=0, column=0, padx=(0, 8), pady=(0, 6), sticky="ew")
        jobs_controls_frame.grid_columnconfigure(0, weight=1)

        self.run_all_button = theme.primary_button(
            jobs_controls_frame,
            text="Run All Jobs",
            command=lambda: self.parent.batch_jobs_tab.run_all_jobs()
        )
        self.run_all_button.grid(row=0, column=0, padx=0, pady=0, sticky="e")

        # Jobs list frame
        jobs_list_frame = ctk.CTkScrollableFrame(
            main_frame, label_text="Backup Jobs", label_font=theme.FONT_H1,
            fg_color=theme.SURFACE, corner_radius=theme.RADIUS,
        )
        jobs_list_frame.grid(row=1, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        jobs_list_frame.grid_columnconfigure(0, weight=1)

        self.jobs_list_frame = jobs_list_frame

        # Job detail/edit frame
        job_edit_frame = theme.card(main_frame)
        job_edit_frame.grid(row=0, column=1, rowspan=2, padx=(8, 0), pady=8, sticky="nsew")

        job_edit_frame.grid_columnconfigure(0, weight=1)
        job_edit_frame.grid_rowconfigure(7, weight=1)

        # Job edit controls
        theme.section_label(job_edit_frame, "Add / Edit Backup Job").grid(
            row=0, column=0, padx=16, pady=(16, 18), sticky="w"
        )

        # Job name
        ctk.CTkLabel(job_edit_frame, text="Job Name", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=1, column=0, padx=16, pady=(0, 5), sticky="w"
        )

        self.job_name_var = ctk.StringVar()
        job_name_entry = ctk.CTkEntry(
            job_edit_frame,
            textvariable=self.job_name_var,
            width=280,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ALT,
            border_color=theme.BORDER,
        )
        job_name_entry.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="w")

        # Source path
        ctk.CTkLabel(job_edit_frame, text="Source Path", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=3, column=0, padx=16, pady=(0, 5), sticky="w"
        )

        source_path_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        source_path_frame.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")

        source_path_frame.grid_columnconfigure(0, weight=1)

        self.source_path_var = ctk.StringVar()
        source_path_entry = ctk.CTkEntry(
            source_path_frame,
            textvariable=self.source_path_var,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ALT,
            border_color=theme.BORDER,
        )
        source_path_entry.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="ew")

        source_browse_button = theme.secondary_button(
            source_path_frame,
            text="Browse",
            width=80,
            command=lambda: self.browse_directory(self.source_path_var)
        )
        source_browse_button.grid(row=0, column=1, padx=0, pady=0)

        # Destination type
        ctk.CTkLabel(job_edit_frame, text="Destination Type", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=5, column=0, padx=16, pady=(0, 5), sticky="w"
        )

        # Destination type selection
        self.dest_type_var = ctk.StringVar(value="Local Directory")
        dest_type_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        dest_type_frame.grid(row=6, column=0, padx=16, pady=(0, 12), sticky="ew")

        dest_type_local = ctk.CTkRadioButton(
            dest_type_frame,
            text="Local Directory",
            font=theme.FONT_BODY,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            variable=self.dest_type_var,
            value="Local Directory",
            command=self.toggle_destination_type
        )
        dest_type_local.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        # Google Drive support is not wired up in this build (see
        # REMEDIATION_PLAN.md Phase 6) — disable rather than leave it broken.
        dest_type_gdrive = ctk.CTkRadioButton(
            dest_type_frame,
            text="Google Drive",
            font=theme.FONT_BODY,
            variable=self.dest_type_var,
            value="Google Drive",
            command=self.toggle_destination_type,
            state="disabled"
        )
        dest_type_gdrive.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(
            dest_type_frame,
            text="(not available in this build)",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_MUTED
        ).grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")

        # Destination path
        ctk.CTkLabel(job_edit_frame, text="Destination Path", font=theme.FONT_BODY_BOLD,
                     text_color=theme.TEXT_MUTED).grid(
            row=7, column=0, padx=16, pady=(0, 5), sticky="w"
        )

        # Local destination frame
        self.local_dest_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        self.local_dest_frame.grid(row=8, column=0, padx=16, pady=(0, 12), sticky="ew")
        self.local_dest_frame.grid_columnconfigure(0, weight=1)

        self.dest_path_var = ctk.StringVar()
        dest_path_entry = ctk.CTkEntry(
            self.local_dest_frame,
            textvariable=self.dest_path_var,
            font=theme.FONT_BODY,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.SURFACE_ALT,
            border_color=theme.BORDER,
        )
        dest_path_entry.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="ew")

        dest_browse_button = theme.secondary_button(
            self.local_dest_frame,
            text="Browse",
            width=80,
            command=lambda: self.browse_directory(self.dest_path_var)
        )
        dest_browse_button.grid(row=0, column=1, padx=0, pady=0)

        # Google Drive destination frame
        self.gdrive_dest_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        self.gdrive_dest_frame.grid(row=8, column=0, padx=16, pady=(0, 12), sticky="ew")
        self.gdrive_dest_frame.grid_columnconfigure(0, weight=1)

        # Google Drive folder selection
        self.gdrive_folder_var = ctk.StringVar(value="root")
        self.gdrive_folder_id_var = ctk.StringVar(value="root")

        gdrive_folder_label = ctk.CTkLabel(
            self.gdrive_dest_frame,
            text="Selected Folder:",
            font=theme.FONT_BODY,
        )
        gdrive_folder_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.gdrive_folder_display = ctk.CTkLabel(
            self.gdrive_dest_frame,
            textvariable=self.gdrive_folder_var,
            font=theme.FONT_BODY_BOLD
        )
        self.gdrive_folder_display.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        gdrive_select_button = theme.secondary_button(
            self.gdrive_dest_frame,
            text="Select Folder",
            width=100,
            command=self.select_google_drive_folder
        )
        gdrive_select_button.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        # Hide Google Drive frame by default
        self.gdrive_dest_frame.grid_remove()

        # Buttons
        buttons_frame = ctk.CTkFrame(job_edit_frame, fg_color="transparent")
        buttons_frame.grid(row=9, column=0, padx=12, pady=(16, 16), sticky="ew")

        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.save_job_button = theme.primary_button(
            buttons_frame,
            text="Save",
            command=self.save_job
        )
        self.save_job_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.new_job_button = theme.secondary_button(
            buttons_frame,
            text="New",
            command=self.new_job
        )
        self.new_job_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.delete_job_button = theme.danger_button(
            buttons_frame,
            text="Delete",
            command=self.delete_job
        )
        self.delete_job_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        # Initialize editing state
        self.new_job()

    def load_backup_jobs(self):
        """Load existing backup jobs from the database"""
        try:
            # Clear existing jobs list
            for widget in self.jobs_list_frame.winfo_children():
                widget.destroy()

            # Get all active jobs
            BackupJob = self.parent.BackupJob
            jobs = self.db_session.query(BackupJob).filter_by(is_active=True).all()

            # Update parent's job selection dropdown
            backup_tab = self.parent.backup_tab
            backup_tab.job_ids_by_name = {job.name: job.id for job in jobs}
            if jobs:
                job_names = [job.name for job in jobs]
                backup_tab.job_selection.configure(values=job_names)
                backup_tab.job_selection_var.set(jobs[0].name)
                backup_tab.on_job_selected(jobs[0].name)
            else:
                backup_tab.job_selection.configure(values=["No jobs available"])
                backup_tab.job_selection_var.set("No jobs available")
                backup_tab.update_job_details(None)

            # Add jobs to the jobs list
            if not jobs:
                ctk.CTkLabel(
                    self.jobs_list_frame, text="No backup jobs yet — create one on the right.",
                    font=theme.FONT_BODY, text_color=theme.TEXT_MUTED,
                ).grid(row=0, column=0, padx=10, pady=20, sticky="w")

            for i, job in enumerate(jobs):
                job_frame = ctk.CTkFrame(self.jobs_list_frame, fg_color=theme.SURFACE_ALT,
                                          corner_radius=theme.RADIUS_SM)
                job_frame.grid(row=i, column=0, padx=6, pady=6, sticky="ew")
                job_frame.grid_columnconfigure(0, weight=1)

                # Job Name
                ctk.CTkLabel(job_frame, text=job.name, font=theme.FONT_H2).grid(
                    row=0, column=0, padx=12, pady=(10, 4), sticky="w"
                )

                # Source Path
                source_text = f"Source: {job.source_path}"
                if len(source_text) > 40:
                    source_text = source_text[:37] + "..."
                ctk.CTkLabel(job_frame, text=source_text, font=theme.FONT_SMALL,
                             text_color=theme.TEXT_MUTED).grid(
                    row=1, column=0, padx=12, pady=0, sticky="w"
                )

                # Last Backup
                last_backup = "Never" if not job.last_backup else job.last_backup.strftime("%Y-%m-%d %H:%M")
                ctk.CTkLabel(job_frame, text=f"Last Backup: {last_backup}", font=theme.FONT_SMALL,
                             text_color=theme.TEXT_MUTED).grid(
                    row=2, column=0, padx=12, pady=(0, 10), sticky="w"
                )

                # Edit button
                edit_button = theme.secondary_button(
                    job_frame,
                    text="Edit",
                    width=60,
                    command=lambda j=job: self.edit_job(j)
                )
                edit_button.grid(row=0, column=1, rowspan=3, padx=12, pady=10)

        except Exception as e:
            logger.error(f"Error loading backup jobs: {e}")
            self.parent.log_message(f"Error loading backup jobs: {e}")

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

            folder_listbox = tk.Listbox(folder_frame, bg="#2b2b2b", fg="white", selectbackground="#1f538d")
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
            CTkMessagebox(
                title="Error",
                message="Job name and source path are required",
                icon="cancel"
            )
            return

        if not os.path.isdir(source_path):
            CTkMessagebox(
                title="Error",
                message="Source path is not a valid directory",
                icon="cancel"
            )
            return

        # Validate destination based on type
        if dest_type == "Local Directory":
            if not dest_path:
                CTkMessagebox(
                    title="Error",
                    message="Destination path is required",
                    icon="cancel"
                )
                return

            if not os.path.isdir(dest_path):
                CTkMessagebox(
                    title="Error",
                    message="Destination path is not a valid directory",
                    icon="cancel"
                )
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
                CTkMessagebox(
                    title="Error",
                    message="An active job with this name already exists",
                    icon="cancel"
                )
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
                    CTkMessagebox(
                        title="Success",
                        message="Job updated successfully",
                        icon="check"
                    )
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
                CTkMessagebox(
                    title="Success",
                    message="Job created successfully",
                    icon="check"
                )

            # Refresh the jobs list
            self.load_backup_jobs()
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

        self.save_job_button.configure(text="Create Job")
        self.delete_job_button.configure(state="disabled", fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER)

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

        self.save_job_button.configure(text="Update Job")
        self.delete_job_button.configure(state="normal", fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER)

        # Switch to Jobs tab
        self.parent.tab_view.set("Jobs")

    def delete_job(self):
        """Delete the current job"""
        if self.current_editing_job_id is None:
            return

        # Show confirmation dialog
        messagebox = CTkMessagebox(
            title="Confirm Deletion",
            message="Are you sure you want to delete this job?",
            icon="question",
            option_1="Cancel",
            option_2="Delete"
        )
        response = messagebox.get()

        if response == "Delete":
            try:
                BackupJob = self.parent.BackupJob
                job = self.db_session.get(BackupJob, self.current_editing_job_id)
                if job:
                    # Mark as inactive instead of deleting permanently
                    job.is_active = False
                    self.db_session.commit()

                    CTkMessagebox(
                        title="Success",
                        message="Job deleted successfully",
                        icon="check"
                    )

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