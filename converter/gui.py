#!/usr/bin/env python3
"""Super Dragon's Lair - MSU Data Generator GUI.

Tkinter wrapper around tools/generate_msu_data.py that provides a visual
interface for converting Daphne laserdisc source data (.m2v/.ogg) into
MSU-1 files (.msu + .pcm + manifest.xml).
"""

import os
import re
import sys
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution — import defaults from tools/paths.py
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

try:
    from paths import (
        DAPHNE_FRAMEFILE,
        DAPHNE_CONTENT,
        FFMPEG,
        DISTRIBUTION,
        BUILD_DIR,
    )
    DEFAULT_FRAMEFILE = str(DAPHNE_FRAMEFILE)
    DEFAULT_CONTENT = str(DAPHNE_CONTENT)
    DEFAULT_FFMPEG = str(FFMPEG)
except ImportError:
    DEFAULT_FRAMEFILE = str(PROJECT_ROOT / "data" / "laserdisc" / "framefile" / "dlcdrom.TXT")
    DEFAULT_CONTENT = str(PROJECT_ROOT / "data" / "laserdisc" / "DLCDROM")
    DEFAULT_FFMPEG = "ffmpeg"
    DISTRIBUTION = PROJECT_ROOT / "distribution"
    BUILD_DIR = PROJECT_ROOT / "build"

GENERATE_SCRIPT = TOOLS_DIR / "generate_msu_data.py"
MANIFEST_SCRIPT = TOOLS_DIR / "generate_manifest.py"
CHAPTERS_DIR = PROJECT_ROOT / "data" / "chapters"

# Phase weights for overall progress (renormalized when phases skipped)
PHASE_WEIGHTS = {
    "1":  40,   # Extract video
    "1b": 10,   # Extract audio
    "1c":  2,   # Copy PCM
    "2":  40,   # Convert tiles
    "3":   8,   # Package .msu
}

# Regex patterns for parsing subprocess output
RE_PHASE = re.compile(r"^--- (Phase \S+): (.+?) ---$")
RE_PROGRESS = re.compile(r"^\[\s*(\d+)/(\d+)\]")
RE_ERROR = re.compile(r"^ERROR", re.IGNORECASE)
RE_WARN = re.compile(r"^WARN", re.IGNORECASE)


class Tooltip:
    """Simple hover tooltip for tkinter widgets."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9),
        )
        label.pack(ipadx=4, ipady=2)

    def _hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class MSUGeneratorGUI:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Super Dragon's Lair - MSU Data Generator")
        self.root.geometry("800x600")
        self.root.minsize(650, 450)

        self.process = None
        self.worker_thread = None
        self.is_running = False
        self.cancelled = False
        self.start_time = None

        # Phase tracking for overall progress
        self.current_phase_key = None
        self.phase_progress = {}  # phase_key -> (current, total)
        self.active_weights = dict(PHASE_WEIGHTS)

        self._build_ui()
        self._validate_all()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Source Data ---
        src_frame = ttk.LabelFrame(main, text="Source Data", padding=6)
        src_frame.pack(fill=tk.X, pady=(0, 4))

        self.framefile_var = tk.StringVar(value=DEFAULT_FRAMEFILE)
        self.content_var = tk.StringVar(value=DEFAULT_CONTENT)
        self.ffmpeg_var = tk.StringVar(value=DEFAULT_FFMPEG)

        self._path_row(src_frame, 0, "Framefile:", self.framefile_var,
                       self._browse_framefile, is_file=True,
                       tooltip="Daphne framefile (dlcdrom.TXT)")
        self._path_row(src_frame, 1, "Content:", self.content_var,
                       self._browse_content, is_file=False,
                       tooltip="Directory containing .m2v and .ogg segment files")
        self._path_row(src_frame, 2, "ffmpeg:", self.ffmpeg_var,
                       self._browse_ffmpeg, is_file=True,
                       tooltip="Path to ffmpeg executable (or just 'ffmpeg' if on PATH)")

        self.framefile_status = ttk.Label(src_frame, text="", width=2)
        self.framefile_status.grid(row=0, column=3, padx=(4, 0))
        self.content_status = ttk.Label(src_frame, text="", width=2)
        self.content_status.grid(row=1, column=3, padx=(4, 0))
        self.ffmpeg_status = ttk.Label(src_frame, text="", width=2)
        self.ffmpeg_status.grid(row=2, column=3, padx=(4, 0))

        for var in (self.framefile_var, self.content_var, self.ffmpeg_var):
            var.trace_add("write", lambda *_: self._validate_all())

        # --- Options ---
        opt_frame = ttk.LabelFrame(main, text="Options", padding=6)
        opt_frame.pack(fill=tk.X, pady=(0, 4))

        row0 = ttk.Frame(opt_frame)
        row0.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(row0, text="Workers:").pack(side=tk.LEFT)
        self.workers_var = tk.StringVar(value="8")
        workers_spin = ttk.Spinbox(row0, from_=1, to=32, width=4,
                                   textvariable=self.workers_var)
        workers_spin.pack(side=tk.LEFT, padx=(4, 16))
        Tooltip(workers_spin, "Number of parallel worker threads for tile conversion")

        self.clean_var = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row0, text="Clean (re-extract all)",
                                   variable=self.clean_var)
        clean_cb.pack(side=tk.LEFT)
        Tooltip(clean_cb, "Delete existing extracted frames before re-extracting from .m2v")

        row1 = ttk.Frame(opt_frame)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Phases:").pack(side=tk.LEFT)
        self.phase_extract = tk.BooleanVar(value=True)
        self.phase_audio = tk.BooleanVar(value=True)
        self.phase_convert = tk.BooleanVar(value=True)
        self.phase_package = tk.BooleanVar(value=True)

        for text, var in [("Extract", self.phase_extract),
                          ("Audio", self.phase_audio),
                          ("Convert", self.phase_convert),
                          ("Package", self.phase_package)]:
            ttk.Checkbutton(row1, text=text, variable=var).pack(side=tk.LEFT, padx=(8, 0))

        # --- Progress ---
        prog_frame = ttk.LabelFrame(main, text="Progress", padding=6)
        prog_frame.pack(fill=tk.X, pady=(0, 4))

        self.phase_label = ttk.Label(prog_frame, text="Ready")
        self.phase_label.pack(fill=tk.X)

        bar_frame = ttk.Frame(prog_frame)
        bar_frame.pack(fill=tk.X, pady=(4, 0))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(bar_frame, variable=self.progress_var,
                                            maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_pct = ttk.Label(bar_frame, text="0%", width=6, anchor=tk.E)
        self.progress_pct.pack(side=tk.LEFT, padx=(8, 0))

        self.progress_count = ttk.Label(bar_frame, text="", width=12, anchor=tk.E)
        self.progress_count.pack(side=tk.LEFT, padx=(4, 0))

        self.time_label = ttk.Label(prog_frame, text="")
        self.time_label.pack(fill=tk.X, pady=(2, 0))

        # --- Log Output ---
        log_frame = ttk.LabelFrame(main, text="Log Output", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED,
                                font=("Consolas", 9), height=10)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                  command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("error", foreground="#cc0000")
        self.log_text.tag_configure("warn", foreground="#cc8800")
        self.log_text.tag_configure("phase", foreground="#0066cc", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("success", foreground="#008800")

        # --- Bottom bar ---
        bottom = ttk.Frame(main)
        bottom.pack(fill=tk.X)

        self.generate_btn = ttk.Button(bottom, text="Generate",
                                       command=self._start_generation)
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.cancel_btn = ttk.Button(bottom, text="Cancel",
                                     command=self._cancel_generation, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT)

        self.manifest_var = tk.BooleanVar(value=True)
        manifest_cb = ttk.Checkbutton(bottom, text="Auto-manifest",
                                      variable=self.manifest_var)
        manifest_cb.pack(side=tk.RIGHT)
        Tooltip(manifest_cb, "Automatically generate manifest.xml after successful packaging")

    def _path_row(self, parent, row, label, var, browse_cmd, is_file=True, tooltip=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=(0, 4))
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=(0, 4))
        parent.columnconfigure(1, weight=1)
        btn = ttk.Button(parent, text="Browse...", command=browse_cmd, width=8)
        btn.grid(row=row, column=2)
        if tooltip:
            Tooltip(entry, tooltip)

    # ------------------------------------------------------------------
    # Browse dialogs
    # ------------------------------------------------------------------
    def _browse_framefile(self):
        path = filedialog.askopenfilename(
            title="Select Daphne framefile",
            filetypes=[("Text files", "*.TXT *.txt"), ("All files", "*.*")],
            initialdir=str(Path(self.framefile_var.get()).parent)
            if Path(self.framefile_var.get()).parent.exists() else str(PROJECT_ROOT),
        )
        if path:
            self.framefile_var.set(path)

    def _browse_content(self):
        path = filedialog.askdirectory(
            title="Select Daphne content directory",
            initialdir=self.content_var.get()
            if Path(self.content_var.get()).exists() else str(PROJECT_ROOT),
        )
        if path:
            self.content_var.set(path)

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(
            title="Select ffmpeg executable",
            filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.ffmpeg_var.set(path)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_all(self):
        ok = True

        # Framefile
        ff_path = Path(self.framefile_var.get())
        if ff_path.is_file():
            self.framefile_status.configure(text="OK", foreground="green")
        else:
            self.framefile_status.configure(text="X", foreground="red")
            ok = False

        # Content directory
        content_path = Path(self.content_var.get())
        if content_path.is_dir():
            has_m2v = any(content_path.glob("*.m2v"))
            if has_m2v:
                self.content_status.configure(text="OK", foreground="green")
            else:
                self.content_status.configure(text="?", foreground="orange")
                # Allow proceeding — .m2v files might be in subdirectories
        else:
            self.content_status.configure(text="X", foreground="red")
            ok = False

        # ffmpeg — check if it's accessible
        ffmpeg_val = self.ffmpeg_var.get().strip()
        if ffmpeg_val:
            ffmpeg_path = Path(ffmpeg_val)
            if ffmpeg_path.is_file() or ffmpeg_val == "ffmpeg":
                self.ffmpeg_status.configure(text="OK", foreground="green")
            else:
                self.ffmpeg_status.configure(text="?", foreground="orange")
        else:
            self.ffmpeg_status.configure(text="X", foreground="red")
            ok = False

        # Check other prerequisites
        if not GENERATE_SCRIPT.exists():
            ok = False
        if not CHAPTERS_DIR.exists():
            ok = False

        state = tk.NORMAL if (ok and not self.is_running) else tk.DISABLED
        self.generate_btn.configure(state=state)
        return ok

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def _build_args(self):
        """Translate GUI state into CLI arguments for generate_msu_data.py."""
        args = [sys.executable, str(GENERATE_SCRIPT)]
        args += ["--workers", self.workers_var.get()]
        args += ["--framefile", self.framefile_var.get()]
        args += ["--content-root", self.content_var.get()]

        if self.clean_var.get():
            args.append("--clean")
        if not self.phase_extract.get():
            args.append("--skip-extract")
        if not self.phase_audio.get():
            args.append("--skip-audio")
        if not self.phase_convert.get():
            args.append("--skip-convert")
        if not self.phase_package.get():
            args.append("--skip-package")

        return args

    def _build_env(self):
        """Build environment for subprocess with FFMPEG and unbuffered output."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        ffmpeg_val = self.ffmpeg_var.get().strip()
        if ffmpeg_val and ffmpeg_val != "ffmpeg":
            env["FFMPEG"] = ffmpeg_val
        return env

    def _compute_active_weights(self):
        """Compute phase weights based on which phases are enabled."""
        self.active_weights = {}
        if self.phase_extract.get():
            self.active_weights["1"] = PHASE_WEIGHTS["1"]
        if self.phase_audio.get():
            self.active_weights["1b"] = PHASE_WEIGHTS["1b"]
        # 1c (copy) always runs if audio ran
        if self.phase_audio.get():
            self.active_weights["1c"] = PHASE_WEIGHTS["1c"]
        if self.phase_convert.get():
            self.active_weights["2"] = PHASE_WEIGHTS["2"]
        if self.phase_package.get():
            self.active_weights["3"] = PHASE_WEIGHTS["3"]
        if not self.active_weights:
            self.active_weights = {"1": 1}  # fallback

    def _start_generation(self):
        if self.is_running:
            return

        # Re-validate
        if not self._validate_all():
            messagebox.showerror("Validation Failed",
                                 "Please fix the highlighted paths before generating.")
            return

        # Check chapters dir
        if not CHAPTERS_DIR.exists():
            messagebox.showerror("Missing chapters",
                                 f"data/chapters/ not found.\n\n"
                                 f"Run 'make' first to build the ROM and generate chapter data.")
            return

        self.is_running = True
        self.cancelled = False
        self.start_time = time.time()
        self.current_phase_key = None
        self.phase_progress = {}
        self._compute_active_weights()

        self.generate_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.progress_var.set(0)
        self.progress_pct.configure(text="0%")
        self.progress_count.configure(text="")
        self.phase_label.configure(text="Starting...")
        self.time_label.configure(text="")

        # Clear log
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        args = self._build_args()
        env = self._build_env()
        self._log(f"Command: {' '.join(args)}", tag="phase")

        self.worker_thread = threading.Thread(target=self._run_subprocess,
                                              args=(args, env), daemon=True)
        self.worker_thread.start()
        self._update_elapsed()

    def _run_subprocess(self, args, env):
        """Background thread: run subprocess and stream output."""
        try:
            self.process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=env, cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

            for raw_line in self.process.stdout:
                if self.cancelled:
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                self.root.after(0, self._process_line, line)

            self.process.wait()
            rc = self.process.returncode

            if self.cancelled:
                self.root.after(0, self._on_cancelled)
            elif rc == 0:
                self.root.after(0, self._on_success)
            else:
                self.root.after(0, self._on_failure, rc)

        except Exception as e:
            self.root.after(0, self._on_error, str(e))
        finally:
            self.process = None

    def _process_line(self, line):
        """Parse a line of subprocess output and update UI."""
        # Phase header
        m = RE_PHASE.match(line)
        if m:
            phase_id = m.group(1).replace("Phase ", "")
            phase_desc = m.group(2)
            self.current_phase_key = phase_id
            self.phase_label.configure(text=f"Phase {phase_id}: {phase_desc}")
            self._log(line, tag="phase")
            return

        # Progress counter
        m = RE_PROGRESS.match(line)
        if m:
            current = int(m.group(1))
            total = int(m.group(2))
            if self.current_phase_key:
                self.phase_progress[self.current_phase_key] = (current, total)
            self._update_progress(current, total)
            # Determine tag
            tag = None
            if RE_ERROR.search(line):
                tag = "error"
            elif RE_WARN.search(line):
                tag = "warn"
            self._log(line, tag=tag)
            return

        # Error/warn lines
        if RE_ERROR.match(line):
            self._log(line, tag="error")
        elif RE_WARN.match(line):
            self._log(line, tag="warn")
        elif "Success!" in line or "Done!" in line:
            self._log(line, tag="success")
        else:
            self._log(line)

    def _update_progress(self, current, total):
        """Update overall progress bar based on phase weights."""
        # Compute overall percentage
        total_weight = sum(self.active_weights.values())
        if total_weight == 0:
            return

        completed = 0.0
        for key, weight in self.active_weights.items():
            if key in self.phase_progress:
                c, t = self.phase_progress[key]
                if t > 0:
                    completed += weight * (c / t)
                if key == self.current_phase_key:
                    break  # Don't count future phases as partially done
            elif self._phase_order(key) < self._phase_order(self.current_phase_key or "1"):
                completed += weight  # Previous phases are 100%

        pct = min(100.0, (completed / total_weight) * 100)
        self.progress_var.set(pct)
        self.progress_pct.configure(text=f"{pct:.0f}%")
        self.progress_count.configure(text=f"[{current}/{total}]")

    @staticmethod
    def _phase_order(key):
        order = {"1": 0, "1b": 1, "1c": 2, "1d": 3, "1e": 4, "2": 5, "3": 6}
        return order.get(key, 99)

    def _update_elapsed(self):
        """Periodically update elapsed/ETA display."""
        if not self.is_running:
            return
        elapsed = time.time() - self.start_time
        elapsed_str = self._format_time(elapsed)

        pct = self.progress_var.get()
        if pct > 2:
            eta = elapsed * (100 - pct) / pct
            eta_str = f"~{self._format_time(eta)}"
        else:
            eta_str = "calculating..."

        self.time_label.configure(text=f"Elapsed: {elapsed_str}  |  ETA: {eta_str}")
        self.root.after(1000, self._update_elapsed)

    @staticmethod
    def _format_time(seconds):
        m, s = divmod(int(seconds), 60)
        if m >= 60:
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _log(self, message, tag=None):
        """Append a line to the log text widget."""
        self.log_text.configure(state=tk.NORMAL)
        if tag:
            self.log_text.insert(tk.END, message + "\n", tag)
        else:
            self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Completion handlers
    # ------------------------------------------------------------------
    def _on_success(self):
        self.progress_var.set(100)
        self.progress_pct.configure(text="100%")
        self.phase_label.configure(text="Complete!")
        elapsed = self._format_time(time.time() - self.start_time)
        self.time_label.configure(text=f"Elapsed: {elapsed}")
        self._log("Generation completed successfully!", tag="success")

        # Run manifest generation if enabled and package phase was active
        if self.manifest_var.get() and self.phase_package.get():
            self._run_manifest()

        self._generation_finished()

    def _on_failure(self, rc):
        self.phase_label.configure(text="Failed")
        self._log(f"Generation failed with exit code {rc}", tag="error")
        messagebox.showerror("Generation Failed",
                             f"generate_msu_data.py exited with code {rc}.\n\n"
                             f"Check the log output for details.")
        self._generation_finished()

    def _on_error(self, error_msg):
        self.phase_label.configure(text="Error")
        self._log(f"Error: {error_msg}", tag="error")
        messagebox.showerror("Error", f"An error occurred:\n\n{error_msg}")
        self._generation_finished()

    def _on_cancelled(self):
        self.phase_label.configure(text="Cancelled")
        self._log("Generation cancelled by user.", tag="warn")
        self._generation_finished()

    def _generation_finished(self):
        self.is_running = False
        self.generate_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)
        self._validate_all()

    def _run_manifest(self):
        """Run generate_manifest.py after successful generation."""
        if not MANIFEST_SCRIPT.exists():
            self._log("WARN: generate_manifest.py not found, skipping manifest generation",
                      tag="warn")
            return

        self._log("Generating manifest.xml...", tag="phase")
        try:
            result = subprocess.run(
                [sys.executable, str(MANIFEST_SCRIPT), str(DISTRIBUTION)],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            )
            for line in result.stdout.strip().splitlines():
                self._log(line, tag="success")
            if result.returncode != 0:
                for line in result.stderr.strip().splitlines():
                    self._log(line, tag="error")
        except Exception as e:
            self._log(f"Manifest generation error: {e}", tag="error")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    def _cancel_generation(self):
        if not self.is_running or self.cancelled:
            return

        self.cancelled = True
        self._log("Cancelling...", tag="warn")

        if self.process and self.process.poll() is None:
            try:
                # On Windows, kill the entire process tree (including ffmpeg children)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                )
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------
    def _on_close(self):
        if self.is_running:
            if not messagebox.askokcancel(
                "Generation in progress",
                "MSU data generation is still running.\n\n"
                "Cancel the generation and close?",
            ):
                return
            self._cancel_generation()
            # Give the subprocess a moment to die
            if self.worker_thread:
                self.worker_thread.join(timeout=3)

        self.root.destroy()


def main():
    root = tk.Tk()

    # Set window icon if available
    icon_path = PROJECT_ROOT / "converter" / "icon.ico"
    if icon_path.exists():
        root.iconbitmap(str(icon_path))

    MSUGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
