import json
from typing import Optional
import requests


class AISummarizer:
    def __init__(self, provider: str, gemini_key: str = "", groq_key: str = "", groq_model: str = "llama-3.1-8b-instant"):
        self.provider = provider
        self.gemini_key = gemini_key
        self.groq_key = groq_key
        self.groq_model = groq_model

    def summarize(self, commits: list[dict], repo: str) -> list[dict]:
        if not commits:
            return []

        grouped = self._group_by_time_proximity(commits)
        summaries = []

        for group in grouped:
            if self.provider == "gemini":
                summary = self._summarize_with_gemini(group, repo)
            else:
                summary = self._summarize_with_groq(group, repo)
            summaries.append(summary)

        return summaries

    def _group_by_time_proximity(self, commits: list[dict], max_gap_minutes: int = 30) -> list[list[dict]]:
        from datetime import datetime

        sorted_commits = sorted(commits, key=lambda c: c.get("date", ""))
        groups = []
        current_group = []

        for commit in sorted_commits:
            if not commit.get("date"):
                current_group.append(commit)
                continue

            commit_time = datetime.fromisoformat(commit["date"].replace("Z", "+00:00"))

            if current_group:
                last_time = datetime.fromisoformat(current_group[-1]["date"].replace("Z", "+00:00"))
                gap = (commit_time - last_time).total_seconds() / 60

                if gap > max_gap_minutes:
                    groups.append(current_group)
                    current_group = []

            current_group.append(commit)

        if current_group:
            groups.append(current_group)

        return groups

    def _summarize_with_gemini(self, commits: list[dict], repo: str) -> dict:
        if not self.gemini_key:
            return self._fallback_summary(commits, repo)

        messages = "\n".join(
            f"- {c['message'].strip()}" for c in commits
        )

        prompt = f"""You are a developer writing daily task logs. Given these Git commits from repo '{repo}', 
write ONE concise task description that summarizes what was done. Format like a real task log entry.

Commits:
{messages}

Return ONLY valid JSON with this structure:
{{
  "task": "short task description",
  "priority": "High/Medium/Low",
  "status": "Completed/In progress",
  "productivity": 0.0-1.0
}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned)
        except Exception:
            return self._fallback_summary(commits, repo)

    def _summarize_with_groq(self, commits: list[dict], repo: str) -> dict:
        if not self.groq_key:
            return self._fallback_summary(commits, repo)

        messages = "\n".join(
            f"- {c['message'].strip()}" for c in commits
        )

        prompt = f"""You are a developer writing daily task logs. Given these Git commits from repo '{repo}', 
write ONE concise task description that summarizes what was done.

Commits:
{messages}

Return ONLY valid JSON with this structure:
{{
  "task": "short task description",
  "priority": "High/Medium/Low",
  "status": "Completed/In progress",
  "productivity": 0.0-1.0
}}"""

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned)
        except Exception:
            return self._fallback_summary(commits, repo)

    def _fallback_summary(self, commits: list[dict], repo: str) -> dict:
        messages = [c["message"].strip() for c in commits]
        task = "; ".join(messages[:3])
        if len(messages) > 3:
            task += f" (+{len(messages) - 3} more)"
        return {
            "task": task or f"Worked on {repo}",
            "priority": "Medium",
            "status": "Completed",
            "productivity": 0.8,
        }

    def get_start_time(self, commits: list[dict]) -> str:
        if not commits:
            return "9.00am"
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(commits[0]["date"].replace("Z", "+00:00"))
            hour = dt.hour
            minute = dt.minute
            period = "am" if hour < 12 else "pm"
            if hour == 0:
                hour = 12
            elif hour > 12:
                hour -= 12
            return f"{hour}.{minute:02d}{period}"
        except Exception:
            return "9.00am"

    def get_end_time(self, commits: list[dict]) -> str:
        if not commits:
            return "5.00pm"
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(commits[-1]["date"].replace("Z", "+00:00"))
            hour = dt.hour
            minute = dt.minute
            period = "am" if hour < 12 else "pm"
            if hour == 0:
                hour = 12
            elif hour > 12:
                hour -= 12
            return f"{hour}.{minute:02d}{period}"
        except Exception:
            return "5.00pm"
