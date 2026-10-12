#!/usr/bin/env python3
"""Keep GitHub's clone and view counts past their 14-day window: merges the daily numbers into a CSV.

  python tools/github_traffic.py [--repo FindlayHi/lorekeeper] [--csv ~/lorekeeper-traffic.csv]

Needs push access to the repo. Auth: GH_TOKEN (or GITHUB_TOKEN) if set, else the `gh` CLI's login.
Run it at least weekly; days already in the CSV are updated (today's numbers grow until the day ends), never dropped.
Columns: date, clones, unique_cloners, views, unique_visitors. Unique counts are per day: don't add them across days
(GitHub's 14-day "uniques" total is printed instead). Stdlib only.

Schedule it, e.g. Windows Task Scheduler, daily at 09:00:
  schtasks /Create /SC DAILY /ST 09:00 /TN "Lorekeeper traffic" /TR "py C:\\Users\\you\\src\\lorekeeper\\tools\\github_traffic.py"
or cron (Linux/WSL):  0 9 * * *  python3 ~/src/lorekeeper/tools/github_traffic.py
"""
import argparse, csv, json, os, shutil, subprocess, urllib.request

FIELDS = ['date', 'clones', 'unique_cloners', 'views', 'unique_visitors']


def api(path):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        req = urllib.request.Request('https://api.github.com/' + path, headers={
            'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'User-Agent': 'lorekeeper-traffic'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    gh = shutil.which('gh')
    if not gh:
        raise SystemExit('Set GH_TOKEN, or install the gh CLI and run `gh auth login`.')
    return json.loads(subprocess.run([gh, 'api', path], capture_output=True, text=True, check=True).stdout)


def merge(rows, clones, views):
    """rows: {date: row} from the CSV. Newer API numbers win for the days they cover."""
    for key, data, n, u in (('clones', clones, 'clones', 'unique_cloners'), ('views', views, 'views', 'unique_visitors')):
        for d in data.get(key, []):
            day = d['timestamp'][:10]
            row = rows.setdefault(day, {f: '' for f in FIELDS} | {'date': day})
            row[n], row[u] = d['count'], d['uniques']
    for row in rows.values():
        for f in FIELDS[1:]:
            if row.get(f) in ('', None):
                row[f] = 0   # a day that one list has and the other doesn't had none of it
    return rows


def read(path):
    try:
        with open(path, newline='', encoding='utf-8') as f:
            return {r['date']: r for r in csv.DictReader(f)}
    except FileNotFoundError:
        return {}


def write(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows[d] for d in sorted(rows))
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--repo', default='FindlayHi/lorekeeper')
    ap.add_argument('--csv', default=os.path.join(os.path.expanduser('~'), 'lorekeeper-traffic.csv'))
    a = ap.parse_args()
    clones, views = api(f'repos/{a.repo}/traffic/clones'), api(f'repos/{a.repo}/traffic/views')
    rows = merge(read(a.csv), clones, views)
    write(a.csv, rows)
    total = sum(int(r['clones']) for r in rows.values())
    print(f"{a.csv}: {len(rows)} days, {total} clones in all. Last 14 days: {clones.get('count', 0)} clones by "
          f"{clones.get('uniques', 0)} unique cloners, {views.get('count', 0)} views by {views.get('uniques', 0)} visitors.")


if __name__ == '__main__':
    main()
