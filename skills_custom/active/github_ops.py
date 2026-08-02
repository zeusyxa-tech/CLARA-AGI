#!/usr/bin/env python3
"""
CLARA-AGI Skill: github_ops
Full GitHub ops via gh CLI patterns: issues, PRs, repos, actions, release.
Requires gh CLI installed and authenticated.
"""
import subprocess, shlex, json


def _run(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: gh:<subcmd>|<args>\n"
                "  repo                    current repo info\n"
                "  issues                  list issues\n"
                "  prs                     list pull requests\n"
                "  issue:<n>               view issue\n"
                "  pr:<n>                  view pull request\n"
                "  search:<q>              search issues/PRs\n"
                "  status                  auth status")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub == "status":
            out, err, rc = _run(["gh", "auth", "status"])
            return out or err or "(no auth info)"
        if sub == "repo":
            out, _, _ = _run(["gh", "repo", "view", "--json", "name,owner,url,defaultBranchRef,pushedAt"])
            return out or "(no repo context)"
        if sub == "issues":
            out, _, _ = _run(["gh", "issue", "list", "--limit", "20", "--json", "number,title,state,createdAt"])
            data = json.loads(out) if out else []
            return "\n".join(f"#{i['number']} [{i['state']}] {i['title']}" for i in data[:20]) or "(no issues)"
        if sub == "prs":
            out, _, _ = _run(["gh", "pr", "list", "--limit", "20", "--json", "number,title,state,createdAt"])
            data = json.loads(out) if out else []
            return "\n".join(f"#{i['number']} [{i['state']}] {i['title']}" for i in data[:20]) or "(no PRs)"
        if sub.startswith("issue:"):
            n = sub.split(":", 1)[1].strip()
            out, _, _ = _run(["gh", "issue", "view", n, "--json", "title,body,state,url"])
            return out or f"(issue {n} not found)"
        if sub.startswith("pr:"):
            n = sub.split(":", 1)[1].strip()
            out, _, _ = _run(["gh", "pr", "view", n, "--json", "title,body,state,url,mergeable"])
            return out or f"(pr {n} not found)"
        if sub.startswith("search:"):
            q = arg.strip() or sub.split(":", 1)[1].strip()
            out, _, _ = _run(["gh", "search", "issues", q, "--limit", "10", "--json", "number,title,url"])
            data = json.loads(out) if out else []
            return "\n".join(f"#{i['number']} {i['title']}\n  {i['url']}" for i in data[:10]) or "(no results)"
        return f"❌ Unknown github subcmd: {sub}"
    except Exception as e:
        return f"❌ {e}"
