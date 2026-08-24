import hashlib
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pyotp

from .export import merge_accounts, read_backup, write_backup
from .importers import DIGESTS, decode_qr_from_pil, image_from_clipboard, parse_otpauth
from .vault import Vault

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CODE_FONT = ("Consolas", 24, "bold")
GREEN = "#2fb471"
ORANGE = "#e08e45"
RED = "#e05555"
ROW_BG = "#1e1e20"
WINDOW_BG = ("#f0f0f0", "#18181a")


def format_code(code):
    mid = len(code) // 2
    return code[:mid] + " " + code[mid:]


class PasswordPrompt(ctk.CTkToplevel):
    def __init__(self, master, title, prompt, confirm=False):
        super().__init__(master)
        self.title(title)
        self.geometry("410x250")
        self.resizable(False, False)
        self.configure(fg_color=WINDOW_BG)
        self.result = None
        self.confirm_mode = confirm
        self.after(120, self.grab_set)

        ctk.CTkLabel(self, text=prompt, justify="left", anchor="w").pack(
            fill="x", padx=24, pady=(20, 6)
        )
        self.entry = ctk.CTkEntry(self, show="\u2022", width=350, placeholder_text="Password")
        self.entry.pack(padx=24, pady=5)
        self.entry.bind("<Return>", lambda e: self._ok())

        if confirm:
            self.entry2 = ctk.CTkEntry(self, show="\u2022", width=350, placeholder_text="Repeat password")
            self.entry2.pack(padx=24, pady=5)
            self.entry2.bind("<Return>", lambda e: self._ok())
        else:
            self.entry2 = None

        self.error_lbl = ctk.CTkLabel(self, text="", text_color=RED)
        self.error_lbl.pack(padx=24, pady=4)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(2, 16))
        ctk.CTkButton(
            row, text="Cancel", width=120, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray40"), command=self.destroy,
        ).pack(side="left", padx=6)
        ctk.CTkButton(row, text="OK", width=120, command=self._ok).pack(side="left", padx=6)

        self.entry.focus_set()

    def _ok(self):
        password = self.entry.get()
        if not password:
            self.error_lbl.configure(text="Password cannot be empty")
            return
        if self.confirm_mode:
            if len(password) < 8:
                self.error_lbl.configure(text="Use at least 8 characters")
                return
            if password != self.entry2.get():
                self.error_lbl.configure(text="Passwords do not match")
                return
        self.result = password
        self.destroy()


class AddAccountDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save):
        super().__init__(master)
        self.on_save = on_save
        self.parsed = None
        self.title("Add account")
        self.geometry("580x480")
        self.resizable(False, False)
        self.configure(fg_color=WINDOW_BG)
        self.after(120, self.grab_set)

        ctk.CTkLabel(
            self, text="Paste the otpauth:// setup link (or decode a QR code)",
            font=("", 13, "bold"), anchor="w",
        ).pack(fill="x", padx=22, pady=(20, 4))

        self.text = ctk.CTkTextbox(self, height=90, font=("Consolas", 12), wrap="char")
        self.text.pack(fill="x", padx=22)
        self.text.bind("<KeyRelease>", lambda e: self._preview())

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=10)

        def tool_button(text, command):
            return ctk.CTkButton(
                buttons, text=text, command=command, height=30,
                fg_color="transparent", border_width=1,
                border_color=("gray60", "gray40"),
                text_color=("#222222", "#eeeeee"),
            )

        tool_button("Paste link", self._paste_link).pack(side="left", padx=(0, 8))
        tool_button("QR from screenshot", self._qr_clipboard).pack(side="left", padx=(0, 8))
        tool_button("QR from image file\u2026", self._qr_file).pack(side="left")

        self.status_lbl = ctk.CTkLabel(
            self, text="Waiting for a link or QR\u2026", justify="left", anchor="w",
            wraplength=520, text_color="gray60",
        )
        self.status_lbl.pack(fill="x", padx=22, pady=4)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=22, pady=(0, 18))
        ctk.CTkButton(
            bottom, text="Cancel", width=110, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray40"), command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        self.save_btn = ctk.CTkButton(bottom, text="Save account", width=130, state="disabled", command=self._save)
        self.save_btn.pack(side="right")

    def _set_status(self, text, color):
        self.status_lbl.configure(text=text, text_color=color)

    def _paste_link(self):
        try:
            clip = self.clipboard_get()
        except Exception:
            self._set_status("Clipboard has no text.", RED)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", clip.strip())
        self._preview()

    def _qr_clipboard(self):
        image = image_from_clipboard()
        if image is None:
            self._set_status(
                "No image in clipboard.\nTake a screenshot of the QR first (Win+Shift+S).", RED
            )
            return
        self._decode_image(image)

    def _qr_file(self):
        path = filedialog.askopenfilename(
            parent=self, title="Choose a QR image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            from PIL import Image

            image = Image.open(path)
        except Exception as exc:
            self._set_status(f"Could not open image: {exc}", RED)
            return
        self._decode_image(image)

    def _decode_image(self, image):
        uri = decode_qr_from_pil(image)
        if not uri:
            self._set_status("No QR code found in that image.", RED)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", uri)
        self._preview()

    def _preview(self):
        raw = self.text.get("1.0", "end-1c").strip()
        self.parsed = None
        self.save_btn.configure(state="disabled")
        if not raw:
            self._set_status("Waiting for a link or QR\u2026", "gray60")
            return
        try:
            account = parse_otpauth(raw)
        except ValueError as exc:
            self._set_status(str(exc), RED)
            return
        except Exception:
            self._set_status("Could not read that link.", RED)
            return
        self.parsed = account
        name = account["issuer"] or "Unnamed"
        detail = f" \u2014 {account['label']}" if account["label"] and account["label"] != name else ""
        self._set_status(f"{name}{detail}  \u2713  ready to save", GREEN)
        self.save_btn.configure(state="normal")

    def _save(self):
        if self.parsed:
            self.on_save(self.parsed)
            self.destroy()


class AccountRow(ctk.CTkFrame):
    def __init__(self, master, account, app):
        super().__init__(master, fg_color=ROW_BG, corner_radius=10)
        self.app = app
        self.account = account
        self.period = int(account.get("period", 30))
        self.flashing = False
        self.flash_job = None
        self._shown_code = None

        digest = DIGESTS.get(str(account.get("algorithm", "SHA1")).upper(), hashlib.sha1)
        self.totp = pyotp.TOTP(
            account["secret"],
            digits=int(account.get("digits", 6)),
            interval=self.period,
            digest=digest,
        )

        self.grid_columnconfigure(0, weight=1)

        names = ctk.CTkFrame(self, fg_color="transparent")
        names.grid(row=0, column=0, sticky="ew", padx=(14, 4), pady=(10, 2))
        issuer = account.get("issuer") or "Unnamed account"
        ctk.CTkLabel(names, text=issuer, font=("", 15, "bold"), anchor="w").pack(fill="x")
        if account.get("label"):
            ctk.CTkLabel(names, text=account["label"], font=("", 12), text_color="gray60", anchor="w").pack(fill="x")

        self.code_lbl = ctk.CTkLabel(self, text="", font=CODE_FONT, text_color="#eaeaea", width=170)
        self.code_lbl.grid(row=0, column=1, rowspan=2, sticky="e", padx=(4, 8), pady=(8, 0))

        delete_btn = ctk.CTkButton(
            self, text="\u2715", width=28, height=28, corner_radius=6,
            fg_color="transparent", border_width=1, border_color="#44444a",
            hover_color="#33333a", text_color="gray70",
            command=lambda: app.delete_account(self),
        )
        delete_btn._no_copy = True
        delete_btn.grid(row=0, column=2, rowspan=2, sticky="n", padx=(0, 10), pady=10)

        self.bar = ctk.CTkProgressBar(self, height=5, corner_radius=2, progress_color=GREEN)
        self.bar.set(1.0)
        self.bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(2, 10))

        for widget in self._walk(self):
            if not getattr(widget, "_no_copy", False):
                widget.bind("<Button-1>", lambda e: app.copy_account(self))

    @staticmethod
    def _walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from AccountRow._walk(child)


class AuthenticatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("2FA Authenticator")
        self.geometry("520x700")
        self.minsize(450, 560)
        self.vault = Vault()
        self.rows = []
        self._tick_started = False
        if self.vault.exists():
            self._build_unlock()
        else:
            self._build_create()

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def _center_frame(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.place(relx=0.5, rely=0.45, anchor="center")
        return frame

    def _build_create(self):
        self._clear()
        frame = self._center_frame()
        ctk.CTkLabel(frame, text="Welcome", font=("", 26, "bold")).pack(pady=(0, 4))
        ctk.CTkLabel(
            frame,
            text="Create your master password.\nIt unlocks this app and cannot be recovered.",
            text_color="gray60", justify="center",
        ).pack(pady=(0, 18))
        self.pw1 = ctk.CTkEntry(frame, show="\u2022", width=290, placeholder_text="Master password (min 8 chars)")
        self.pw1.pack(pady=5)
        self.pw1.bind("<Return>", lambda e: self.pw2.focus_set())
        self.pw2 = ctk.CTkEntry(frame, show="\u2022", width=290, placeholder_text="Repeat password")
        self.pw2.pack(pady=5)
        self.pw2.bind("<Return>", lambda e: self._do_create())
        self.auth_status = ctk.CTkLabel(frame, text="", text_color=RED)
        self.auth_status.pack(pady=4)
        ctk.CTkButton(frame, text="Create vault", width=290, command=self._do_create).pack(pady=(10, 0))
        self.pw1.focus_set()

    def _do_create(self):
        pw_a, pw_b = self.pw1.get(), self.pw2.get()
        if len(pw_a) < 8:
            self.auth_status.configure(text="Use at least 8 characters")
            return
        if pw_a != pw_b:
            self.auth_status.configure(text="Passwords do not match")
            return
        try:
            self.vault.create(pw_a)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not create the vault:\n{exc}", parent=self)
            return
        self._enter_main()

    def _build_unlock(self):
        self._clear()
        frame = self._center_frame()
        ctk.CTkLabel(frame, text="2FA Authenticator", font=("", 26, "bold")).pack(pady=(0, 2))
        ctk.CTkLabel(frame, text="Enter your master password", text_color="gray60").pack(pady=(0, 16))
        self.pw = ctk.CTkEntry(frame, show="\u2022", width=290, placeholder_text="Master password")
        self.pw.pack(pady=5)
        self.pw.bind("<Return>", lambda e: self._do_unlock())
        self.auth_status = ctk.CTkLabel(frame, text="", text_color=RED)
        self.auth_status.pack(pady=4)
        ctk.CTkButton(frame, text="Unlock", width=290, command=self._do_unlock).pack(pady=(10, 0))
        self.pw.focus_set()

    def _do_unlock(self):
        password = self.pw.get()
        if not password:
            return
        self.auth_status.configure(text="")
        if not self.vault.unlock(password):
            self.auth_status.configure(text="Wrong password")
            self.pw.delete(0, "end")
            return
        self._enter_main()

    def _enter_main(self):
        self._clear()
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(header, text="Your accounts", font=("", 20, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add", width=84, height=30, command=self._open_add).pack(side="right")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=18, pady=(0, 8))

        def tool_button(text, command):
            return ctk.CTkButton(
                tools, text=text, height=28, width=130, command=command,
                fg_color="transparent", border_width=1, border_color=("gray55", "gray35"),
            )

        tool_button("Export backup", self._export_backup).pack(side="left")
        tool_button("Import backup", self._import_backup).pack(side="left", padx=8)

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        ctk.CTkLabel(
            self, text="Click a code to copy it \u2022 codes refresh automatically",
            text_color="gray50", font=("", 11),
        ).pack(side="bottom", pady=8)

        self._refresh_rows()
        if not self._tick_started:
            self._tick_started = True
            self.after(250, self._tick)

    def _refresh_rows(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.rows.clear()
        accounts = self.vault.data.get("accounts", [])
        if not accounts:
            ctk.CTkLabel(
                self.list_frame,
                text="No accounts yet.\nClick \u201c+ Add\u201d to add your first one.",
                text_color="gray55", justify="center", font=("", 14),
            ).pack(pady=48)
            return
        for account in accounts:
            row = AccountRow(self.list_frame, account, self)
            row.pack(fill="x", pady=5, padx=4)
            self.rows.append(row)

    def _tick(self):
        now = time.time()
        for row in self.rows:
            if not row.winfo_exists():
                continue
            remaining = row.period - (now % row.period)
            frac = max(remaining / row.period, 0.0)
            row.bar.set(frac)
            row.bar.configure(progress_color=GREEN if frac > 0.18 else ORANGE)
            code = row.totp.now()
            if code != row._shown_code and not row.flashing:
                row._shown_code = code
                row.code_lbl.configure(text=format_code(code))
        self.after(250, self._tick)

    def copy_account(self, row):
        code = row.totp.now()
        self.clipboard_clear()
        self.clipboard_append(code)
        row.flashing = True
        row.code_lbl.configure(text="Copied \u2713", text_color=GREEN)
        if row.flash_job:
            self.after_cancel(row.flash_job)

        def restore():
            row.flashing = False
            row._shown_code = row.totp.now()
            row.code_lbl.configure(text=format_code(row._shown_code), text_color="#eaeaea")

        row.flash_job = self.after(900, restore)

    def delete_account(self, row):
        account = row.account
        name = account.get("issuer") or account.get("label") or "this account"
        confirm = messagebox.askyesno(
            "Delete account",
            f"Remove {name}?\n\nThe secret will be erased from the vault.",
            parent=self,
        )
        if not confirm:
            return
        self.vault.data["accounts"].remove(account)
        try:
            self.vault.save()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        row.destroy()
        if row in self.rows:
            self.rows.remove(row)
        if not self.rows:
            self._refresh_rows()

    def add_account(self, account):
        for existing in self.vault.data["accounts"]:
            if existing["secret"].lower() == account["secret"].lower() and existing["label"] == account["label"]:
                messagebox.showinfo("Already exists", "That account is already in your list.", parent=self)
                return
        self.vault.data["accounts"].append(account)
        try:
            self.vault.save()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self._refresh_rows()

    def _open_add(self):
        AddAccountDialog(self, on_save=self.add_account)

    def _export_backup(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Save backup",
            defaultextension=".totpbak",
            initialfile="authenticator-backup.totpbak",
            filetypes=[("Authenticator backup", "*.totpbak"), ("All files", "*.*")],
        )
        if not path:
            return
        dialog = PasswordPrompt(self, "Backup password", "Set a password for this backup file.", confirm=True)
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            write_backup(path, self.vault.data, dialog.result)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        messagebox.showinfo("Backup saved", f"Encrypted backup written to:\n{path}", parent=self)

    def _import_backup(self):
        path = filedialog.askopenfilename(
            parent=self, title="Open backup",
            filetypes=[("Authenticator backup", "*.totpbak"), ("All files", "*.*")],
        )
        if not path:
            return
        dialog = PasswordPrompt(self, "Restore backup", "Password of the backup file:")
        self.wait_window(dialog)
        if not dialog.result:
            return
        try:
            data = read_backup(path, dialog.result)
        except Exception:
            messagebox.showerror("Restore failed", "Wrong password or corrupted file.", parent=self)
            return
        accounts = self.vault.data.setdefault("accounts", [])
        added = merge_accounts(accounts, data.get("accounts", []))
        try:
            self.vault.save()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self._refresh_rows()
        total = len(data.get("accounts", []))
        skipped = total - added
        message = f"Added {added} account(s)."
        if skipped:
            message += f"\n{skipped} duplicate(s) skipped."
        messagebox.showinfo("Restore complete", message, parent=self)


def main():
    AuthenticatorApp().mainloop()
