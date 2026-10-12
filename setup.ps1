# One-time setup: a venv with the dependencies, and a Start menu shortcut. Needs Python 3.10+ and Claude Code (signed in).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$here\.venv")) { py -3 -m venv "$here\.venv" }
& "$here\.venv\Scripts\python.exe" -m pip install -q -r "$here\requirements.txt"
$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Lorekeeper.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "$here\.venv\Scripts\pythonw.exe"; $s.Arguments = "`"$here\lorekeeper.py`""; $s.WorkingDirectory = $here; $s.Save()
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Write-Warning "Claude Code not found: install it (https://claude.com/claude-code) and run 'claude' once to sign in." }
Write-Host "Done. Start Lorekeeper from the Start menu, or run Lorekeeper.cmd."
