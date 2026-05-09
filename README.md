# devsync

`devsync` is a local Python CLI for managing multiple GitHub credential profiles and keeping project context continuous when switching between Devin accounts.

## Install

```bash
git clone https://github.com/dirazerita-beep/devsync.git
cd devsync
python3 -m pip install -e .
```

Requires Python 3.8+.

## Storage

`devsync` stores local config in `~/.devsync/`:

- `profiles.json` is encrypted with Fernet.
- `key.key` stores the local Fernet key.
- `config.json` stores the default repo and active profile/repo.

## Commands

### Add a profile

```bash
devsync profile add main
```

Prompts for:

- `github_token`
- `git_user_name`
- `git_user_email`

### List profiles

```bash
devsync profile list
```

Shows saved profiles in a table and masks GitHub tokens except the last 4 characters.

### Set default repo

```bash
devsync repo set https://github.com/dirazerita-beep/devsync
```

### Use a profile

Use the saved default repo:

```bash
devsync use main
```

Or pass a repo directly:

```bash
devsync use main --repo https://github.com/dirazerita-beep/devsync
```

This command:

1. Loads the selected profile.
2. Sets global Git config:
   - `user.name`
   - `user.email`
3. Clones the repo if the local folder does not exist.
4. If the local folder exists:
   - Updates the `origin` remote to `https://<token>@github.com/owner/repo.git`
   - Runs `git pull`
   - Shows changed files after pull
5. Creates `DEVIN_PROGRESS.md` if missing.
6. Saves the active profile and repo to `~/.devsync/config.json`.

### Status

```bash
devsync status
```

Shows:

- Active profile name
- Git user
- Current repo
- Current branch

### Handoff

```bash
devsync handoff
```

Generates a handoff prompt with:

- Repo URL
- Last 10 commits
- Current branch
- `DEVIN_PROGRESS.md` content
- Continuation instructions

The prompt is copied to your clipboard automatically.

## Recommended workflow

```text
Old Devin session ends → update DEVIN_PROGRESS.md → push to GitHub
→ User runs: devsync use <new_profile>  (pulls latest automatically)
→ User runs: devsync handoff  (generates + copies prompt)
→ Paste prompt to new Devin → new Devin understands and continues work
```

At the end of every Devin session, always instruct Devin to:

```bash
git commit -am 'progress: update session notes' && git push
```

Before that command, Devin must update `DEVIN_PROGRESS.md`.

## Example full flow

```bash
devsync profile add old-devin
devsync profile add new-devin
devsync repo set https://github.com/dirazerita-beep/devsync
devsync use new-devin
devsync status
devsync handoff
```

Paste the generated handoff prompt into the new Devin session.
