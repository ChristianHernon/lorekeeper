import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import github_traffic as gt  # noqa: E402


def test_merge_keeps_history_and_updates_days(tmp_path):
    path = str(tmp_path / 't.csv')
    gt.write(path, gt.merge({}, {'clones': [{'timestamp': '2026-01-01T00:00:00Z', 'count': 3, 'uniques': 2}]}, {'views': []}))
    later = gt.merge(gt.read(path), {'clones': [{'timestamp': '2026-01-15T00:00:00Z', 'count': 1, 'uniques': 1}]},
                     {'views': [{'timestamp': '2026-01-15T00:00:00Z', 'count': 9, 'uniques': 4}]})
    gt.write(path, later)
    rows = gt.read(path)
    assert list(rows) == ['2026-01-01', '2026-01-15']   # the old day outlived the API window
    assert rows['2026-01-01']['clones'] == '3' and rows['2026-01-01']['views'] == '0'
    assert rows['2026-01-15'] == {'date': '2026-01-15', 'clones': '1', 'unique_cloners': '1', 'views': '9', 'unique_visitors': '4'}
