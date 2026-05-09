from __future__ import annotations

import os
import platform
import queue
import threading
from pathlib import Path
from typing import Callable, List, Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    import ttkbootstrap as tb
    from ttkbootstrap.constants import (
        BOTH,
        DANGER,
        END,
        INFO,
        LEFT,
        OUTLINE,
        PRIMARY,
        RIGHT,
        SECONDARY,
        SUCCESS,
        WARNING,
        WORD,
        X,
        Y,
    )
except ModuleNotFoundError as exc:
    tk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    scrolledtext = None  # type: ignore[assignment]
    tb = None  # type: ignore[assignment]
    GUI_IMPORT_ERROR: Optional[ModuleNotFoundError] = exc
else:
    GUI_IMPORT_ERROR = None

from devsync import (
    DevsyncError,
    PROGRESS_FILE,
    build_handoff_prompt,
    copy_handoff_prompt,
    get_status_data,
    load_config,
    load_profiles,
    mask_token,
    save_profile_data,
    set_default_repo_data,
    use_profile_data,
)


LIGHT_THEME = "cosmo"
DARK_THEME = "darkly"

if platform.system() == "Windows":
    UI_FONT_FAMILY = "Segoe UI"
    MONO_FONT_FAMILY = "Consolas"
elif platform.system() == "Darwin":
    UI_FONT_FAMILY = "SF Pro Text"
    MONO_FONT_FAMILY = "Menlo"
else:
    UI_FONT_FAMILY = "DejaVu Sans"
    MONO_FONT_FAMILY = "DejaVu Sans Mono"

FONT_TITLE = (UI_FONT_FAMILY, 17, "bold")
FONT_SUBTITLE = (UI_FONT_FAMILY, 9)
FONT_SECTION = (UI_FONT_FAMILY, 10, "bold")
FONT_LABEL = (UI_FONT_FAMILY, 9)
FONT_VALUE = (UI_FONT_FAMILY, 10)
FONT_VALUE_BOLD = (UI_FONT_FAMILY, 10, "bold")
FONT_CHIP = (UI_FONT_FAMILY, 9, "bold")
FONT_BUTTON = (UI_FONT_FAMILY, 9, "bold")
FONT_MONO = (MONO_FONT_FAMILY, 9)


class DevsyncGui:
    def __init__(self, root: "tb.Window") -> None:
        self.root = root
        self.root.title("devsync")
        self.root.geometry("1100x820")
        self.root.minsize(900, 700)
        self.output_queue: "queue.Queue[str]" = queue.Queue()

        self.profile_var = tk.StringVar()
        self.repo_var = tk.StringVar()
        self.base_dir_var = tk.StringVar(value=str(Path.cwd()))

        self.status_profile_var = tk.StringVar(value="-")
        self.status_user_var = tk.StringVar(value="-")
        self.status_repo_var = tk.StringVar(value="-")
        self.status_branch_var = tk.StringVar(value="-")
        self.header_chip_var = tk.StringVar(value="No active profile")

        self.is_dark = False
        self._status_dots: List[tuple["tb.Label", Callable[[], str]]] = []

        self._configure_styles()
        self._build()
        self.refresh_all()
        self._poll_output()

    def _configure_styles(self) -> None:
        style = self.root.style
        style.configure("TButton", font=FONT_BUTTON)
        style.configure("TLabel", font=FONT_LABEL)
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=4)
        style.configure(
            "Card.TLabelframe",
            borderwidth=1,
            relief="solid",
            padding=14,
        )
        style.configure(
            "Card.TLabelframe.Label",
            font=FONT_SECTION,
        )
        style.configure(
            "Section.TLabel",
            font=FONT_SECTION,
        )
        style.configure(
            "Muted.TLabel",
            font=FONT_LABEL,
            foreground="#6b7280",
        )
        style.configure(
            "Value.TLabel",
            font=FONT_VALUE_BOLD,
        )
        style.configure(
            "Header.TFrame",
            background=style.colors.primary,
        )
        style.configure(
            "HeaderTitle.TLabel",
            font=FONT_TITLE,
            background=style.colors.primary,
            foreground="#ffffff",
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            font=FONT_SUBTITLE,
            background=style.colors.primary,
            foreground="#e5e7eb",
        )
        style.configure(
            "HeaderChip.TLabel",
            font=FONT_CHIP,
            background="#ffffff",
            foreground=style.colors.primary,
            padding=(12, 4),
        )
        style.configure(
            "TNotebook.Tab",
            padding=(18, 9),
            font=FONT_BUTTON,
        )
        style.configure(
            "Treeview",
            rowheight=26,
            font=FONT_VALUE,
        )
        style.configure(
            "Treeview.Heading",
            font=FONT_BUTTON,
            padding=(8, 6),
        )

    def _build(self) -> None:
        outer = tb.Frame(self.root)
        outer.pack(fill=BOTH, expand=True)

        self._build_header(outer)
        self._build_body(outer)

    def _build_header(self, parent: "tb.Frame") -> None:
        header = tk.Frame(parent, bg=self.root.style.colors.primary)
        header.pack(fill=X, side=tk.TOP)

        inner = tk.Frame(header, bg=self.root.style.colors.primary)
        inner.pack(fill=X, padx=20, pady=14)

        left = tk.Frame(inner, bg=self.root.style.colors.primary)
        left.pack(side=LEFT, fill=Y)

        title = tk.Label(
            left,
            text="\u26a1  devsync",
            font=FONT_TITLE,
            bg=self.root.style.colors.primary,
            fg="#ffffff",
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            left,
            text="Multi-account GitHub credentials & Devin handoff manager",
            font=FONT_SUBTITLE,
            bg=self.root.style.colors.primary,
            fg="#e5e7eb",
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        right = tk.Frame(inner, bg=self.root.style.colors.primary)
        right.pack(side=RIGHT, fill=Y)

        self.header_chip = tk.Label(
            right,
            textvariable=self.header_chip_var,
            font=FONT_CHIP,
            bg="#ffffff",
            fg=self.root.style.colors.primary,
            padx=12,
            pady=4,
        )
        self.header_chip.pack(side=LEFT, padx=(0, 12))

        self.theme_btn = tb.Button(
            right,
            text="\u263d  Dark",
            bootstyle=(OUTLINE, "light"),
            command=self.toggle_theme,
            width=10,
        )
        self.theme_btn.pack(side=LEFT)

        self._header_widgets = [header, inner, left, right, title, subtitle]

    def _build_body(self, parent: "tb.Frame") -> None:
        body = tb.Frame(parent, padding=(16, 14, 16, 14))
        body.pack(fill=BOTH, expand=True)

        # Pack the log first so it claims its preferred height before the
        # notebook expands to fill the rest.
        self._build_log(body)

        self.notebook = tb.Notebook(body, bootstyle=PRIMARY)
        self.notebook.pack(fill=BOTH, expand=True, side=tk.TOP)

        repo_tab = tb.Frame(self.notebook, padding=(2, 14, 2, 2))
        profiles_tab = tb.Frame(self.notebook, padding=(2, 14, 2, 2))
        handoff_tab = tb.Frame(self.notebook, padding=(2, 14, 2, 2))

        self.notebook.add(repo_tab, text="  Repo Sync  ")
        self.notebook.add(profiles_tab, text="  Profiles  ")
        self.notebook.add(handoff_tab, text="  Handoff  ")

        self._build_repo_tab(repo_tab)
        self._build_profiles_tab(profiles_tab)
        self._build_handoff_tab(handoff_tab)

    # ------------------------------------------------------------------ tabs
    def _build_repo_tab(self, parent: "tb.Frame") -> None:
        parent.columnconfigure(0, weight=1)

        config_card = tb.Labelframe(parent, text="  Configuration  ", style="Card.TLabelframe")
        config_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        config_card.columnconfigure(1, weight=1)

        self._row_label(config_card, "Profile", 0)
        self.profile_combo = tb.Combobox(
            config_card,
            textvariable=self.profile_var,
            state="readonly",
        )
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        tb.Button(
            config_card,
            text="\u21bb  Refresh",
            bootstyle=(OUTLINE, PRIMARY),
            command=self.refresh_all,
            width=12,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=6)

        self._row_label(config_card, "GitHub repo URL", 1)
        tb.Entry(config_card, textvariable=self.repo_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )
        tb.Button(
            config_card,
            text="Save Default Repo",
            bootstyle=(OUTLINE, PRIMARY),
            command=self.save_default_repo,
            width=18,
        ).grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=6)

        self._row_label(config_card, "Local parent folder", 2)
        tb.Entry(config_card, textvariable=self.base_dir_var).grid(
            row=2, column=1, sticky="ew", padx=8, pady=6
        )
        tb.Button(
            config_card,
            text="Browse\u2026",
            bootstyle=(OUTLINE, PRIMARY),
            command=self.choose_base_dir,
            width=12,
        ).grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=6)

        actions_card = tb.Labelframe(parent, text="  Actions  ", style="Card.TLabelframe")
        actions_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for col in range(4):
            actions_card.columnconfigure(col, weight=1)

        tb.Button(
            actions_card,
            text="\u21ca  Clone / Pull Repo",
            bootstyle=PRIMARY,
            command=self.use_selected_profile,
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=2)
        tb.Button(
            actions_card,
            text="\u24d8  Show Status",
            bootstyle=INFO,
            command=self.show_status,
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        tb.Button(
            actions_card,
            text="\U0001f4c1  Open Repo Folder",
            bootstyle=SECONDARY,
            command=self.open_repo_folder,
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=2)
        tb.Button(
            actions_card,
            text="\u2398  Copy Handoff",
            bootstyle=SUCCESS,
            command=self.copy_handoff,
        ).grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        status_card = tb.Labelframe(parent, text="  Current Status  ", style="Card.TLabelframe")
        status_card.grid(row=2, column=0, sticky="nsew")
        parent.rowconfigure(2, weight=1)
        status_card.columnconfigure(2, weight=1)

        self._status_dots = []
        self._status_row(status_card, 0, "Active profile", self.status_profile_var,
                         lambda: self.status_profile_var.get())
        self._status_row(status_card, 1, "Git user", self.status_user_var,
                         lambda: self.status_user_var.get())
        self._status_row(status_card, 2, "Current repo", self.status_repo_var,
                         lambda: self.status_repo_var.get())
        self._status_row(status_card, 3, "Current branch", self.status_branch_var,
                         lambda: self.status_branch_var.get())

    def _build_profiles_tab(self, parent: "tb.Frame") -> None:
        parent.columnconfigure(0, weight=1)

        form_card = tb.Labelframe(parent, text="  Add or Update Profile  ", style="Card.TLabelframe")
        form_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        form_card.columnconfigure(1, weight=1)

        self.new_profile_name = tk.StringVar()
        self.new_token = tk.StringVar()
        self.new_git_name = tk.StringVar()
        self.new_git_email = tk.StringVar()

        self._row_label(form_card, "Profile name", 0)
        tb.Entry(form_card, textvariable=self.new_profile_name).grid(
            row=0, column=1, sticky="ew", padx=8, pady=6
        )

        self._row_label(form_card, "GitHub token", 1)
        tb.Entry(form_card, textvariable=self.new_token, show="\u2022").grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )

        self._row_label(form_card, "Git user.name", 2)
        tb.Entry(form_card, textvariable=self.new_git_name).grid(
            row=2, column=1, sticky="ew", padx=8, pady=6
        )

        self._row_label(form_card, "Git user.email", 3)
        tb.Entry(form_card, textvariable=self.new_git_email).grid(
            row=3, column=1, sticky="ew", padx=8, pady=6
        )

        tb.Button(
            form_card,
            text="\u2714  Save Profile",
            bootstyle=PRIMARY,
            command=self.save_profile,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 4))

        list_card = tb.Labelframe(parent, text="  Saved Profiles  ", style="Card.TLabelframe")
        list_card.grid(row=1, column=0, sticky="nsew")
        parent.rowconfigure(1, weight=1)
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(0, weight=1)

        self.profiles_tree = tb.Treeview(
            list_card,
            columns=("name", "git_name", "email", "token"),
            show="headings",
            bootstyle=PRIMARY,
        )
        self.profiles_tree.heading("name", text="Name")
        self.profiles_tree.heading("git_name", text="Git User Name")
        self.profiles_tree.heading("email", text="Email")
        self.profiles_tree.heading("token", text="Token")
        self.profiles_tree.column("name", width=160, anchor="w")
        self.profiles_tree.column("git_name", width=180, anchor="w")
        self.profiles_tree.column("email", width=240, anchor="w")
        self.profiles_tree.column("token", width=160, anchor="w")
        self.profiles_tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_handoff_tab(self, parent: "tb.Frame") -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        action_card = tb.Frame(parent)
        action_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        tb.Label(
            action_card,
            text="Generate a handoff prompt with recent commits, branch, and progress notes.",
            style="Muted.TLabel",
        ).pack(side=LEFT, padx=(2, 0))

        tb.Button(
            action_card,
            text="\U0001f441  Preview",
            bootstyle=(OUTLINE, INFO),
            command=self.preview_handoff,
            width=14,
        ).pack(side=RIGHT, padx=(8, 0))
        tb.Button(
            action_card,
            text="\u2398  Copy to Clipboard",
            bootstyle=SUCCESS,
            command=self.copy_handoff,
            width=20,
        ).pack(side=RIGHT)

        text_card = tb.Labelframe(parent, text="  Handoff Preview  ", style="Card.TLabelframe")
        text_card.grid(row=1, column=0, sticky="nsew")
        text_card.columnconfigure(0, weight=1)
        text_card.rowconfigure(0, weight=1)

        self.handoff_text = scrolledtext.ScrolledText(
            text_card,
            wrap=WORD,
            font=FONT_MONO,
            relief="flat",
            borderwidth=0,
        )
        self.handoff_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_log(self, parent: "tb.Frame") -> None:
        log_card = tb.Labelframe(parent, text="  Activity Log  ", style="Card.TLabelframe")
        log_card.pack(fill=X, side=tk.BOTTOM, pady=(12, 0))

        self.output = scrolledtext.ScrolledText(
            log_card,
            height=5,
            wrap=WORD,
            font=FONT_MONO,
            relief="flat",
            borderwidth=0,
        )
        self.output.pack(fill=X, expand=False, padx=4, pady=4)

    # --------------------------------------------------------------- helpers
    def _row_label(self, parent: "tb.Frame", text: str, row: int) -> None:
        tb.Label(parent, text=text, style="Muted.TLabel").grid(
            row=row, column=0, sticky="w", padx=(4, 8), pady=6
        )

    def _status_row(
        self,
        parent: "tb.Frame",
        row: int,
        label: str,
        value_var: tk.StringVar,
        getter: Callable[[], str],
    ) -> None:
        dot = tb.Label(parent, text="\u25cf", font=(UI_FONT_FAMILY, 14), bootstyle=SECONDARY)
        dot.grid(row=row, column=0, sticky="w", padx=(8, 10), pady=6)
        tb.Label(parent, text=label, style="Muted.TLabel").grid(
            row=row, column=1, sticky="w", padx=(0, 16), pady=6
        )
        tb.Label(parent, textvariable=value_var, style="Value.TLabel").grid(
            row=row, column=2, sticky="w", pady=6
        )
        self._status_dots.append((dot, getter))

    def _refresh_status_dots(self) -> None:
        for dot, getter in self._status_dots:
            value = (getter() or "").strip()
            if value and value != "-":
                dot.configure(bootstyle=SUCCESS)
            else:
                dot.configure(bootstyle=SECONDARY)

    def _refresh_header_chip(self) -> None:
        active = (self.status_profile_var.get() or "").strip()
        if active and active != "-":
            self.header_chip_var.set(f"\u25cf  {active}")
        else:
            self.header_chip_var.set("No active profile")

    # ------------------------------------------------------------- behaviour
    def toggle_theme(self) -> None:
        self.is_dark = not self.is_dark
        self.root.style.theme_use(DARK_THEME if self.is_dark else LIGHT_THEME)
        self._configure_styles()
        # Re-color the header (raw tk widgets don't follow ttk themes)
        primary = self.root.style.colors.primary
        for widget in self._header_widgets:
            try:
                widget.configure(bg=primary)
            except tk.TclError:
                pass
        try:
            self.header_chip.configure(bg="#ffffff", fg=primary)
        except tk.TclError:
            pass
        self.theme_btn.configure(text="\u2600  Light" if self.is_dark else "\u263d  Dark")
        self._refresh_status_dots()

    def log(self, message: str) -> None:
        self.output_queue.put(message)

    def _poll_output(self) -> None:
        while not self.output_queue.empty():
            message = self.output_queue.get()
            self.output.insert(END, f"{message}\n")
            self.output.see(END)
        self.root.after(100, self._poll_output)

    def run_background(self, task: Callable[[], None]) -> None:
        def wrapped() -> None:
            try:
                task()
            except DevsyncError as exc:
                self.root.after(0, lambda exc=exc: messagebox.showerror("devsync error", str(exc)))
                self.log(f"Error: {exc}")
            except Exception as exc:  # pragma: no cover - GUI safety net
                self.root.after(0, lambda exc=exc: messagebox.showerror("Unexpected error", str(exc)))
                self.log(f"Unexpected error: {exc}")

        threading.Thread(target=wrapped, daemon=True).start()

    def refresh_all(self) -> None:
        self.refresh_profiles()
        self.refresh_status()
        config = load_config()
        self.repo_var.set(config.get("active_repo") or config.get("default_repo", ""))

    def refresh_profiles(self) -> None:
        profiles = load_profiles()
        names = sorted(profiles)
        self.profile_combo["values"] = names
        if names and self.profile_var.get() not in names:
            self.profile_var.set(names[0])

        self.profiles_tree.delete(*self.profiles_tree.get_children())
        for name in names:
            profile = profiles[name]
            self.profiles_tree.insert(
                "",
                END,
                values=(
                    name,
                    profile.get("git_user_name", ""),
                    profile.get("git_user_email", ""),
                    mask_token(profile.get("github_token", "")),
                ),
            )

    def refresh_status(self) -> None:
        data = get_status_data()
        self.status_profile_var.set(data["active_profile"])
        self.status_user_var.set(data["git_user"])
        self.status_repo_var.set(data["current_repo"])
        self.status_branch_var.set(data["current_branch"])
        self._refresh_status_dots()
        self._refresh_header_chip()

    def save_profile(self) -> None:
        name = self.new_profile_name.get().strip()
        token = self.new_token.get().strip()
        git_name = self.new_git_name.get().strip()
        git_email = self.new_git_email.get().strip()
        if not all([name, token, git_name, git_email]):
            messagebox.showwarning("Missing fields", "Fill profile name, token, git user.name, and git user.email.")
            return
        message = save_profile_data(name, token, git_name, git_email)
        self.new_token.set("")
        self.log(message)
        self.refresh_profiles()
        self.profile_var.set(name)
        messagebox.showinfo("Profile saved", message)

    def save_default_repo(self) -> None:
        repo_url = self.repo_var.get().strip()
        if not repo_url:
            messagebox.showwarning("Missing repo", "Enter a GitHub repo URL.")
            return
        try:
            message = set_default_repo_data(repo_url)
        except Exception as exc:
            messagebox.showerror("Repo error", str(exc))
            return
        self.log(message)
        messagebox.showinfo("Default repo saved", message)

    def choose_base_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.base_dir_var.get() or str(Path.cwd()))
        if selected:
            self.base_dir_var.set(selected)

    def use_selected_profile(self) -> None:
        profile = self.profile_var.get().strip()
        repo_url = self.repo_var.get().strip() or None
        base_dir = Path(self.base_dir_var.get()).expanduser()
        if not profile:
            messagebox.showwarning("Missing profile", "Select or create a profile first.")
            return
        self.log("Starting clone / pull...")

        def task() -> None:
            result = use_profile_data(profile, repo_url, base_dir=base_dir, on_output=self.log)
            self.log("devsync ready")
            self.log(f"Profile: {result['profile']}")
            self.log(f"Repo: {result['repo']}")
            self.log(f"Local path: {result['local_path']}")
            self.log(f"{PROGRESS_FILE}: {result['progress_status']}")
            self.log("Changed files after pull:")
            self.log(result["changed_summary"])
            self.root.after(0, self.refresh_all)
            self.root.after(0, lambda: messagebox.showinfo("Repo ready", f"Repo ready at:\n{result['local_path']}"))

        self.run_background(task)

    def show_status(self) -> None:
        self.refresh_status()
        self.log("Status refreshed.")

    def open_repo_folder(self) -> None:
        config = load_config()
        repo_path = config.get("active_repo_path")
        if not repo_path:
            messagebox.showwarning("No active repo", "Run Clone / Pull Repo first.")
            return
        path = Path(repo_path)
        if not path.exists():
            messagebox.showwarning("Missing folder", f"Repo folder does not exist:\n{path}")
            return
        if hasattr(os, "startfile"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            self.log(f"Repo folder: {path}")

    def preview_handoff(self) -> None:
        try:
            prompt = build_handoff_prompt()
        except DevsyncError as exc:
            messagebox.showerror("Handoff error", str(exc))
            return
        self.handoff_text.delete("1.0", END)
        self.handoff_text.insert(END, prompt)
        self.log("Handoff preview generated.")

    def copy_handoff(self) -> None:
        try:
            prompt = copy_handoff_prompt()
        except DevsyncError as exc:
            messagebox.showerror("Handoff error", str(exc))
            return
        self.handoff_text.delete("1.0", END)
        self.handoff_text.insert(END, prompt)
        self.log("Handoff prompt copied to clipboard!")
        messagebox.showinfo("Copied", "Handoff prompt copied to clipboard!")


def main() -> None:
    if GUI_IMPORT_ERROR:
        raise SystemExit(
            "GUI dependencies are not available. Make sure Python is installed "
            "with Tcl/Tk support and that the optional `ttkbootstrap` package is "
            "installed (it is included in devsync's pyproject dependencies)."
        ) from GUI_IMPORT_ERROR

    root = tb.Window(themename=LIGHT_THEME)
    DevsyncGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
