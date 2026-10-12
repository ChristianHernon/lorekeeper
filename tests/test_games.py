import json, os, sys, tempfile

D = tempfile.mkdtemp()
os.environ['LOREKEEPER_DIR'] = D
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import games  # noqa: E402

LIB = r'''"libraryfolders"
{
	"0"
	{
		"path"		"%s"
		"apps" { "1245620" "1" }
	}
}'''

ACF = '''"AppState"
{
	"appid"		"%s"
	"name"		"%s"
	"installdir"		"%s"
}'''


def steam_tree():
    steam = tempfile.mkdtemp()
    apps = os.path.join(steam, 'steamapps')
    os.makedirs(apps)
    open(os.path.join(apps, 'libraryfolders.vdf'), 'w').write(LIB % steam.replace('\\', '\\\\'))
    for appid, name, d in [('1245620', 'ELDEN RING', 'ELDEN RING'), ('228980', 'Steamworks Common Redistributables', 'Steamworks Shared'),
                           ('1086940', "Baldur's Gate 3", "Baldurs Gate 3")]:
        open(os.path.join(apps, f'appmanifest_{appid}.acf'), 'w').write(ACF % (appid, name, d))
    return steam


def test_vdf_nested():
    v = games.vdf('"a" { "b" "1" "c" { "d" "x\\\\y" } } "e" "2"')
    assert v == {'a': {'b': '1', 'c': {'d': 'x\\y'}}, 'e': '2'}


def test_steam_index_skips_tools():
    steam = steam_tree()
    names = sorted(g['name'] for g in games.steam_games(steam))
    assert names == ["Baldur's Gate 3", 'ELDEN RING']


def test_match_by_exe_and_title():
    gs = games.steam_games(steam_tree())
    er = next(g for g in gs if g['name'] == 'ELDEN RING')
    assert games.match(os.path.join(er['dir'], 'Game', 'eldenring.exe'), '', gs)['name'] == 'ELDEN RING'
    assert games.match(r'C:\elsewhere\bg3.exe', "Baldur's Gate 3 (1.0)", gs)['name'] == "Baldur's Gate 3"
    assert games.match(r'C:\Windows\notepad.exe', 'Untitled - Notepad', gs) is None


def test_epic_manifest():
    m = tempfile.mkdtemp()
    json.dump({'DisplayName': 'Hades', 'AppName': 'Min', 'InstallLocation': r'C:\Epic\Hades', 'AppCategories': ['public', 'games']},
              open(os.path.join(m, 'x.item'), 'w'))
    json.dump({'DisplayName': 'Unreal', 'InstallLocation': r'C:\Epic\UE', 'AppCategories': ['engines']}, open(os.path.join(m, 'y.item'), 'w'))
    assert [g['name'] for g in games.epic_games(m)] == ['Hades']


def test_find_named_game():
    gs = games.steam_games(steam_tree())
    assert games.find('elden ring', gs)['name'] == 'ELDEN RING'
    assert games.find('baldurs gate', gs)['name'] == "Baldur's Gate 3"
    assert games.find('chrono trigger', gs) == {'name': 'Chrono Trigger', 'id': '', 'source': 'named', 'dir': ''}


def test_pin_holds_until_another_game():
    gs = games.steam_games(steam_tree())
    json.dump(gs, open(games.INDEX, 'w'))
    games.pin({'name': 'Chrono Trigger'}, r'C:\emu\retroarch.exe')
    assert games.current(r'C:\emu\retroarch.exe', 'RetroArch')[0]['name'] == 'Chrono Trigger'
    assert games.current(r'C:\Program Files\Google\Chrome\chrome.exe', 'wiki')[0]['name'] == 'Chrono Trigger'
    er = os.path.join(gs[0]['dir'], 'game.exe')
    assert games.current(er, '')[0]['name'] == gs[0]['name']
    assert games.pinned() is None
