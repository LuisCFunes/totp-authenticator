$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)

python -m PyInstaller --noconfirm --onefile --windowed `
    --name "2FA-Authenticator" `
    --icon assets/icon.ico `
    --collect-all customtkinter `
    main.py

if ($?) {
    Write-Host ""
    Write-Host "Build complete -> dist\2FA-Authenticator.exe"
}
