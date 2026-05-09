from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


def redact_sensitive(text: str, secrets: List[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def run_and_stream(
    args: List[str],
    cwd: Optional[Path] = None,
    secrets: Optional[List[str]] = None,
) -> subprocess.CompletedProcess[str]:
    completed = run_command(args, cwd=cwd, check=False)
    secret_values = secrets or []
    if completed.stdout:
        console.print(redact_sensitive(completed.stdout.rstrip(), secret_values))
    if completed.stderr:
        console.print(redact_sensitive(completed.stderr.rstrip(), secret_values), style="yellow")
    if completed.returncode != 0:
        raise typer.Exit(completed.returncode)
    return completed


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


@profile_app.command("add")
def add_profile(name: str) -> None:
    github_token = typer.prompt("github_token", hide_input=sys.stdin.isatty())
    git_user_name = typer.prompt("git_user_name")
    git_user_email = typer.prompt("git_user_email")

    profiles = load_profiles()
    profiles[name] = {
        "github_token": github_token,
        "git_user_name": git_user_name,
        "git_user_email": git_user_email,
    }
    save_profiles(profiles)
    console.print(f"Profile {name} saved.")


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
    _, _, normalized_url = parse_repo_url(github_repo_url)
    config = load_config()
    config["default_repo"] = normalized_url
    save_config(config)
    console.print(f"Default repo set to {normalized_url}")


@app.command("use")
def use_profile(profile_name: str, repo: Optional[str] = typer.Option(None, "--repo")) -> None:
    profiles = load_profiles()
    if profile_name not in profiles:
        console.print(f"Profile {profile_name} not found.", style="red")
        raise typer.Exit(1)

    profile = profiles[profile_name]
    config = load_config()
    repo_url = repo or config.get("default_repo")
    if not repo_url:
        console.print("No repo provided. Run `devsync repo set <github_repo_url>` or pass --repo.", style="red")
        raise typer.Exit(1)

    _, _, normalized_url = parse_repo_url(repo_url)
    token_url = auth_repo_url(normalized_url, profile["github_token"])
    local_path = (Path.cwd() / repo_folder_name(normalized_url)).resolve()

    run_and_stream(["git", "config", "--global", "user.name", profile["git_user_name"]])
    run_and_stream(["git", "config", "--global", "user.email", profile["git_user_email"]])

    changed_summary = "Repository cloned."
    if local_path.exists():
        if not (local_path / ".git").exists():
            console.print(f"{local_path} exists but is not a git repository.", style="red")
            raise typer.Exit(1)

        before = git_output(["rev-parse", "HEAD"], local_path)
        run_and_stream(["git", "remote", "set-url", "origin", token_url], cwd=local_path, secrets=[profile["github_token"]])
        run_and_stream(["git", "pull"], cwd=local_path, secrets=[profile["github_token"]])
        after = git_output(["rev-parse", "HEAD"], local_path)
        changed_summary = summarize_changed_files(local_path, before, after)
    else:
        run_and_stream(["git", "clone", token_url, str(local_path)], secrets=[profile["github_token"]])

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

    console.print("\n[bold green]devsync ready[/bold green]")
    console.print(f"Profile: {profile_name}")
    console.print(f"Repo: {normalized_url}")
    console.print(f"Local path: {local_path}")
    console.print(f"{PROGRESS_FILE}: {'created' if progress_created else 'already exists'}")
    console.print("\nChanged files after pull:")
    console.print(changed_summary)


@app.command("status")
def status() -> None:
    config = load_config()
    active_profile = config.get("active_profile", "")
    profiles = load_profiles()
    profile = profiles.get(active_profile, {})
    repo_url = config.get("active_repo") or config.get("default_repo", "")

    table = Table(title="devsync status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Active profile", active_profile or "-")
    table.add_row("Git user", profile.get("git_user_name", "-"))
    table.add_row("Current repo", repo_url or "-")

    branch = "-"
    if repo_url:
        repo_path = get_active_repo_path(config)
        if repo_path.exists():
            branch = git_output(["branch", "--show-current"], repo_path) or "-"
    table.add_row("Current branch", branch)
    console.print(table)


@app.command("handoff")
def handoff() -> None:
    config = load_config()
    repo_url = config.get("active_repo") or config.get("default_repo")
    active_profile = config.get("active_profile")
    if not repo_url or not active_profile:
        console.print("No active repo/profile configured. Run `devsync use <profile>` first.", style="red")
        raise typer.Exit(1)

    repo_path = get_active_repo_path(config)
    if not repo_path.exists():
        console.print(f"Active repo path does not exist: {repo_path}", style="red")
        raise typer.Exit(1)

    commits = git_output(["log", "--oneline", "-10"], repo_path) or "(no commits found)"
    branch = git_output(["branch", "--show-current"], repo_path) or "(unknown)"
    progress_path = repo_path / PROGRESS_FILE
    progress = progress_path.read_text(encoding="utf-8") if progress_path.exists() else "(DEVIN_PROGRESS.md not found)"

    prompt = f"""---
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

    pyperclip.copy(prompt)
    console.print("Handoff prompt copied to clipboard!")


if __name__ == "__main__":
    app()
