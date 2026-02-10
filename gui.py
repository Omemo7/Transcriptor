import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
import queue
import transcribe_module
import time
from media_item import MediaItem


# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TranscriptorQueueApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- WINDOW SETUP ---
        self.title("Transcriptor")
        self.iconbitmap("icon.ico")
        self.after(0, lambda: self.state('zoomed'))
        self.grid_rowconfigure(1, weight=1) # Scroll area expands
        self.grid_columnconfigure(0, weight=1)

        # --- 1. HEADER ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        self.btn_add = ctk.CTkButton(self.header_frame, text="+ Add Media Files", 
                                     command=self.add_files, font=("Arial", 14, "bold"), width=200)
        self.btn_add.pack(side="left", padx=10, pady=10)

        self.lbl_info = ctk.CTkLabel(self.header_frame, text="Queue: Files process automatically one-by-one.", text_color="gray")
        self.lbl_info.pack(side="left", padx=10)

        # --- 2. SCROLLABLE QUEUE AREA ---
        self.scroll_area = ctk.CTkScrollableFrame(self, label_text="Transcription Queue")
        self.scroll_area.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)
        self.scroll_area.grid_columnconfigure(0, weight=1) # Items expand width

        # --- 3. GLOBAL FOOTER ---
        self.footer = ctk.CTkFrame(self)
        self.footer.grid(row=2, column=0, sticky="ew", padx=20, pady=20)

        self.btn_save_all = ctk.CTkButton(self.footer, text="Save All Finished", command=self.save_all_finished)
        self.btn_save_all.pack(side="left", padx=10, pady=10)

        self.btn_stop_all = ctk.CTkButton(self.footer, text="Stop All", command=self.stop_all, fg_color="#c0392b")
        self.btn_stop_all.pack(side="right", padx=10)

        self.btn_start_all = ctk.CTkButton(self.footer, text="Start All Pending", command=self.start_all_pending, fg_color="green")
        self.btn_start_all.pack(side="right", padx=10)

        # --- VARIABLES ---
        self.items = [] 
        self.job_queue = queue.Queue()
        
        # Start the background worker
        self.start_worker_thread()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        try:
            for file in os.listdir("."):
                if file.startswith("recovery_") and file.endswith(".txt"):
                    try:
                        os.remove(file)
                    except: pass # Skip if still locked by another instance
        except: pass

    def start_worker_thread(self):
        self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker_thread.start()

    def add_files(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("Media Files", "*.mp3 *.mp4 *.wav *.m4a *.mkv")])
        for path in file_paths:
            item = MediaItem(self.scroll_area, path, self)
            item.pack(fill="x", pady=2, padx=5)
            self.items.append(item)

    # --- QUEUE MANAGEMENT ---
    def add_to_queue(self, media_item):
        self.job_queue.put(media_item)

    def start_all_pending(self):
        for item in self.items:
            if item.state in ["idle", "stopped", "error"]:
                item.request_start()

    def stop_all(self):
        # Mark all items to stop
        for item in self.items:
            if item.state in ["waiting", "processing"]:
                item.request_stop()

    def save_all_finished(self):
        done_items = [i for i in self.items if i.state == "done"]
        if not done_items:
            messagebox.showinfo("Info", "No finished items to save.")
            return

        folder = filedialog.askdirectory(title="Select Folder to Save All Transcripts")
        if folder:
            count = 0
            for item in done_items:
                if os.path.exists(item.recovery_file):
                    name = f"{os.path.splitext(item.filename)[0]}.txt"
                    path = os.path.join(folder, name)
                    try:
                        with open(item.recovery_file, "r", encoding="utf-8") as src, open(path, "w", encoding="utf-8") as dst:
                            dst.write(src.read())
                        count += 1
                    except: pass
            messagebox.showinfo("Success", f"Saved {count} files to {folder}")


    def remove_from_list(self, item_to_remove):
        if item_to_remove in self.items:
            self.items.remove(item_to_remove)

    # [ADD THIS NEW METHOD]
    def on_closing(self):
        """
        Runs when the user clicks the X button.
        Stops threads and deletes all temp files.
        """
        # 1. Stop any running transcription
        self.stop_all()

        self.update() 
        time.sleep(0.1)
        
        # 2. Delete recovery files for ALL items in the list
        for item in self.items:
            if os.path.exists(item.recovery_file):
                try:
                    os.remove(item.recovery_file) # Delete the file
                except Exception: 
                    pass # If file is open or locked, just skip it

        # 3. Actually close the window
        self.destroy()
        os._exit(0) # Force kill any remaining background threads
    # --- WORKER LOOP (Single Thread for Safety) ---
    # --- WORKER LOOP (Fixed: Locks variable to correct row) ---
    def worker_loop(self):
        while True:
            try:
                # 1. Get next job
                current_item = self.job_queue.get()
                
                # FIX: We use 'target=current_item' in the lambda.
                # This freezes the variable so the GUI updates the CORRECT row,
                # even if the worker has already moved to the next file.

                if current_item.cancel_flag:
                    self.after(0, lambda target=current_item: target.finish_stopped())
                    self.job_queue.task_done()
                    continue

                self.after(0, lambda target=current_item: target.update_status("Processing...", "processing"))

                try:
                    with open(current_item.recovery_file, "a", encoding="utf-8") as f:
                        
                        def on_progress(percent, chunk_text):
                            if chunk_text:
                                f.write(chunk_text + " ")
                                f.flush()
                            # FIX: Capture 'target' here too
                            self.after(0, lambda target=current_item: target.on_progress(percent, chunk_text))
                        
                        def check_cancel(): 
                            return current_item.cancel_flag

                        transcribe_module.run_transcription(
                            current_item.file_path,
                            progress_callback=on_progress,
                            check_cancel=check_cancel
                        )
                    
                    if current_item.cancel_flag:
                        self.after(0, lambda target=current_item: target.finish_stopped())
                    else:
                        # FIX: Capture 'target'. This prevents the "Stuck at 100%" bug!
                        self.after(0, lambda target=current_item: target.finish_success())
                
                except Exception as e:
                    self.after(0, lambda target=current_item: target.finish_error(str(e)))

                self.job_queue.task_done()
            
            except Exception as e:
                print(f"Queue Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    app = TranscriptorQueueApp()
    app.mainloop()





