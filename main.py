import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
import queue
import transcribe_module
import time
from media_item import MediaItem

import global_vars
from util import Util

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class TranscriptorQueueApp(ctk.CTk):
    def __init__(self):
        super().__init__()

       
        os.makedirs(global_vars.rec_folder, exist_ok=True)

        # --- WINDOW SETUP ---
        self.title("Transcriptor")
        self.iconbitmap("icon.ico")
        self.after(0, lambda: self.state('zoomed'))
        self.minsize(600, 400)
        self.grid_rowconfigure(1, weight=1) # Scroll area expands
        self.grid_columnconfigure(0, weight=1)

             # --- VARIABLES ---
        self.items = [] 
        self.job_queue = queue.Queue()
        self.total_duration=0
        

        # --- 1. HEADER ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        # IMPORTANT: Responsiveness Configuration
        # This tells the frame: "Column 1 (the progress bar) gets all the extra space"
        self.header_frame.grid_columnconfigure(1, weight=1)

        # 1. Add Button (Fixed width, Left side)
        self.btn_add = ctk.CTkButton(
            self.header_frame, 
            text="+ Add Media Files", 
            command=self.add_files, 
            font=("Arial", 13, "bold"), 
            width=140,
            height=35
        )
        self.btn_add.grid(row=0, column=0, padx=(0, 15), sticky="w")

        # 2. Progress Bar (Flexible width, Middle)
        self.progress_bar = ctk.CTkProgressBar(self.header_frame, height=12)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=5)
        self.progress_bar.grid_remove()

        self.progress_bar.set(0) # Start empty

        # 3. Counter Label (e.g., "12/50") - Fixed width, Right of bar
        self.lbl_progress_count = ctk.CTkLabel(
            self.header_frame, 
            text="", 
            font=("Arial", 12, "bold"),
            text_color=("gray10", "gray90") # Adaptive color for light/dark mode
        )
        self.lbl_progress_count.grid(row=0, column=2, padx=(5, 15))

        # 4. Total Duration Label (Fixed width, Far Right)
        # Assuming you have a format_duration function defined elsewhere
        formatted_time = Util.format_duration(self.total_duration)
        self.lbl_total_duration = ctk.CTkLabel(
            self.header_frame, 
            text=f'Total: {formatted_time}', 
            text_color="gray", 
            font=("Arial", 12)
        )
        self.lbl_total_duration.grid(row=0, column=3, sticky="e",padx=20)



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

   
        # Start the background worker
        self.start_worker_thread()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        

    def start_worker_thread(self):
        self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        self.worker_thread.start()




    def update_total_duration_label(self):
        self.lbl_total_duration.configure(text=f'Total Duration: {Util.format_duration(self.total_duration)}')

    
    def add_files(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("Media Files", "*.mp3 *.mp4 *.wav *.m4a *.mkv")])
        for path in file_paths:
            item = MediaItem(self.scroll_area, path, self,on_delete_click=self.delete_item)
            item.pack(fill="x", pady=2, padx=5)
            self.items.append(item)
            self.total_duration=self.total_duration+item.durationInSeconds
            self.update_total_duration_label()
            self.progress_bar.grid()
            self.update_total_progress()

            

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



    def delete_item(self, item_to_remove):
        """
        Removes the item.
        """
        if item_to_remove in self.items:
            self.total_duration=self.total_duration-item_to_remove.durationInSeconds
            self.update_total_duration_label()
            self.items.remove(item_to_remove)
            item_to_remove.pack_forget() # Hide immediately so it looks deleted
            item_to_remove.request_stop()
            self.after(0, self.update_total_progress)
        else: print("item is not found in items")

    def delete_recovery_file(self,item):
        if os.path.exists(item.recovery_file):
            try:
                os.remove(item.recovery_file)
                print('deleted')
            except Exception as e:
                print(f"Failed to delete: {e}")
        item.destroy()

    def remove_from_list(self, item_to_remove):
        if item_to_remove in self.items:
            self.items.remove(item_to_remove)

    # [ADD THIS NEW METHOD]
    




    def on_closing(self):
        # 1. Stop threads
        self.stop_all()
        
        # 2. Update UI briefly to let threads react
        # (This pumps the message loop so workers can receive the stop signal)
        start = time.time()
        while time.time() - start < 0.5:
            self.update()
            time.sleep(0.05)

        # 3. Nuke the folder (Retries for 2 seconds: 20 attempts * 0.1s)
        Util.force_delete_folder(global_vars.rec_folder, max_retries=20, delay=0.1)

        # 4. Exit
        self.destroy()
        os._exit(0)


    def update_total_progress(self):
        totalCount=len(self.items)
        if totalCount==0: 
            self.lbl_progress_count.configure(text="")
            self.progress_bar.grid_remove()
            return
        doneCount=sum([1 for x in self.items if x.state=="done"])
        percentage=doneCount/totalCount
        self.progress_bar.set(percentage)
        self.lbl_progress_count.configure(text=f"{doneCount}/{totalCount}")


    class UserCancelled(Exception): 
        pass

    def worker_loop(self):
        while True:
            try:
                
                # 1. Get next job
                current_item = self.job_queue.get()
                
                # ... (your existing setup code) ...
                
                if current_item.cancel_flag:
                    # ... (your existing skip logic) ...
                    self.job_queue.task_done()
                    continue

                self.after(0, lambda target=current_item: target.update_status("Processing...", "processing"))

                try:
                    with open(current_item.recovery_file, "w", encoding="utf-8") as f:
                        
                        # --- CHANGE 1: Force stop in on_progress ---
                        def on_progress(percent, chunk_text):
                            if current_item.cancel_flag:
                                raise self.UserCancelled()  # <--- CRITICAL: Abort immediately!
                                
                            if chunk_text:
                                f.write(chunk_text + " ")
                                f.flush()
                            self.after(0, lambda target=current_item: target.on_progress(percent, chunk_text))
                        
                        # --- CHANGE 2: Force stop in check_cancel ---
                        def check_cancel(): 
                            if current_item.cancel_flag:
                                raise self.UserCancelled()  # <--- CRITICAL: Abort immediately!
                            return False

                        transcribe_module.run_transcription(
                            current_item.file_path,
                            progress_callback=on_progress,
                            check_cancel=check_cancel
                        )
                    
                    # If we get here, it finished successfully
                    self.after(0, lambda target=current_item: target.finish_success())
                    self.after(0, self.update_total_progress)

                # --- CHANGE 3: Catch the forced stop ---
                except self.UserCancelled:
                    # This block runs INSTANTLY when you raise the exception above
                    self.delete_recovery_file(current_item)
                    self.after(0, lambda target=current_item: target.finish_stopped())

                except Exception as e:
                    self.delete_recovery_file(current_item)
                    # This handles actual errors
                    self.after(0, lambda target=current_item: target.finish_error(str(e)))

                self.job_queue.task_done()
            except Exception as e:
                print(f"Queue Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    app = TranscriptorQueueApp()
    app.mainloop()





