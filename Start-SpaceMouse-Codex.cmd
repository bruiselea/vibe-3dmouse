@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python virtual environment was not found.
  echo Run the setup steps in README.md first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m spacemouse_input gui
