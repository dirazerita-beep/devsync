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

## GUI mode

### One-click launchers

The repo ships with click-and-go launchers so you do not have to use a terminal
once Python is installed:

- **Windows**: double-click `run-devsync-gui.bat` in the repo folder.
- **macOS / Linux**: `chmod +x run-devsync-gui.sh` once, then double-click
  `run-devsync-gui.sh` from your file manager (or run `./run-devsync-gui.sh`).

The first run will automatically install `devsync` and its dependencies in
editable mode (`pip install -e .`). Subsequent runs skip the install step and
just launch the GUI.

> Tip (Windows): right-click `run-devsync-gui.bat` → **Send to → Desktop (create
> shortcut)** to get a real one-click icon on your desktop.

### Build a standalone .exe (for distribution)

If you want to share the app with users who do not have Python, double-click
`build-distributable.bat` (Windows) or run `./build-distributable.sh`
(macOS / Linux). It uses [PyInstaller](https://pyinstaller.org/) to bundle the
GUI into a single executable and drops the result into a folder named
`Hasil Build/`:

```
Hasil Build/
├── devsync-gui.exe        (Windows; single-file, no Python required)
└── Cara Pakai.txt         (Indonesian usage notes for end users)
```

Right-click the `Hasil Build` folder → **Send to → Compressed (zipped) folder**,
and you have a single zip you can share with anyone. The recipient just
extracts the zip and double-clicks `devsync-gui.exe` — no install, no Python.

PyInstaller can only build for the host platform, so run the builder on
Windows to produce a `.exe`, on macOS to produce a macOS binary, etc.

### Manual launch

If you prefer the terminal, the standard entry points still work:

```bash
devsync-gui
```

If Windows does not recognize `devsync-gui`, run it from the repo folder with:

```bash
python -m devsync_gui
```

On Windows, use a normal Python installer from python.org with Tcl/Tk enabled.
If your Python does not include Tkinter, the GUI will show a Tkinter support error.

The GUI uses [`ttkbootstrap`](https://ttkbootstrap.readthedocs.io/) to provide a
modern look with a header bar, card-based layout, color-coded action buttons,
status indicators with colored dots, and a one-click **Light / Dark** theme toggle.

The GUI lets you:

- Save GitHub credential profiles.
- Save a default repo URL.
- Choose the local parent folder where the repo should live.
- Clone or pull a repo with one button.
- View active profile, repo, and branch status with at-a-glance dot indicators.
- Generate, preview, and copy the Devin handoff prompt.
- Switch between a clean light theme (`cosmo`) and a dark theme (`darkly`).

Recommended GUI flow:

1. Open `devsync-gui`.
2. Go to **Profiles** and save your profile.
3. Go to **Repo Sync** and enter the GitHub repo URL.
4. Click **Save Default Repo**.
5. Click **Clone / Pull Repo**.
6. Click **Copy Handoff** when you want to continue in a new Devin session.

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
