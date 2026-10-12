import requests
from datetime import datetime, timezone
from typing import Optional


class GitFetcher:
    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        })

    def fetch_commits(self, repo: str, since: str, until: str) -> list[dict]:
    def fetch_branches(self, repo: str) -> list[str]:
        url = f"https://api.github.com/repos/{repo}/branches"
        params = {"per_page": 100}
        branches = []
        page = 1

        while True:
            params["page"] = page
            resp = self.session.get(url, params=params, timeout=15)

            if resp.status_code == 404:
                raise ValueError(f"Repository '{repo}' not found or no access.")
            resp.raise_for_status()

            page_data = resp.json()
            if not page_data:
                break

            branches.extend(b["name"] for b in page_data)
            page += 1

        return branches

    def fetch_commits(self, repo: str, since: str, until: str, branch: str = None) -> list[dict]:
        url = f"https://api.github.com/repos/{repo}/commits"
        params = {
            "author": self.username,
            "since": since,
            "until": until,
            "per_page": 100,
        }
        if branch:
            params["sha"] = branch

        all_commits = []
        page = 1

        while True:
            params["page"] = page
            resp = self.session.get(url, params=params)

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                raise RuntimeError("GitHub API rate limit exceeded. Wait or use a token with higher limits.")

            if resp.status_code == 404:
                raise ValueError(f"Repository '{repo}' not found or no access.")

            resp.raise_for_status()
            page_data = resp.json()

            if not page_data:
                break

            for commit_data in page_data:
                commit = commit_data["commit"]
                author_info = commit.get("author") or {}
                all_commits.append({
                    "sha": commit_data["sha"][:7],
                    "message": commit["message"],
                    "date": author_info.get("date", ""),
                    "author": commit["author"]["name"] if commit.get("author") else "unknown",
                    "url": commit_data["html_url"],
                })

            page += 1

        return sorted(all_commits, key=lambda c: c.get("date", ""))
