from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pyperclip
import typer
from cryptography.fernet import Fernet, InvalidToken
from rich.console import Console
from rich.table import Table


APP_DIR = Path.home() / ".devsync"
KEY_FILE = APP_DIR / "key.key"
PROFILES_FILE = APP_DIR / "profiles.json"
CONFIG_FILE = APP_DIR / "config.json"
PROGRESS_FILE = "DEVIN_PROGRESS.md"

PROGRESS_TEMPLATE = """---
# Devin Progress Notes

## ✅ Completed
- 

## 🔄 In Progress
- 

## 📋 Todo
- 

## 📝 Notes & Decisions
- 

## ⚠️ Known Bugs / Blockers
- 
---
"""

console = Console()
app = typer.Typer(help="Manage GitHub credential profiles and Devin handoffs.")
profile_app = typer.Typer(help="Manage saved GitHub credential profiles.")
app.add_typer(profile_app, name="profile")


class DevsyncError(Exception):
    pass


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        APP_DIR.chmod(0o700)
    except OSError:
        pass


def get_fernet() -> Fernet:
    ensure_app_dir()
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
        try:
            KEY_FILE.chmod(0o600)
        except OSError:
            pass
    return Fernet(KEY_FILE.read_bytes())


def load_profiles() -> Dict[str, Dict[str, str]]:
    if not PROFILES_FILE.exists():
        return {}
    try:
        decrypted = get_fernet().decrypt(PROFILES_FILE.read_bytes())
        return json.loads(decrypted.decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"Unable to read encrypted profiles: {exc}") from exc


def save_profiles(profiles: Dict[str, Dict[str, str]]) -> None:
    ensure_app_dir()
    encrypted = get_fernet().encrypt(json.dumps(profiles, indent=2).encode("utf-8"))
    PROFILES_FILE.write_bytes(encrypted)
    try:
        PROFILES_FILE.chmod(0o600)
    except OSError:
        pass


def load_config() -> Dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Unable to read config: {exc}") from exc


def save_config(config: Dict[str, str]) -> None:
    ensure_app_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def run_command(args: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def run_checked(args: List[str], cwd: Optional[Path] = None, secrets: Optional[List[str]] = None) -> subprocess.CompletedProcess[str]:
    completed = run_command(args, cwd=cwd, check=False)
    if completed.returncode != 0:
        output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
        raise DevsyncError(redact_sensitive(output or "Command failed.", secrets or []))
    return completed


def redact_sensitive(text: str, secrets: List[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def parse_repo_url(repo_url: str) -> Tuple[str, str, str]:
    repo_url = repo_url.strip()

    ssh_match = re.match(r"^git@github\.com:([^/]+)/(.+?)(?:\.git)?$", repo_url)
    if ssh_match:
        owner, repo = ssh_match.groups()
        return owner, repo, f"https://github.com/{owner}/{repo}.git"

    parsed = urlparse(repo_url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise typer.BadParameter("Repo URL must be a GitHub URL.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise typer.BadParameter("Repo URL must include owner and repo.")

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo, f"https://github.com/{owner}/{repo}.git"


def auth_repo_url(repo_url: str, token: str) -> str:
    owner, repo, _ = parse_repo_url(repo_url)
    return f"https://{token}@github.com/{owner}/{repo}.git"


def repo_folder_name(repo_url: str) -> str:
    _, repo, _ = parse_repo_url(repo_url)
    return repo


def mask_token(token: str) -> str:
    if not token:
        return ""
    return f"{'*' * max(len(token) - 4, 4)}{token[-4:]}"


def get_active_repo_path(config: Dict[str, str]) -> Path:
    local_path = config.get("active_repo_path")
    if local_path:
        return Path(local_path).expanduser().resolve()

    repo_url = config.get("active_repo") or config.get("default_repo")
    if not repo_url:
        raise typer.BadParameter("No active repo configured. Run `devsync use <profile> --repo <url>` first.")
    return (Path.cwd() / repo_folder_name(repo_url)).resolve()


def git_output(args: List[str], cwd: Path) -> str:
    completed = run_command(["git", *args], cwd=cwd, check=False)
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def ensure_progress_file(repo_path: Path) -> bool:
    progress_path = repo_path / PROGRESS_FILE
    if progress_path.exists():
        return False
    progress_path.write_text(PROGRESS_TEMPLATE, encoding="utf-8")
    return True


def summarize_changed_files(repo_path: Path, before: str, after: str) -> str:
    if not before or not after or before == after:
        return "No changed files from pull."

    completed = run_command(["git", "diff", "--name-status", before, after], cwd=repo_path, check=False)
    output = completed.stdout.strip()
    return output or "No changed files from pull."


def save_profile_data(name: str, github_token: str, git_user_name: str, git_user_email: str) -> str:
    profiles = load_profiles()
    profiles[name] = {
        "github_token": github_token,
        "git_user_name": git_user_name,
        "git_user_email": git_user_email,
    }
    save_profiles(profiles)
    return f"Profile {name} saved."


def set_default_repo_data(github_repo_url: str) -> str:
    _, _, normalized_url = parse_repo_url(github_repo_url)
    config = load_config()
    config["default_repo"] = normalized_url
    save_config(config)
    return f"Default repo set to {normalized_url}"


def use_profile_data(
    profile_name: str,
    repo: Optional[str] = None,
    base_dir: Optional[Path] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    profiles = load_profiles()
    if profile_name not in profiles:
        raise DevsyncError(f"Profile {profile_name} not found.")

    profile = profiles[profile_name]
    config = load_config()
    repo_url = repo or config.get("default_repo")
    if not repo_url:
        raise DevsyncError("No repo provided. Set a default repo or pass a repo URL.")

    _, _, normalized_url = parse_repo_url(repo_url)
    token_url = auth_repo_url(normalized_url, profile["github_token"])
    parent_dir = (base_dir or Path.cwd()).expanduser().resolve()
    local_path = (parent_dir / repo_folder_name(normalized_url)).resolve()

    def emit(message: str) -> None:
        if on_output:
            on_output(message)

    run_checked(["git", "config", "--global", "user.name", profile["git_user_name"]])
    run_checked(["git", "config", "--global", "user.email", profile["git_user_email"]])

    changed_summary = "Repository cloned."
    if local_path.exists():
        if not (local_path / ".git").exists():
            raise DevsyncError(f"{local_path} exists but is not a git repository.")

        before = git_output(["rev-parse", "HEAD"], local_path)
        run_checked(["git", "remote", "set-url", "origin", token_url], cwd=local_path, secrets=[profile["github_token"]])
        pull = run_checked(["git", "pull"], cwd=local_path, secrets=[profile["github_token"]])
        if pull.stdout.strip():
            emit(redact_sensitive(pull.stdout.strip(), [profile["github_token"]]))
        if pull.stderr.strip():
            emit(redact_sensitive(pull.stderr.strip(), [profile["github_token"]]))
        after = git_output(["rev-parse", "HEAD"], local_path)
        changed_summary = summarize_changed_files(local_path, before, after)
    else:
        parent_dir.mkdir(parents=True, exist_ok=True)
        clone = run_checked(["git", "clone", token_url, str(local_path)], secrets=[profile["github_token"]])
        if clone.stdout.strip():
            emit(redact_sensitive(clone.stdout.strip(), [profile["github_token"]]))
        if clone.stderr.strip():
            emit(redact_sensitive(clone.stderr.strip(), [profile["github_token"]]))

    progress_created = ensure_progress_file(local_path)

    config.update(
        {
            "active_profile": profile_name,
            "active_repo": normalized_url,
            "active_repo_path": str(local_path),
            "default_repo": normalized_url,
        }
    )
    save_config(config)

    return {
        "profile": profile_name,
        "repo": normalized_url,
        "local_path": str(local_path),
        "progress_status": "created" if progress_created else "already exists",
        "changed_summary": changed_summary,
    }


def get_status_data() -> Dict[str, str]:
    config = load_config()
    active_profile = config.get("active_profile", "")
    profiles = load_profiles()
    profile = profiles.get(active_profile, {})
    repo_url = config.get("active_repo") or config.get("default_repo", "")
    branch = "-"

    if repo_url:
        repo_path = get_active_repo_path(config)
        if repo_path.exists():
            branch = git_output(["branch", "--show-current"], repo_path) or "-"

    return {
        "active_profile": active_profile or "-",
        "git_user": profile.get("git_user_name", "-"),
        "current_repo": repo_url or "-",
        "current_branch": branch,
    }


def build_handoff_prompt() -> str:
    config = load_config()
    repo_url = config.get("active_repo") or config.get("default_repo")
    active_profile = config.get("active_profile")
    if not repo_url or not active_profile:
        raise DevsyncError("No active repo/profile configured. Run `devsync use <profile>` first.")

    repo_path = get_active_repo_path(config)
    if not repo_path.exists():
        raise DevsyncError(f"Active repo path does not exist: {repo_path}")

    commits = git_output(["log", "--oneline", "-10"], repo_path) or "(no commits found)"
    branch = git_output(["branch", "--show-current"], repo_path) or "(unknown)"
    progress_path = repo_path / PROGRESS_FILE
    progress = progress_path.read_text(encoding="utf-8") if progress_path.exists() else "(DEVIN_PROGRESS.md not found)"

    return f"""---
===== PASTE THIS TO NEW DEVIN SESSION =====

You are continuing work on this project.
Repo: {repo_url}

RECENT COMMITS:
{commits}

CURRENT BRANCH: {branch}

PROGRESS NOTES:
{progress}

INSTRUCTIONS:
- Read the full codebase before making any changes
- Continue from where left off based on progress notes above
- Update DEVIN_PROGRESS.md before ending each session
- Commit and push with: git commit -am "progress: update session notes"
===========================================
---
"""


def copy_handoff_prompt() -> str:
    prompt = build_handoff_prompt()
    pyperclip.copy(prompt)
    return prompt


@profile_app.command("add")
def add_profile(name: str) -> None:
    github_token = typer.prompt("github_token", hide_input=sys.stdin.isatty())
    git_user_name = typer.prompt("git_user_name")
    git_user_email = typer.prompt("git_user_email")

    console.print(save_profile_data(name, github_token, git_user_name, git_user_email))


@profile_app.command("list")
def list_profiles() -> None:
    profiles = load_profiles()
    table = Table(title="devsync profiles")
    table.add_column("Name")
    table.add_column("Git User Name")
    table.add_column("Email")
    table.add_column("Token")

    for name, profile in sorted(profiles.items()):
        table.add_row(
            name,
            profile.get("git_user_name", ""),
            profile.get("git_user_email", ""),
            mask_token(profile.get("github_token", "")),
        )
    console.print(table)


repo_app = typer.Typer(help="Manage repository settings.")
app.add_typer(repo_app, name="repo")


@repo_app.command("set")
def set_repo(github_repo_url: str) -> None:
    console.print(set_default_repo_data(github_repo_url))


@app.command("use")
def use_profile(profile_name: str, repo: Optional[str] = typer.Option(None, "--repo")) -> None:
    try:
        result = use_profile_data(profile_name, repo, on_output=console.print)
    except DevsyncError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1) from exc

    console.print("\n[bold green]devsync ready[/bold green]")
    console.print(f"Profile: {result['profile']}")
    console.print(f"Repo: {result['repo']}")
    console.print(f"Local path: {result['local_path']}")
    console.print(f"{PROGRESS_FILE}: {result['progress_status']}")
    console.print("\nChanged files after pull:")
    console.print(result["changed_summary"])


@app.command("status")
def status() -> None:
    data = get_status_data()

    table = Table(title="devsync status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Active profile", data["active_profile"])
    table.add_row("Git user", data["git_user"])
    table.add_row("Current repo", data["current_repo"])
    table.add_row("Current branch", data["current_branch"])
    console.print(table)


@app.command("handoff")
def handoff() -> None:
    try:
        copy_handoff_prompt()
    except DevsyncError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1) from exc
    console.print("Handoff prompt copied to clipboard!")


if __name__ == "__main__":
    app()
