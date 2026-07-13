import json
from typing import Optional
import requests


class AISummarizer:
    def __init__(self, provider: str, gemini_key: str = "", groq_key: str = "", groq_model: str = "llama-3.1-8b-instant"):
        self.provider = provider
        self.gemini_key = gemini_key
        self.groq_key = groq_key
        self.groq_model = groq_model

    def summarize(self, commits: list[dict], repo: str, mode: str = "short") -> list[dict]:
        if not commits:
            return []

        grouped = self._group_by_time_proximity(commits)
        summaries = []

        for group in grouped:
            if mode == "full":
                summary = self._full_summary(group, repo)
            elif self.provider == "gemini":
                summary = self._summarize_with_gemini(group, repo, mode)
            else:
                summary = self._summarize_with_groq(group, repo, mode)

            summary["start_time"] = self._format_time(group[0].get("date", ""))
            summary["end_time"] = self._format_time(group[-1].get("date", ""))
            summaries.append(summary)

        return summaries

    def _format_time(self, iso_date: str) -> str:
        if not iso_date:
            return "9.00am"
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
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

    def _build_prompt(self, repo: str, messages: str, mode: str) -> str:
        prompts = {
            "short": f"Given these Git commits from repo '{repo}', write ONE very concise task description (max 15 words) summarizing what was done.\n\nCommits:\n{messages}",
            "medium": f"Given these Git commits from repo '{repo}', write a short paragraph (2-3 sentences) describing what was done.\n\nCommits:\n{messages}",
            "long": f"Given these Git commits from repo '{repo}', write a detailed description of the work done, including technical specifics.\n\nCommits:\n{messages}",
        }
        instruction = prompts.get(mode, prompts["short"])
        return f"""{instruction}

Return ONLY a single JSON object (NOT an array): {{"task": "...", "priority": "High/Medium/Low", "status": "Completed/In progress", "productivity": 0.0-1.0}}"""

    def _normalize_response(self, parsed) -> dict:
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list) and len(parsed) > 0:
            tasks = [p.get("task", "") for p in parsed if isinstance(p, dict)]
            first = parsed[0] if isinstance(parsed[0], dict) else {}
            return {
                "task": "; ".join(t for t in tasks if t),
                "priority": first.get("priority", "Medium"),
                "status": first.get("status", "Completed"),
                "productivity": first.get("productivity", 0.8),
            }
        return {"task": "", "priority": "Medium", "status": "Completed", "productivity": 0.8}

    def _full_summary(self, commits: list[dict], repo: str) -> dict:
        messages = [c["message"].strip() for c in commits]
        return {
            "task": "; ".join(messages),
            "priority": "Medium",
            "status": "Completed",
            "productivity": 0.8,
        }

    def _summarize_with_gemini(self, commits: list[dict], repo: str, mode: str) -> dict:
        if not self.gemini_key:
            return self._fallback_summary(commits, repo, mode)

        messages = "\n".join(f"- {c['message'].strip()}" for c in commits)
        prompt = self._build_prompt(repo, messages, mode)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            return self._normalize_response(json.loads(cleaned))
        except Exception:
            return self._fallback_summary(commits, repo, mode)

    def _summarize_with_groq(self, commits: list[dict], repo: str, mode: str) -> dict:
        if not self.groq_key:
            return self._fallback_summary(commits, repo, mode)

        messages = "\n".join(f"- {c['message'].strip()}" for c in commits)
        prompt = self._build_prompt(repo, messages, mode)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": "You output only valid JSON and nothing else. No explanations, no markdown."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            return self._normalize_response(json.loads(cleaned))
        except Exception:
            return self._fallback_summary(commits, repo, mode)

    def _fallback_summary(self, commits: list[dict], repo: str, mode: str = "short") -> dict:
        messages = [c["message"].strip() for c in commits]
        if mode == "full":
            task = "; ".join(messages)
        else:
            task = "; ".join(messages[:3])
            if len(messages) > 3:
                task += f" (+{len(messages) - 3} more)"
        return {
            "task": task or f"Worked on {repo}",
            "priority": "Medium",
            "status": "Completed",
            "productivity": 0.8,
        }
