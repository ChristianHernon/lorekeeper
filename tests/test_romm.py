import os, sys, tempfile
os.environ.setdefault('LOREKEEPER_DIR', tempfile.mkdtemp())
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import brain, games, romm  # noqa: E402


def test_emulator_titles():
    c = romm.clean_title
    assert c('RetroArch Snes9x 1.62.3 || Super Metroid (Japan, USA) (En,Ja) || 60 FPS') == ['Super Metroid']
    assert c('Dolphin 2412 | JIT64 DC | Vulkan | HLE | Super Mario Sunshine (GMSE01)') == ['Super Mario Sunshine']
    assert c('Chrono Trigger (USA) - DuckStation') == ['Chrono Trigger']
    assert c('RetroArch') == []


def test_emulators_recognised():
    assert romm.EMULATORS.search(r'C:\RetroArch-Win64\retroarch.exe')
    assert romm.EMULATORS.search(r'C:\Emu\duckstation-qt-x64-ReleaseLTCG.exe')
    assert not romm.EMULATORS.search(r'C:\Games\aresonance.exe')
    assert not romm.EMULATORS.search(r'C:\Windows\notepad.exe')


def test_emulator_without_romm_names_the_game():
    g, _ = games.current(r'C:\RetroArch-Win64\retroarch.exe', 'RetroArch Snes9x 1.62.3 || Super Metroid (USA)')
    assert g == {'name': 'Super Metroid', 'id': '', 'source': 'emulator', 'dir': ''}


def test_platform_in_prompt():
    r = brain.request('how do I beat Kraid', {'name': 'Super Metroid', 'id': '12', 'source': 'romm', 'platform': 'Super Nintendo'}, '', [])
    assert r.startswith('Game: Super Metroid (Super Nintendo)')


def test_update_versions():
    import updater
    assert updater.newer('0.1.10', '0.1.9') and updater.newer('v0.2.0', '0.1.3') and updater.newer('1.0.0', '0.9.99')
    assert not updater.newer('0.1.3', '0.1.3') and not updater.newer('0.1.2', '0.1.3') and not updater.newer('garbage', '0.1.3')
