import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests

from git_fetcher import GitFetcher
from ai_summarizer import AISummarizer
from excel_generator import ExcelGenerator


class App:
    def __init__(self):
        self.config = self._load_config()
        self.root = tk.Tk()
        self.root.title("Daily Task Log Generator")
        self.root.geometry("700x520")
        self.root.resizable(False, False)

        self.repos = []
        self.output_path = None

        self._build_ui()
        self._load_repos()

    def _load_config(self):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path) as f:
            return json.load(f)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # === Repo selection ===
        ttk.Label(main, text="Repository:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))

        repo_frame = ttk.Frame(main)
        repo_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        main.columnconfigure(0, weight=1)

        self.repo_var = tk.StringVar()
        self.repo_combo = ttk.Combobox(repo_frame, textvariable=self.repo_var, width=60, state="normal")
        self.repo_combo.pack(side="left", fill="x", expand=True)

        self.refresh_btn = ttk.Button(repo_frame, text="Refresh", command=self._load_repos)
        self.refresh_btn.pack(side="right", padx=(5, 0))

        # === Date selection ===
        ttk.Label(main, text="Date:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(0, 5))

        date_frame = ttk.Frame(main)
        date_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.date_var = tk.StringVar(value="today")
        ttk.Radiobutton(date_frame, text="Today", variable=self.date_var, value="today").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(date_frame, text="Yesterday", variable=self.date_var, value="yesterday").pack(side="left", padx=(0, 10))

        ttk.Radiobutton(date_frame, text="Custom:", variable=self.date_var, value="custom").pack(side="left", padx=(0, 5))
        self.date_entry = ttk.Entry(date_frame, width=12)
        self.date_entry.pack(side="left")
        self.date_entry.insert(0, "YYYY-MM-DD")

        # === Generate button ===
        self.generate_btn = ttk.Button(main, text="Generate Task Log", command=self._generate)
        self.generate_btn.grid(row=4, column=0, sticky="w", pady=(5, 10))

        # === Status text ===
        ttk.Label(main, text="Status:", font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w")

        self.status_text = tk.Text(main, height=12, width=80, state="disabled", wrap="word", font=("Consolas", 9))
        self.status_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(3, 5))
        main.rowconfigure(6, weight=1)

        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=6, column=3, sticky="ns", pady=(3, 5))
        self.status_text.configure(yscrollcommand=scrollbar.set)

        # === Open Excel button (hidden initially) ===
        self.open_btn = ttk.Button(main, text="Open Excel File", command=self._open_excel, state="disabled")
        self.open_btn.grid(row=7, column=0, sticky="w")

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
        self._log(f"\n--- Generating task log for {repo} ({date_val}) ---")

        def run():
            try:
                self._run_pipeline(repo, date_val)
            except Exception as e:
                self.root.after(0, lambda: self._log(f"ERROR: {e}"))
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, lambda: self.generate_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _run_pipeline(self, repo: str, date_val: str):
        config = self.config
        github_cfg = config["github"]
        ai_cfg = config["ai"]
        defaults = config.get("defaults", {})

        # Parse date
        if date_val == "today":
            dt = datetime.now(timezone.utc)
        elif date_val == "yesterday":
            dt = datetime.now(timezone.utc) - timedelta(days=1)
        else:
            dt = datetime.strptime(date_val, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        since = dt.strftime("%Y-%m-%dT00:00:00Z")
        until = dt.strftime("%Y-%m-%dT23:59:59Z")
        date_label = dt.strftime("%Y-%m-%d")

        # Step 1: Fetch commits
        self.root.after(0, lambda: self._log("Fetching commits..."))
        fetcher = GitFetcher(token=github_cfg["token"], username=github_cfg["username"])
        commits = fetcher.fetch_commits(repo, since=since, until=until)
        self.root.after(0, lambda: self._log(f"Found {len(commits)} commits"))

        # Step 2: Summarize
        summarizer = AISummarizer(
            provider=ai_cfg["provider"],
            gemini_key=ai_cfg.get("gemini_api_key", ""),
            groq_key=ai_cfg.get("groq_api_key", ""),
            groq_model=ai_cfg.get("groq_model", "llama-3.1-8b-instant"),
        )

        if commits:
            self.root.after(0, lambda: self._log(f"Summarizing with {ai_cfg['provider']}..."))
            summaries = summarizer.summarize(commits, repo)
            self.root.after(0, lambda: self._log(f"Generated {len(summaries)} task summaries"))
        else:
            summaries = []
            self.root.after(0, lambda: self._log("No commits found"))

        # Step 3: Generate Excel
        date_parts = date_label.split("-")
        filename = f"Task_Log_Altitude_{date_parts[2]}_{date_parts[1]}_{date_parts[0]}.xlsx"
        output_path = str(Path(__file__).parent / filename)

        self.root.after(0, lambda: self._log(f"Generating Excel: {filename}..."))
        generator = ExcelGenerator(assigned_by=defaults.get("assigned_by", "Altitude"))
        generator.generate(
            date_str=date_label,
            task_summaries=summaries,
            repo_commits={repo: commits},
            output_path=output_path,
        )

        self.output_path = output_path
        self.root.after(0, lambda: self._log(f"DONE! Saved as: {filename}"))
        self.root.after(0, lambda: self.open_btn.configure(state="normal"))

    def _open_excel(self):
        if self.output_path and Path(self.output_path).exists():
            os.startfile(self.output_path)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
