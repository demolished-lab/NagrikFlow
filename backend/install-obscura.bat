@echo off
REM Install obscura stealth browser for Tier-3 fetches
REM Downloads from GitHub releases; adjust URL for latest version.
set OBSCURA_VERSION=0.1.0
set DEST=%USERPROFILE%\.obscura
if not exist "%DEST%" mkdir "%DEST%"
curl -L -o "%DEST%\obscura.exe" "https://github.com/cobalt1006/obscura/releases/download/v%OBSCURA_VERSION%/obscura.exe"
if %ERRORLEVEL% equ 0 (
    echo obscura installed to %DEST%\obscura.exe
) else (
    echo Failed to download obscura. Check https://github.com/cobalt1006/obscura/releases
)
