@echo off
chcp 65001 >nul
echo ========================================================
echo   Ηλεκτρονικό Πρωτόκολλο Εγγράφων — Τοπική Μεταγλώττιση
echo ========================================================
echo.

where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Το PyInstaller δεν βρέθηκε. Εγκατάσταση...
    pip install pyinstaller
)

echo [*] Μεταγλώττιση με PyInstaller (build.spec)...
pyinstaller --noconfirm --clean build.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Η εφαρμογή δημιουργήθηκε επιτυχώς στον φάκελο:
    echo      dist\Protokollo\Protokollo.exe
    echo.
) else (
    echo.
    echo [ERROR] Η μεταγλώττιση απέτυχε. Ελέγξτε τα παραπάνω μηνύματα.
    echo.
)
pause
