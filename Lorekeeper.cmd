@echo off
rem Starts Lorekeeper in the tray, no console. First run: setup.ps1
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0lorekeeper.py"
