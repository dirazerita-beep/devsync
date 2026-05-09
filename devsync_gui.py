from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Callable

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ModuleNotFoundError as exc:
    tk = None
    filedialog = None
    messagebox = None
    scrolledtext = None
    ttk = None
    TKINTER_IMPORT_ERROR = exc
else:
    TKINTER_IMPORT_ERROR = None

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


class DevsyncGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("devsync")
        self.root.geometry("920x680")
        self.output_queue: queue.Queue[str] = queue.Queue()

        self.profile_var = tk.StringVar()
        self.repo_var = tk.StringVar()
        self.base_dir_var = tk.StringVar(value=str(Path.cwd()))

        self._build()
        self.refresh_all()
        self._poll_output()

    def _build(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_tab = ttk.Frame(notebook)
        profiles_tab = ttk.Frame(notebook)
        handoff_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Repo Sync")
        notebook.add(profiles_tab, text="Profiles")
        notebook.add(handoff_tab, text="Handoff")

        self._build_main_tab(main_tab)
        self._build_profiles_tab(profiles_tab)
        self._build_handoff_tab(handoff_tab)

        output_frame = ttk.LabelFrame(self.root, text="Log")
        output_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        self.output = scrolledtext.ScrolledText(output_frame, height=8, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _build_main_tab(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Profile").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.profile_combo = ttk.Combobox(frame, textvariable=self.profile_var, state="readonly")
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(frame, text="Refresh", command=self.refresh_all).grid(row=0, column=2, sticky="ew", padx=8, pady=8)

        ttk.Label(frame, text="GitHub repo URL").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(frame, textvariable=self.repo_var).grid(row=1, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(frame, text="Save Default Repo", command=self.save_default_repo).grid(
            row=1, column=2, sticky="ew", padx=8, pady=8
        )

        ttk.Label(frame, text="Local parent folder").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(frame, textvariable=self.base_dir_var).grid(row=2, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(frame, text="Browse", command=self.choose_base_dir).grid(row=2, column=2, sticky="ew", padx=8, pady=8)

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        buttons.columnconfigure((0, 1, 2, 3), weight=1)
        ttk.Button(buttons, text="Clone / Pull Repo", command=self.use_selected_profile).grid(
            row=0, column=0, sticky="ew", padx=4
        )
        ttk.Button(buttons, text="Show Status", command=self.show_status).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(buttons, text="Open Repo Folder", command=self.open_repo_folder).grid(
            row=0, column=2, sticky="ew", padx=4
        )
        ttk.Button(buttons, text="Copy Handoff", command=self.copy_handoff).grid(row=0, column=3, sticky="ew", padx=4)

        status_frame = ttk.LabelFrame(frame, text="Current status")
        status_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)
        frame.rowconfigure(4, weight=1)
        self.status_tree = ttk.Treeview(status_frame, columns=("field", "value"), show="headings", height=6)
        self.status_tree.heading("field", text="Field")
        self.status_tree.heading("value", text="Value")
        self.status_tree.column("field", width=160, anchor="w")
        self.status_tree.column("value", width=600, anchor="w")
        self.status_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _build_profiles_tab(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Profile name").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        self.new_profile_name = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_profile_name).grid(row=0, column=1, sticky="ew", padx=8, pady=8)

        ttk.Label(frame, text="GitHub token").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        self.new_token = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_token, show="*").grid(row=1, column=1, sticky="ew", padx=8, pady=8)

        ttk.Label(frame, text="Git user.name").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        self.new_git_name = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_git_name).grid(row=2, column=1, sticky="ew", padx=8, pady=8)

        ttk.Label(frame, text="Git user.email").grid(row=3, column=0, sticky="w", padx=8, pady=8)
        self.new_git_email = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_git_email).grid(row=3, column=1, sticky="ew", padx=8, pady=8)

        ttk.Button(frame, text="Save Profile", command=self.save_profile).grid(
            row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=8
        )

        self.profiles_tree = ttk.Treeview(frame, columns=("name", "git_name", "email", "token"), show="headings")
        self.profiles_tree.heading("name", text="Name")
        self.profiles_tree.heading("git_name", text="Git User Name")
        self.profiles_tree.heading("email", text="Email")
        self.profiles_tree.heading("token", text="Token")
        self.profiles_tree.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        frame.rowconfigure(5, weight=1)

    def _build_handoff_tab(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        buttons = ttk.Frame(frame)
        buttons.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(buttons, text="Preview Handoff", command=self.preview_handoff).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Copy Handoff to Clipboard", command=self.copy_handoff).pack(side=tk.LEFT, padx=4)

        self.handoff_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        self.handoff_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    def log(self, message: str) -> None:
        self.output_queue.put(message)

    def _poll_output(self) -> None:
        while not self.output_queue.empty():
            message = self.output_queue.get()
            self.output.insert(tk.END, f"{message}\n")
            self.output.see(tk.END)
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
                tk.END,
                values=(
                    name,
                    profile.get("git_user_name", ""),
                    profile.get("git_user_email", ""),
                    mask_token(profile.get("github_token", "")),
                ),
            )

    def refresh_status(self) -> None:
        self.status_tree.delete(*self.status_tree.get_children())
        data = get_status_data()
        for field, value in [
            ("Active profile", data["active_profile"]),
            ("Git user", data["git_user"]),
            ("Current repo", data["current_repo"]),
            ("Current branch", data["current_branch"]),
        ]:
            self.status_tree.insert("", tk.END, values=(field, value))

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
            os.startfile(path)
        else:
            self.log(f"Repo folder: {path}")

    def preview_handoff(self) -> None:
        try:
            prompt = build_handoff_prompt()
        except DevsyncError as exc:
            messagebox.showerror("Handoff error", str(exc))
            return
        self.handoff_text.delete("1.0", tk.END)
        self.handoff_text.insert(tk.END, prompt)
        self.log("Handoff preview generated.")

    def copy_handoff(self) -> None:
        try:
            prompt = copy_handoff_prompt()
        except DevsyncError as exc:
            messagebox.showerror("Handoff error", str(exc))
            return
        self.handoff_text.delete("1.0", tk.END)
        self.handoff_text.insert(tk.END, prompt)
        self.log("Handoff prompt copied to clipboard!")
        messagebox.showinfo("Copied", "Handoff prompt copied to clipboard!")


def main() -> None:
    if TKINTER_IMPORT_ERROR:
        raise SystemExit(
            "Tkinter is not available in this Python installation. "
            "Install Python from python.org with Tcl/Tk support, then reinstall devsync."
        ) from TKINTER_IMPORT_ERROR

    root = tk.Tk()
    DevsyncGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
