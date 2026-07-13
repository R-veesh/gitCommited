#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

from git_fetcher import GitFetcher
from ai_summarizer import AISummarizer
from excel_generator import ExcelGenerator


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("Error: config.json not found.")
        print("Copy config.template.json to config.json and fill in your settings.")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    github = config.get("github", {})
    if not github.get("token"):
        print("Error: GitHub token is not set in config.json")
        sys.exit(1)

    ai = config.get("ai", {})
    provider = ai.get("provider", "gemini")
    if provider == "gemini" and not ai.get("gemini_api_key"):
        print("Warning: Gemini API key not set. Will use fallback summaries.")
    elif provider == "groq" and not ai.get("groq_api_key"):
        print("Warning: Groq API key not set. Will use fallback summaries.")

    return config


def parse_date(date_str: str) -> tuple[str, str]:
    from datetime import datetime, timedelta, timezone

    if date_str.lower() == "today":
        dt = datetime.now(timezone.utc)
    elif date_str.lower() == "yesterday":
        dt = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Error: Invalid date '{date_str}'. Use YYYY-MM-DD, 'today', or 'yesterday'.")
            sys.exit(1)

    since = dt.strftime("%Y-%m-%dT00:00:00Z")
    until = dt.strftime("%Y-%m-%dT23:59:59Z")
    date_label = dt.strftime("%Y-%m-%d")
    return since, until, date_label


def main():
    parser = argparse.ArgumentParser(description="Generate daily task log from Git commits")
    parser.add_argument("--date", default="today",
                        help="Date to generate log for (YYYY-MM-DD, 'today', or 'yesterday')")
    parser.add_argument("--repo", "-r", required=True,
                        help="Repository in format 'owner/repo' (e.g., 'R-veesh/gitCommited')")
    parser.add_argument("--mode", default=None, choices=["full", "long", "medium", "short"],
                        help="Summarization mode: full (no AI), short, medium, long")
    args = parser.parse_args()

    config = load_config()
    github_cfg = config["github"]
    ai_cfg = config["ai"]
    defaults = config.get("defaults", {})

    since, until, date_label = parse_date(args.date)

    print(f"Fetching commits for {args.repo} on {date_label}...")

    fetcher = GitFetcher(token=github_cfg["token"], username=github_cfg["username"])
    try:
        commits = fetcher.fetch_commits(args.repo, since=since, until=until)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching commits: {e}")
        sys.exit(1)

    mode = args.mode or defaults.get("summarize_mode", "short")
    tz = defaults.get("timezone", "Asia/Colombo")

    summarizer = AISummarizer(
        provider=ai_cfg["provider"],
        gemini_key=ai_cfg.get("gemini_api_key", ""),
        groq_key=ai_cfg.get("groq_api_key", ""),
        groq_model=ai_cfg.get("groq_model", "llama-3.1-8b-instant"),
        timezone=tz,
    )

    if not commits:
        print(f"No commits found for {github_cfg['username']} in {args.repo} on {date_label}.")
        print("Generating Excel with no task data...")
        summaries = []
    else:
        print(f"Found {len(commits)} commits. Summarizing with {ai_cfg['provider']} (mode: {mode})...")
        summaries = summarizer.summarize(commits, args.repo, mode=mode)

    date_parts = date_label.split("-")
    output_filename = f"Task_Log_Altitude_{date_parts[2]}_{date_parts[1]}_{date_parts[0]}.xlsx"
    output_path = Path(__file__).parent / output_filename

    print(f"Generating Excel: {output_filename}...")

    break_configs = [
        ("tea_break_1", "10.30am - 11.00am", "Tea break"),
        ("lunch_break", "1.00pm - 2.00pm", "Lunch break"),
        ("tea_break_2", "4.00pm - 4.20pm", "Tea break"),
    ]
    breaks = []
    for key, default, label in break_configs:
        val = defaults.get(key, default)
        parts = val.split(" - ")
        if len(parts) == 2:
            breaks.append((parts[0].strip(), parts[1].strip(), label))

    generator = ExcelGenerator(
        assigned_by=defaults.get("assigned_by", "Altitude"),
        breaks=breaks,
    )
    merge = Path(str(output_path)).exists()
    generator.generate(
        date_str=date_label,
        task_summaries=summaries,
        repo_commits={args.repo: commits},
        output_path=str(output_path),
        merge_existing=merge,
    )

    print(f"Done! Output: {output_path}")


if __name__ == "__main__":
    main()
