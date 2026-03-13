import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import video_engine
import time
import sys
import datetime
import shutil

class NullWriter:
    def write(self, arg): pass
    def flush(self): pass

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

class FastClipApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FastClip - 智慧剪輯師")
        self.root.geometry("500x530")
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f9fa")

        # Styles
        style = ttk.Style()
        style.configure("TButton", font=("Microsoft JhengHei", 9))
        style.configure("TLabel", font=("Microsoft JhengHei", 9), background="#f8f9fa")
        
        main_frame = tk.Frame(root, bg="#f8f9fa", padx=15, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main_frame, text="🎬 FastClip 智慧剪輯師", font=("Microsoft JhengHei", 14, "bold"), bg="#f8f9fa", fg="#2c3e50").pack(pady=(0, 10))

        # Media Directory
        tk.Label(main_frame, text="1. 素材資料夾:", bg="#f8f9fa", font=("Microsoft JhengHei", 9, "bold")).pack(anchor="w")
        dir_frame = tk.Frame(main_frame, bg="#f8f9fa")
        dir_frame.pack(fill="x", pady=(2, 2))
        self.media_dir_var = tk.StringVar()
        tk.Entry(dir_frame, textvariable=self.media_dir_var, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(dir_frame, text="瀏覽...", command=self.browse_dir).pack(side="right")
        
        self.count_label = tk.Label(main_frame, text="尚未選取素材", bg="#f8f9fa", fg="#3498db", font=("Microsoft JhengHei", 8))
        self.count_label.pack(anchor="w", pady=(0, 8))

        # Smart Inputs (Side by Side)
        settings_frame = tk.LabelFrame(main_frame, text="素材時長設定 (秒)", bg="#f8f9fa", font=("Microsoft JhengHei", 8), padx=10, pady=5)
        settings_frame.pack(fill="x", pady=5)

        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(2, weight=1)
        settings_frame.columnconfigure(3, weight=1)

        tk.Label(settings_frame, text="照片 (2~5):", bg="#f8f9fa").grid(row=0, column=0, sticky="e")
        self.photo_dur_var = tk.StringVar(value="3")
        self.photo_dur_var.trace_add("write", lambda *args: self.auto_calc_total())
        tk.Entry(settings_frame, textvariable=self.photo_dur_var, width=8).grid(row=0, column=1, sticky="w", padx=(5, 20))

        tk.Label(settings_frame, text="影片 (5~30):", bg="#f8f9fa").grid(row=0, column=2, sticky="e")
        self.video_dur_var = tk.StringVar(value="8")
        self.video_dur_var.trace_add("write", lambda *args: self.auto_calc_total())
        tk.Entry(settings_frame, textvariable=self.video_dur_var, width=8).grid(row=0, column=3, sticky="w", padx=(5, 0))

        # Audio Source
        tk.Label(main_frame, text="2. 背景音樂 (YouTube 網址或檔案):", bg="#f8f9fa", font=("Microsoft JhengHei", 9, "bold")).pack(anchor="w", pady=(5, 0))
        audio_frame = tk.Frame(main_frame, bg="#f8f9fa")
        audio_frame.pack(fill="x", pady=(2, 8))
        self.audio_source_var = tk.StringVar()
        tk.Entry(audio_frame, textvariable=self.audio_source_var, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(audio_frame, text="選擇...", command=self.browse_audio).pack(side="right")

        # Output Directory
        tk.Label(main_frame, text="3. 儲存路徑:", bg="#f8f9fa", font=("Microsoft JhengHei", 9, "bold")).pack(anchor="w")
        out_frame = tk.Frame(main_frame, bg="#f8f9fa")
        out_frame.pack(fill="x", pady=(2, 8))
        self.output_dir_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop"))
        tk.Entry(out_frame, textvariable=self.output_dir_var, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(out_frame, text="瀏覽...", command=self.browse_output_dir).pack(side="right")

        # Total Duration (Read Only)
        self.total_dur_text = tk.StringVar(value="預估影片長度: 0 分 0 秒")
        self.total_dur_label = tk.Label(main_frame, textvariable=self.total_dur_text, bg="#f8f9fa", font=("Microsoft JhengHei", 10, "bold"), fg="#e67e22")
        self.total_dur_label.pack(anchor="w", pady=5)
        self.calculated_total_sec = 0

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(10, 5))
        self.status_label = tk.Label(main_frame, text="就緒", bg="#f8f9fa", fg="#7f8c8d", font=("Microsoft JhengHei", 8))
        self.status_label.pack()

        # Action Buttons
        self.start_btn = tk.Button(main_frame, text="立即產出影片", command=self.start_process, font=("Microsoft JhengHei", 11, "bold"), bg="#27ae60", fg="white", padx=15, pady=5, relief="flat")
        self.start_btn.pack(pady=(10, 0))

        self.file_counts = {"img": 0, "vid": 0}

    def browse_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.media_dir_var.set(directory)
            self.update_file_counts(directory)

    def update_file_counts(self, directory):
        valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        valid_vid_exts = ('.mp4', '.mov', '.avi')
        try:
            files = os.listdir(directory)
            img_count = len([f for f in files if f.lower().endswith(valid_img_exts)])
            vid_count = len([f for f in files if f.lower().endswith(valid_vid_exts)])
            self.file_counts = {"img": img_count, "vid": vid_count}
            self.count_label.config(text=f"偵測到：{img_count} 張照片，{vid_count} 段影片")
            self.auto_calc_total()
        except Exception:
            self.count_label.config(text="讀取資料夾出錯", fg="red")

    def auto_calc_total(self):
        try:
            p_dur = float(self.photo_dur_var.get() or 0)
            v_dur = float(self.video_dur_var.get() or 0)
            num_total = self.file_counts["img"] + self.file_counts["vid"]
            if num_total == 0: 
                self.total_dur_text.set("預估影片長度: 0 分 0 秒")
                self.calculated_total_sec = 0
                return

            total_sec = (self.file_counts["img"] * p_dur) + (self.file_counts["vid"] * v_dur)
            total_sec -= (num_total - 1) * 0.5
            total_sec = max(1, int(total_sec))
            
            self.calculated_total_sec = total_sec
            self.total_dur_text.set(f"預估影片長度: {total_sec // 60} 分 {total_sec % 60} 秒")
        except ValueError:
            pass

    def browse_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if file_path:
            self.audio_source_var.set(file_path)

    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def update_status(self, text, progress=None):
        self.status_label.config(text=text)
        if progress is not None:
            self.progress_var.set(progress)
        self.root.update_idletasks()

    def start_process(self):
        # Validation
        try:
            p_dur = float(self.photo_dur_var.get())
            if not 2 <= p_dur <= 5: raise ValueError("照片時間需介於 2~5 秒！")
            
            v_max = float(self.video_dur_var.get())
            if not 5 <= v_max <= 30: raise ValueError("影片單段時間需介於 5~30 秒！")
            
            total_sec = self.calculated_total_sec
            if total_sec <= 0: raise ValueError("請先選擇素材資料夾！")
        except ValueError as e:
            messagebox.showerror("驗證錯誤", str(e) if "介於" in str(e) or "素材" in str(e) else "請輸入正確的數字格式！")
            return

        media_dir = self.media_dir_var.get()
        audio_src = self.audio_source_var.get()
        out_dir = self.output_dir_var.get()
        
        if not media_dir or not audio_src or not out_dir:
            messagebox.showerror("錯誤", "資料不完整！")
            return

        self.start_btn.config(state="disabled")
        threading.Thread(target=self.process_thread, args=(media_dir, audio_src, out_dir, total_sec, 3, v_max), daemon=True).start()

    def process_thread(self, media_dir, audio_src, out_dir, duration, c_min, c_max):
        try:
            self.update_status("正在準備素材...", 5)
            audio_path = video_engine.download_audio(audio_src)
            
            self.update_status("正在合成影片中...", 10)
            now_str = datetime.datetime.now().strftime("%Y%m%d%H%M")
            output_name = f"FastClip_{now_str}.mp4"
            output_path = os.path.join(out_dir, output_name)
            
            def prog_cb(data):
                if isinstance(data, dict):
                    prefix = data.get('prefix', '')
                    idx = data.get('index', 0)
                    total = data.get('total', 1)
                    p = data.get('percentage', 0)
                    
                    # Focus strictly on the core rendering task
                    if prefix == "frame_index":
                        msg = f"正在合成影片 (第 {idx}/{total} 幀)..."
                        # weighted: 10% prep + 85% rendering
                        self.update_status(msg, 10 + (p * 0.85))
                    elif "audio" in prefix.lower():
                        self.update_status("正在處理音軌...", 10)
                else:
                    self.update_status("正在處理中...", 10 + (data * 0.85))

            self.update_status("正在啟動合成引擎...", 10)
            video_engine.create_video(media_dir, audio_path, duration, output_path, c_min, c_max, progress_callback=prog_cb)
            
            self.update_status("正在整理最終檔案...", 95)
            # Copy audio to output folder if it's a downloaded file
            if "temp" in audio_path and os.path.exists(audio_path):
                audio_ext = os.path.splitext(audio_path)[1]
                audio_out = os.path.join(out_dir, f"FastClip_{now_str}_背景音樂{audio_ext}")
                try:
                    shutil.copy2(audio_path, audio_out)
                except Exception:
                    pass

            # Check if output is healthy (more than 1KB)
            if os.path.exists(output_path) and os.path.getsize(output_path) < 2000:
                raise RuntimeError("產出的影片檔異常偏小（僅 1KB），可能是合成過程中斷或記憶體不足。請嘗試縮短長度或換一個背景音樂網址！")

            self.update_status("製作成功！", 100)
            messagebox.showinfo("成功", f"影片產出成功！\n存檔路徑：{output_path}")
        except Exception as e:
            self.update_status("發生錯誤", 0)
            messagebox.showerror("錯誤", str(e))
        finally:
            self.start_btn.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = FastClipApp(root)
    root.mainloop()
