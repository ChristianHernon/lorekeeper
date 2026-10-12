"""First run of an installed Lorekeeper: what setup.ps1 does for a source checkout, done from the app.
  - the Kokoro voice model (~120 MB) downloads in the background, progress in the box; answers use Windows' voice until then
  - no Claude Code? offer to install it (Anthropic's official installer, in a terminal window) and open it to sign in"""
import os, shutil, subprocess, threading, urllib.request
import config

MODEL_URL = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
MODEL_FILES = ('kokoro-v1.0.int8.onnx', 'voices-v1.0.bin')
CLAUDE_INSTALL = 'irm https://claude.ai/install.ps1 | iex'


def missing_models():
    return [f for f in MODEL_FILES if not os.path.exists(os.path.join(config.MODELS, f))]


def download_models(progress=lambda done, total: None):
    """Fetch the missing model files, each to a .part file renamed when whole. Returns True when all are present."""
    os.makedirs(config.MODELS, exist_ok=True)
    todo = missing_models()
    sizes, got = {}, 0
    for f in todo:
        try:
            req = urllib.request.Request(MODEL_URL + f, method='HEAD', headers={'User-Agent': 'Lorekeeper'})
            sizes[f] = int(urllib.request.urlopen(req, timeout=20).headers.get('Content-Length') or 0)
        except Exception:
            sizes[f] = 0
    total = sum(sizes.values())
    for f in todo:
        dest = os.path.join(config.MODELS, f)
        part = dest + '.part'
        with urllib.request.urlopen(urllib.request.Request(MODEL_URL + f, headers={'User-Agent': 'Lorekeeper'}), timeout=60) as r, open(part, 'wb') as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                progress(got, total)
        os.replace(part, dest)
    return not missing_models()


def claude_installed():
    import brain   # its PATH includes where Claude Code's own installer puts it
    return bool(shutil.which('claude'))


def install_claude():
    """Anthropic's official Windows installer in a visible PowerShell window, then Claude Code itself to sign in."""
    cmd = (f"Write-Host 'Installing Claude Code (Anthropic''s official installer)...'; {CLAUDE_INSTALL}; "
           "$env:Path = \"$env:USERPROFILE\\.local\\bin;$env:Path\"; "
           "Write-Host ''; Write-Host 'Now sign in with your Claude Pro or Max account. When you are signed in, close this window.'; claude")
    subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-Command', cmd],
                     creationflags=0x00000010)   # CREATE_NEW_CONSOLE: the person needs to see and type in it


def run(app, box):
    """Called once the app is up. Models first (no questions asked), then Claude Code if it's missing."""
    def models():
        if not missing_models():
            return
        box.show('Getting the voice ready', 'Downloading the voice (about 120 MB, once). Answers use the Windows voice until it is done.',
                 stay=True, title=True)
        last = [-1]

        def progress(done, total):
            pct = int(done * 100 / total) if total else 0
            if pct >= last[0] + 5:
                last[0] = pct
                box.show('Getting the voice ready', f'Downloading the voice: {pct}%', stay=True, title=True)
        try:
            ok = download_models(progress)
        except Exception as e:
            ok = False
            print('model download:', e)
        if ok:
            app.voice._kokoro = None   # loads on the next answer
            box.show('Voice ready', 'Lorekeeper has its voice. Hold the hotkey in a game and ask.', title=True)
        else:
            box.show('Voice download failed', 'Answers use the Windows voice for now. Lorekeeper tries again next time it starts.', title=True)

    def claude():
        if claude_installed():
            return

        def ask():
            from tkinter import messagebox
            if messagebox.askyesno('Lorekeeper needs Claude Code',
                                   'Lorekeeper answers through Claude Code, on the Claude Pro or Max plan you already have '
                                   '(no API key, no extra bill).\n\nInstall Claude Code now? A window opens with Anthropic\'s '
                                   'official installer, then asks you to sign in.', parent=box.root):
                install_claude()
                box.show('Claude Code', 'Finish the install and sign in in the window that opened. Then hold the hotkey in a game and ask.',
                         stay=True, title=True)
            else:
                box.show('Claude Code', 'Lorekeeper can\'t answer without it. Install it any time: claude.com/claude-code', stay=True, title=True)
        box.root.after(2500, ask)

    def both():
        claude()
        models()
    threading.Thread(target=both, daemon=True).start()
