# PyInstaller recipe: one folder (dist/Lorekeeper) with Python and every dependency inside. Build from the repo root:
#   pyinstaller packaging/lorekeeper.spec --noconfirm
# Then packaging/lorekeeper.iss wraps the folder into Lorekeeper-Setup-<version>.exe (Inno Setup).
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
datas = [(os.path.join(ROOT, 'assets'), 'assets')]
binaries, hidden = [], ['pystray._win32', 'keyring.backends.Windows', 'comtypes.stream']
# packages that carry native libraries or data files (models' configs, espeak voices, PortAudio, libsndfile…)
for pkg in ('faster_whisper', 'ctranslate2', 'onnxruntime', 'kokoro_onnx', 'espeakng_loader', 'language_tags', 'phonemizer',
            'sounddevice', '_sounddevice_data', 'soundfile', '_soundfile_data', 'dxcam', 'av', 'tokenizers', 'edge_tts', 'certifi'):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception as e:
        print('skip', pkg, e)

a = Analysis([os.path.join(ROOT, 'lorekeeper.py')], pathex=[ROOT], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=['pytest', 'matplotlib', 'IPython', 'tkinter.test', 'PyInstaller'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Lorekeeper', icon=os.path.join(ROOT, 'assets', 'lorekeeper.ico'),
          console=False, upx=False, version=None)
coll = COLLECT(exe, a.binaries, a.datas, name='Lorekeeper', upx=False)
