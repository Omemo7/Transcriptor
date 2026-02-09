import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
import queue
import time
import transcribe_module


class MediaItem(ctk.CTkFrame):
    """
    Represents a single row in the scrollable list.
    """
    def __init__(self, parent, file_path, app_manager):
        super().__init__(parent)
        self.app = app_manager
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.transcription_text = ""
        self.state = "idle"  # idle, waiting, processing, done, error, stopped
        
        # Create a unique recovery filename
        safe_name = "".join([c for c in self.filename if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        self.recovery_file = f"recovery_{safe_name}.txt"

        # --- UI LAYOUT ---
        self.grid_columnconfigure(1, weight=1) 
        
        # 1. Filename
        self.lbl_name = ctk.CTkLabel(self, text=self.filename, anchor="w", font=("Arial", 12, "bold"))
        self.lbl_name.grid(row=0, column=0, columnspan=2, padx=10, pady=(5,0), sticky="ew")

        # 2. Status
        self.lbl_status = ctk.CTkLabel(self, text="Idle", text_color="gray", font=("Arial", 11))
        self.lbl_status.grid(row=0, column=2, padx=10, pady=(5,0), sticky="e")

        # 3. Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, height=8)
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="ew")
        self.progress_bar.set(0)

        # 4. Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=0, column=3, rowspan=2, padx=5, pady=5, sticky="e")

        self.btn_start = ctk.CTkButton(self.btn_frame, text="▶", width=30, height=30, 
                                       command=self.request_start, fg_color="green")
        self.btn_start.pack(side="left", padx=2)

        self.btn_stop = ctk.CTkButton(self.btn_frame, text="⏹", width=30, height=30, 
                                      command=self.request_stop, fg_color="#c0392b", state="disabled")
        self.btn_stop.pack(side="left", padx=2)

        self.btn_copy = ctk.CTkButton(self.btn_frame, text="Copy", width=50, height=30, 
                                      command=self.copy_text, state="disabled")
        self.btn_copy.pack(side="left", padx=2)

        self.btn_save = ctk.CTkButton(self.btn_frame, text="Save", width=50, height=30, 
                                      command=self.save_text, state="disabled")
        self.btn_save.pack(side="left", padx=2)

        self.cancel_flag = False

    # --- METHODS THAT WERE MISSING ---
    def request_start(self):
        if self.state in ["processing", "waiting"]: return
        self.reset_ui()
        self.app.add_to_queue(self)
        self.update_status("Waiting...", "waiting")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

    def request_stop(self):
        self.cancel_flag = True
        if self.state == "waiting":
            self.update_status("Cancelled", "idle")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
        elif self.state == "processing":
            self.update_status("Stopping...", "stopped")
            self.btn_stop.configure(state="disabled")

    def update_status(self, text, state_code):
        self.state = state_code
        self.lbl_status.configure(text=text)
        if state_code == "done": self.lbl_status.configure(text_color="#2ecc71")
        elif state_code == "error": self.lbl_status.configure(text_color="#e74c3c")
        elif state_code == "processing": self.lbl_status.configure(text_color="#3498db")
        else: self.lbl_status.configure(text_color="gray")

    def reset_ui(self):
        self.transcription_text = ""
        self.progress_bar.set(0)
        self.cancel_flag = False
        self.btn_copy.configure(state="disabled")
        self.btn_save.configure(state="disabled")
        with open(self.recovery_file, "w", encoding="utf-8") as f:
            f.write("")

    def on_progress(self, percent, chunk_text):
        self.progress_bar.set(percent)
        self.lbl_status.configure(text=f"Processing {int(percent*100)}%")
        if chunk_text:
            self.transcription_text += chunk_text + " "

    def finish_success(self):
        self.progress_bar.set(1)
        self.update_status("Completed", "done")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_copy.configure(state="normal")
        self.btn_save.configure(state="normal")

    def finish_stopped(self):
        self.update_status("Stopped", "idle")
        self.progress_bar.set(0)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def finish_error(self, err_msg):
        self.update_status(f"Error: {err_msg}", "error")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    # --- THESE WERE LIKELY MISSING IN YOUR FILE ---
    def copy_text(self):
        if os.path.exists(self.recovery_file):
            try:
                with open(self.recovery_file, "r", encoding="utf-8") as f:
                    text = f.read()
                self.app.clipboard_clear()
                self.app.clipboard_append(text)
                messagebox.showinfo("Copied", f"Text for {self.filename} copied!")
            except: pass

    def save_text(self):
        if not os.path.exists(self.recovery_file): return
        default_name = f"{os.path.splitext(self.filename)[0]}_transcript.txt"
        save_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default_name)
        if save_path:
            with open(self.recovery_file, "r", encoding="utf-8") as src, open(save_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())