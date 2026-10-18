@echo off
setlocal

:: ─────────────────────────────────────────────────────────────
::  Ενδιάμεσο Σενάριο Εκκαθάρισης & Εκκίνησης (Bootstrap Trampoline)
::  Αποτρέπει σφάλματα εκκίνησης (DLL Crashes / Failed to load Python DLL)
::  καθαρίζοντας τις μεταβλητές περιβάλλοντος του PyInstaller bootloader.
:: ─────────────────────────────────────────────────────────────

:: 1. Ρητή μετάβαση στον κατάλογο εγκατάστασης της εφαρμογής
cd /d "%~dp0"

:: 2. Οριστικός καθαρισμός μεταβλητών παλιού PyInstaller περιβάλλοντος
set _MEIPASS2=
set _MEIPASS=
set PYTHONPATH=
set PYTHONHOME=
set PYINSTALLER_STRICT_UNPACK_PROCESS=

:: 3. Εκκίνηση της εφαρμογής σε παρθένο/καθαρό περιβάλλον
start "" "%~dp0Protokollo.exe" %*

endlocal
exit /b 0
