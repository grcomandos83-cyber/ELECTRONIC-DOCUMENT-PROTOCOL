@echo off
cd /d "%~dp0"
if exist "C:\Users\grego\AppData\Local\Programs\Python\Python314\python.exe" (
    "C:\Users\grego\AppData\Local\Programs\Python\Python314\python.exe" main.py
) else if exist "C:\Users\grego\AppData\Local\Programs\Python\Python313\python.exe" (
    "C:\Users\grego\AppData\Local\Programs\Python\Python313\python.exe" main.py
) else (
    python main.py
)
