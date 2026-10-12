# One-time setup: a venv with the dependencies, and a Start menu shortcut. Needs Python 3.10+ and Claude Code (signed in).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$here\.venv")) { py -3 -m venv "$here\.venv" }
& "$here\.venv\Scripts\python.exe" -m pip install -q -r "$here\requirements.txt"
$models = "$env:LOCALAPPDATA\Lorekeeper\models"
New-Item -ItemType Directory -Force $models | Out-Null
$sums = @{ 'kokoro-v1.0.int8.onnx' = '6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb'   # keep in step with firstrun.py
           'voices-v1.0.bin' = 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d' }
foreach ($f in $sums.Keys) {   # the offline voice, ~120 MB once
  if (-not (Test-Path "$models\$f")) {
    Invoke-WebRequest "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f" -OutFile "$models\$f.part"
    if ((Get-FileHash "$models\$f.part" -Algorithm SHA256).Hash -ne $sums[$f]) { Remove-Item "$models\$f.part"; throw "$f does not match its expected checksum" }
    Move-Item "$models\$f.part" "$models\$f"
  }
}
$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Lorekeeper.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "$here\.venv\Scripts\pythonw.exe"; $s.Arguments = "`"$here\lorekeeper.py`""; $s.WorkingDirectory = $here
$s.IconLocation = "$here\assets\lorekeeper.ico,0"; $s.Save()
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Write-Warning "Claude Code not found: install it (https://claude.com/claude-code) and run 'claude' once to sign in." }
Write-Host "Done. Start Lorekeeper from the Start menu, or run Lorekeeper.cmd."
