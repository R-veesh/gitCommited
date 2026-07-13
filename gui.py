import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests

from git_fetcher import GitFetcher
from ai_summarizer import AISummarizer
from excel_generator import ExcelGenerator


CONFIG_PATH = Path(__file__).parent / "config.json"


class App:
    def __init__(self):
        self.config = self._load_config()
        self.root = tk.Tk()
        self.root.title("Daily Task Log Generator")
        self.root.geometry("720x560")
        self.root.resizable(False, False)

        self.repos = []
        self.output_path = None

        self._build_ui()
        self._load_repos()

    def _load_config(self):
        with open(CONFIG_PATH) as f:
            return json.load(f)

    def _save_config(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=4)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # === Settings button (top right) ===
        top_frame = ttk.Frame(main)
        top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        main.columnconfigure(0, weight=1)
        ttk.Button(top_frame, text="Settings", command=self._open_settings).pack(side="right")

        # === Repo selection ===
        ttk.Label(main, text="Repository:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 5))

        repo_frame = ttk.Frame(main)
        repo_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        self.repo_var = tk.StringVar()
        self.repo_combo = ttk.Combobox(repo_frame, textvariable=self.repo_var, width=60, state="normal")
        self.repo_combo.pack(side="left", fill="x", expand=True)

        self.refresh_btn = ttk.Button(repo_frame, text="Refresh", command=self._load_repos)
        self.refresh_btn.pack(side="right", padx=(5, 0))

        # === Summarize mode ===
        ttk.Label(main, text="Summarize Mode:", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 5))

        mode_frame = ttk.Frame(main)
        mode_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.mode_var = tk.StringVar(value=self.config.get("defaults", {}).get("summarize_mode", "short"))
        modes = [
            ("Short", "short", "Concise one-line summary"),
            ("Medium", "medium", "Short paragraph (2-3 sentences)"),
            ("Long", "long", "Detailed description"),
            ("Full (no AI)", "full", "Raw commit messages, no summarization"),
        ]
        for i, (label, val, tooltip) in enumerate(modes):
            rb = ttk.Radiobutton(mode_frame, text=label, variable=self.mode_var, value=val)
            rb.pack(side="left", padx=(0, 15))
            rb.bind("<Enter>", lambda e, t=tooltip: self._show_tooltip(e, t))
            rb.bind("<Leave>", self._hide_tooltip)

        self.tooltip_label = ttk.Label(main, text="", foreground="gray")
        self.tooltip_label.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 3))

        # === Date selection ===
        ttk.Label(main, text="Date:", font=("Segoe UI", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 5))

        date_frame = ttk.Frame(main)
        date_frame.grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.date_var = tk.StringVar(value="today")
        ttk.Radiobutton(date_frame, text="Today", variable=self.date_var, value="today").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(date_frame, text="Yesterday", variable=self.date_var, value="yesterday").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(date_frame, text="Custom:", variable=self.date_var, value="custom").pack(side="left", padx=(0, 5))
        self.date_entry = ttk.Entry(date_frame, width=12)
        self.date_entry.pack(side="left")
        self.date_entry.insert(0, "YYYY-MM-DD")

        # === Generate button ===
        self.generate_btn = ttk.Button(main, text="Generate Task Log", command=self._generate)
        self.generate_btn.grid(row=8, column=0, sticky="w", pady=(5, 10))

        # === Status text ===
        ttk.Label(main, text="Status:", font=("Segoe UI", 10, "bold")).grid(row=9, column=0, sticky="w")

        self.status_text = tk.Text(main, height=10, width=80, state="disabled", wrap="word", font=("Consolas", 9))
        self.status_text.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=(3, 5))
        main.rowconfigure(10, weight=1)

        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=10, column=3, sticky="ns", pady=(3, 5))
        self.status_text.configure(yscrollcommand=scrollbar.set)

        # === Open Excel button ===
        self.open_btn = ttk.Button(main, text="Open Excel File", command=self._open_excel, state="disabled")
        self.open_btn.grid(row=11, column=0, sticky="w")

    def _show_tooltip(self, event, text):
        self.tooltip_label.configure(text=text)

    def _hide_tooltip(self, event):
        self.tooltip_label.configure(text="")

    def _log(self, message: str):
        self.status_text.configure(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")
        self.root.update_idletasks()

    def _load_repos(self):
        self.refresh_btn.configure(state="disabled")
        self._log("Loading repositories...")

        def fetch():
            try:
                token = self.config["github"]["token"]
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
                resp = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=headers, timeout=15)
                resp.raise_for_status()
                self.repos = [r["full_name"] for r in resp.json()]
                self.root.after(0, self._update_repo_list)
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Failed to load repos: {e}"))

        threading.Thread(target=fetch, daemon=True).start()

    def _update_repo_list(self):
        self.repo_combo["values"] = self.repos
        if self.repos:
            self.repo_combo.set(self.repos[0])
        self.refresh_btn.configure(state="normal")
        self._log(f"Loaded {len(self.repos)} repositories")

    def _get_date(self) -> str:
        val = self.date_var.get()
        if val == "today":
            return "today"
        elif val == "yesterday":
            return "yesterday"
        else:
            return self.date_entry.get().strip()

    def _generate(self):
        repo = self.repo_var.get().strip()
        if not repo:
            messagebox.showerror("Error", "Please select a repository")
            return

        date_val = self._get_date()
        if date_val not in ("today", "yesterday") and not date_val:
            messagebox.showerror("Error", "Please enter a valid date")
            return

        self.generate_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        mode = self.mode_var.get()
        self._log(f"\n--- Generating task log for {repo} ({date_val}) [mode: {mode}] ---")

        def run():
            try:
                self._run_pipeline(repo, date_val, mode)
            except Exception as e:
                self.root.after(0, lambda: self._log(f"ERROR: {e}"))
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, lambda: self.generate_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _run_pipeline(self, repo: str, date_val: str, mode: str):
        config = self.config
        github_cfg = config["github"]
        ai_cfg = config["ai"]
        defaults = config.get("defaults", {})

        if date_val == "today":
            dt = datetime.now(timezone.utc)
        elif date_val == "yesterday":
            dt = datetime.now(timezone.utc) - timedelta(days=1)
        else:
            dt = datetime.strptime(date_val, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        since = dt.strftime("%Y-%m-%dT00:00:00Z")
        until = dt.strftime("%Y-%m-%dT23:59:59Z")
        date_label = dt.strftime("%Y-%m-%d")

        self.root.after(0, lambda: self._log("Fetching commits..."))
        fetcher = GitFetcher(token=github_cfg["token"], username=github_cfg["username"])
        commits = fetcher.fetch_commits(repo, since=since, until=until)
        self.root.after(0, lambda: self._log(f"Found {len(commits)} commits"))

        tz = defaults.get("timezone", "Asia/Colombo")
        summarizer = AISummarizer(
            provider=ai_cfg["provider"],
            gemini_key=ai_cfg.get("gemini_api_key", ""),
            groq_key=ai_cfg.get("groq_api_key", ""),
            groq_model=ai_cfg.get("groq_model", "llama-3.1-8b-instant"),
            timezone=tz,
        )

        if commits:
            provider_name = "raw" if mode == "full" else ai_cfg["provider"]
            self.root.after(0, lambda p=provider_name, m=mode: self._log(f"Summarizing ({p}, mode: {m})..."))
            summaries = summarizer.summarize(commits, repo, mode=mode)
            self.root.after(0, lambda: self._log(f"Generated {len(summaries)} task summaries"))
        else:
            summaries = []
            self.root.after(0, lambda: self._log("No commits found"))

        date_parts = date_label.split("-")
        filename = f"Task_Log_Altitude_{date_parts[2]}_{date_parts[1]}_{date_parts[0]}.xlsx"
        output_path = str(Path(__file__).parent / filename)

        breaks = [
            (defaults.get("tea_break_1", "10.30am - 11.00am").split(" - ")[0].strip(),
             defaults.get("tea_break_1", "10.30am - 11.00am").split(" - ")[1].strip(),
             "Tea break"),
            (defaults.get("lunch_break", "1.00pm - 2.00pm").split(" - ")[0].strip(),
             defaults.get("lunch_break", "1.00pm - 2.00pm").split(" - ")[1].strip(),
             "Lunch break"),
            (defaults.get("tea_break_2", "4.00pm - 4.20pm").split(" - ")[0].strip(),
             defaults.get("tea_break_2", "4.00pm - 4.20pm").split(" - ")[1].strip(),
             "Tea break"),
        ]

        merge = Path(output_path).exists()
        if merge:
            self.root.after(0, lambda: self._log("Existing file found — merging tasks..."))

        self.root.after(0, lambda: self._log(f"Generating Excel: {filename}..."))
        generator = ExcelGenerator(
            assigned_by=defaults.get("assigned_by", "Altitude"),
            breaks=breaks,
        )
        generator.generate(
            date_str=date_label,
            task_summaries=summaries,
            repo_commits={repo: commits},
            output_path=output_path,
            merge_existing=merge,
        )

        self.output_path = output_path
        self.root.after(0, lambda: self._log(f"DONE! Saved as: {filename}"))
        self.root.after(0, lambda: self.open_btn.configure(state="normal"))

    def _open_excel(self):
        if self.output_path and Path(self.output_path).exists():
            os.startfile(self.output_path)

    def _open_settings(self):
        SettingsWindow(self.root, self.config, self._on_settings_saved)

    def _on_settings_saved(self, new_config):
        self.config = new_config
        self._save_config()
        self.mode_var.set(self.config.get("defaults", {}).get("summarize_mode", "short"))
        self._log("Settings saved")

    def run(self):
        self.root.mainloop()


class SettingsWindow:
    def __init__(self, parent, config, on_save_callback):
        self.config = {k: v.copy() if isinstance(v, dict) else v for k, v in config.items()}
        self.on_save = on_save_callback

        self.win = tk.Toplevel(parent)
        self.win.title("Settings")
        self.win.geometry("520x480")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.win, padding=15)
        main.pack(fill="both", expand=True)

        row = 0

        # === GitHub Settings ===
        ttk.Label(main, text="GitHub", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
        row += 1

        ttk.Label(main, text="Username:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.github_user = ttk.Entry(main, width=40)
        self.github_user.grid(row=row, column=1, sticky="ew", pady=2)
        self.github_user.insert(0, self.config["github"]["username"])
        row += 1

        ttk.Label(main, text="Token:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.github_token = ttk.Entry(main, width=40, show="*")
        self.github_token.grid(row=row, column=1, sticky="ew", pady=2)
        self.github_token.insert(0, self.config["github"]["token"])

        show_btn = ttk.Button(main, text="Show", command=lambda: self._toggle_show(self.github_token))
        show_btn.grid(row=row, column=2, padx=(5, 0))
        row += 1

        # === Separator ===
        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        # === AI Settings ===
        ttk.Label(main, text="AI Provider", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
        row += 1

        self.ai_provider = tk.StringVar(value=self.config["ai"]["provider"])
        ttk.Radiobutton(main, text="Groq", variable=self.ai_provider, value="groq").grid(row=row, column=0, sticky="w")
        ttk.Radiobutton(main, text="Gemini", variable=self.ai_provider, value="gemini").grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(main, text="Groq API Key:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.groq_key = ttk.Entry(main, width=40, show="*")
        self.groq_key.grid(row=row, column=1, sticky="ew", pady=2)
        self.groq_key.insert(0, self.config["ai"].get("groq_api_key", ""))
        row += 1

        ttk.Label(main, text="Gemini API Key:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.gemini_key = ttk.Entry(main, width=40, show="*")
        self.gemini_key.grid(row=row, column=1, sticky="ew", pady=2)
        self.gemini_key.insert(0, self.config["ai"].get("gemini_api_key", ""))
        row += 1

        # === Separator ===
        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        # === Defaults ===
        ttk.Label(main, text="Defaults", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
        row += 1

        ttk.Label(main, text="Assigned By:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.assigned_by = ttk.Entry(main, width=30)
        self.assigned_by.grid(row=row, column=1, sticky="w", pady=2)
        self.assigned_by.insert(0, self.config["defaults"].get("assigned_by", "Altitude"))
        row += 1

        ttk.Label(main, text="Summarize Mode:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.mode_combo = ttk.Combobox(main, values=["short", "medium", "long", "full"], width=10, state="readonly")
        self.mode_combo.grid(row=row, column=1, sticky="w", pady=2)
        self.mode_combo.set(self.config["defaults"].get("summarize_mode", "short"))
        row += 1

        ttk.Label(main, text="Timezone:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.tz_combo = ttk.Combobox(main, values=[
            "Asia/Colombo", "Asia/Kolkata", "Asia/Dubai",
            "Asia/Singapore", "Asia/Shanghai", "UTC",
            "America/New_York", "Europe/London",
        ], width=15, state="normal")
        self.tz_combo.grid(row=row, column=1, sticky="w", pady=2)
        self.tz_combo.set(self.config["defaults"].get("timezone", "Asia/Colombo"))
        row += 1

        # === Breaks ===
        ttk.Label(main, text="Breaks", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 5))
        row += 1

        ttk.Label(main, text="Morning Tea:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.tea1_entry = ttk.Entry(main, width=20)
        self.tea1_entry.grid(row=row, column=1, sticky="w", pady=2)
        self.tea1_entry.insert(0, self.config["defaults"].get("tea_break_1", "10.30am - 11.00am"))
        row += 1

        ttk.Label(main, text="Lunch:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.lunch_entry = ttk.Entry(main, width=20)
        self.lunch_entry.grid(row=row, column=1, sticky="w", pady=2)
        self.lunch_entry.insert(0, self.config["defaults"].get("lunch_break", "1.00pm - 2.00pm"))
        row += 1

        ttk.Label(main, text="Evening Tea:").grid(row=row, column=0, sticky="w", padx=(0, 10))
        self.tea2_entry = ttk.Entry(main, width=20)
        self.tea2_entry.grid(row=row, column=1, sticky="w", pady=2)
        self.tea2_entry.insert(0, self.config["defaults"].get("tea_break_2", "4.00pm - 4.20pm"))
        row += 1

        # === Save / Cancel ===
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=self.win.destroy).pack(side="left")

        main.columnconfigure(1, weight=1)

    def _toggle_show(self, entry):
        if entry.cget("show") == "*":
            entry.configure(show="")
        else:
            entry.configure(show="*")

    def _save(self):
        self.config["github"]["username"] = self.github_user.get().strip()
        self.config["github"]["token"] = self.github_token.get().strip()
        self.config["ai"]["provider"] = self.ai_provider.get()
        self.config["ai"]["groq_api_key"] = self.groq_key.get().strip()
        self.config["ai"]["gemini_api_key"] = self.gemini_key.get().strip()
        self.config["defaults"]["assigned_by"] = self.assigned_by.get().strip()
        self.config["defaults"]["summarize_mode"] = self.mode_combo.get()
        self.config["defaults"]["timezone"] = self.tz_combo.get().strip()
        self.config["defaults"]["tea_break_1"] = self.tea1_entry.get().strip()
        self.config["defaults"]["lunch_break"] = self.lunch_entry.get().strip()
        self.config["defaults"]["tea_break_2"] = self.tea2_entry.get().strip()

        if not self.config["github"]["token"]:
            messagebox.showerror("Error", "GitHub token is required", parent=self.win)
            return

        self.on_save(self.config)
        self.win.destroy()


if __name__ == "__main__":
    App().run()
