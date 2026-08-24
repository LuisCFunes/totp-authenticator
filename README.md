# 2FA Authenticator

A simple desktop two-factor authenticator (TOTP) for Windows, built for personal use. Generates standard RFC 6238 time-based codes — compatible with GitHub, Google, Discord, and any site that supports authenticator apps.

## Features

- Live 6/8-digit TOTP codes with countdown bar, click to copy
- Add accounts by pasting an `otpauth://` link or importing a QR code from a screenshot / image file
- Vault encrypted at rest: scrypt key derivation + AES-256-GCM (stored in `%APPDATA%\TOTPAuthenticator\`)
- Encrypted backup export / restore
- Standalone `.exe` build via PyInstaller

## Run from source

Requires Python 3.10+ (developed on 3.12).

```
pip install -r requirements.txt
python main.py
```

## Build the executable

```
python scripts/make_icon.py      # one-time, generates assets/icon.ico
powershell -File scripts/build.ps1
```

Output: `dist/2FA-Authenticator.exe` — single file, no Python needed on the target machine.

## Usage

1. First launch: create a master password (unrecoverable — it protects the vault).
2. `+ Add`: paste the site's `otpauth://totp/...` setup link, or press Win+Shift+S over the site's QR code and use *QR from screenshot*.
3. Click any code to copy it, then paste it into the login form.
4. Use *Export backup* to save an encrypted file you can restore elsewhere.

## Security notes

- Secrets are only ever written to disk encrypted (vault and backups).
- The master password cannot be recovered; losing it means losing access to stored secrets (keep your sites' recovery codes!).
- Backups are protected by their own password, independent of the master password.

## Project layout

```
main.py               entry point
src/vault.py          encryption container + vault session
src/importers.py      otpauth parsing, QR decoding, clipboard image grab
src/export.py         encrypted backups and merge logic
src/app.py            CustomTkinter UI (unlock screen, account list, dialogs)
scripts/test_logic.py non-GUI test suite
scripts/build.ps1     PyInstaller build script
```
