import customtkinter as ctk
import threading
from tkinter import filedialog, messagebox
import os
import queue
import transcribe_module

class TranscriptorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- WINDOW SETUP ---
        self.title("Jordanian Transcriptor (Clean)")
        self.geometry("900x260") # Compact height since no text area
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.grid_columnconfigure(0, weight=1)

        # 1. Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.btn_select = ctk.CTkButton(self.header_frame, text="Select Media File", 
                                      command=self.select_file, width=160, font=("Arial", 14, "bold"))
        self.btn_select.pack(side="left", padx=10, pady=10)

        self.lbl_filename = ctk.CTkLabel(self.header_frame, text="No file selected", text_color="gray")
        self.lbl_filename.pack(side="left", padx=10)

        # 2. Status & Progress
        self.lbl_status = ctk.CTkLabel(self, text="Select file", font=("Arial", 12))
        self.lbl_status.grid(row=1, column=0, padx=25, pady=(0, 6), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")
        self.progress_bar.set(0)

        # 3. Footer Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.btn_save = ctk.CTkButton(self.btn_frame, text="Save As", command=self.save_to_file, 
                                    state="disabled", fg_color="gray", width=140)
        self.btn_save.pack(side="left", padx=0)

        self.btn_copy = ctk.CTkButton(self.btn_frame, text="Copy Text", command=self.copy_text, 
                                    state="disabled", fg_color="gray", width=140)
        self.btn_copy.pack(side="left", padx=10)

        self.btn_start = ctk.CTkButton(self.btn_frame, text="Start Transcription", command=self.start_thread, 
                                     state="disabled", fg_color="green", width=180)
        self.btn_start.pack(side="right", padx=0)

        self.btn_stop= ctk.CTkButton(self.btn_frame, text="Stop", command=self.stop_process, 
                                     state="disabled", fg_color="red", width=140)
        self.btn_stop.pack(side="right",padx=10)


        

        # Variables
        self.file_path = None
        self.stop_event = threading.Event()
        self.ui_queue = queue.Queue()
        self.recovery_file = "recovery_log.txt"

        # Start Listener
        self.after(100, self._check_queue)

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp3 *.mp4 *.wav *.m4a *.mkv")])
        if file_path:
            self.file_path = file_path
            self.lbl_filename.configure(text=os.path.basename(file_path))
            self.btn_start.configure(state="normal")
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Ready.")
            self.disable_copy_and_save_buttons()


    def enable_copy_and_save_buttons(self):
        self.btn_copy.configure(state="normal", fg_color="#1f6aa5")
        self.btn_save.configure(state="normal", fg_color="#1f6aa5")
    def disable_copy_and_save_buttons(self):
        self.btn_copy.configure(state="disabled", fg_color="gray")
        self.btn_save.configure(state="disabled", fg_color="gray")

    def stop_process(self):
        # 1. Signal the running thread to stop
        # This sets the internal flag to true. Your run_logic loop must check for this.
        self.stop_event.set()
        
    

    def start_thread(self):
        if not self.file_path: return
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", text="Processing...")
        self.btn_stop.configure(state="normal")
        self.btn_select.configure(state="disabled")
        self.disable_copy_and_save_buttons()
        self.progress_bar.set(0)
        
        # Clear previous recovery file
        with open(self.recovery_file, "w", encoding="utf-8") as f:
            f.write("")

        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        try:
            # Open file ONCE for writing
            with open(self.recovery_file, "a", encoding="utf-8") as f:
                
                def on_progress(percent, chunk_text):
                    # Write to disk immediately
                    if chunk_text:
                        f.write(chunk_text + " ")
                        f.flush()
                    
                    # Notify GUI (Percent ONLY, no text)
                    self.ui_queue.put(("PROGRESS", percent))

                transcribe_module.run_transcription(
                    audio_path=self.file_path,
                    progress_callback=on_progress,
                    status_callback=lambda msg: self.ui_queue.put(("STATUS", msg)),
                    check_cancel=self.stop_event.is_set
                )
            if self.stop_event.is_set():
                self.ui_queue.put(("STOPPED", None)) # Send a specific stop signal
            else:
                self.ui_queue.put(("DONE", None))
            

        except Exception as e:
            self.ui_queue.put(("CRASH", str(e)))

    def _check_queue(self):
        try:
            while not self.ui_queue.empty():
                kind, payload = self.ui_queue.get_nowait()

                if kind == "PROGRESS":
                    self.progress_bar.set(payload)
                    self.lbl_status.configure(text=f"Transcribing... {int(payload*100)}%")
                
                elif kind == "STATUS":
                    self.lbl_status.configure(text=payload)
                
                elif kind == "DONE":
                    self.lbl_status.configure(text="Complete!")
                    self.progress_bar.set(1)
                    self._configure_enabled_controls_on_done()
                    messagebox.showinfo("Success", "Transcription Finished!")
                
                elif kind == "STOPPED":
                    self.lbl_status.configure(text="Ready.")
                    self.progress_bar.set(0)
                    self.disable_copy_and_save_buttons()
                    self.btn_start.configure(state="normal", text="Start Transcription")
                    self.btn_select.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    messagebox.showinfo("Stopped", "Transcription was stopped!")
                elif kind == "CRASH":
                    self.lbl_status.configure(text="Error")
                    self._configure_enabled_controls_on_crash()
                    messagebox.showerror("Error", f"Worker Error:\n{payload}")

        except queue.Empty:
            pass
        self.after(100, self._check_queue)

    def _configure_enabled_controls_on_done(self):
        self.btn_start.configure(state="disabled", text="Start Transcription")
        self.btn_stop.configure(state="disabled")
        self.btn_select.configure(state="normal")
        self.enable_copy_and_save_buttons()

    def _configure_enabled_controls_on_crash(self):
        self.btn_start.configure(state="normal", text="Start Transcription")
        self.btn_stop.configure(state="disabled")
        self.btn_select.configure(state="normal")
        self.enable_copy_and_save_buttons()
        



    def copy_text(self):
        # Read from the file since there is no textbox
        if os.path.exists(self.recovery_file):
            try:
                with open(self.recovery_file, "r", encoding="utf-8") as f:
                    text = f.read()
                self.clipboard_clear()
                self.clipboard_append(text)
                self.lbl_status.configure(text="Copied to Clipboard")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def save_to_file(self):
        if not os.path.exists(self.recovery_file): return
        
        default_name = "transcription.txt"
        if self.file_path:
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            default_name = f"{base_name}_transcription.txt"

        save_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default_name)
        if save_path:
            with open(self.recovery_file, "r", encoding="utf-8") as src, open(save_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            self.lbl_status.configure(text="Saved!")

if __name__ == "__main__":
    app = TranscriptorApp()
    app.mainloop()