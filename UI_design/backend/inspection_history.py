"""Small, committed precision-history summaries; no model or image loading."""
from topic16.contracts import read_json, sha256, inside


def read_inspection_history(upgrade, state, asset):
    committed = {r['path']: r for refs in state.get('stages', {}).values() for r in refs}
    rows = []
    for name in ('inspection.json', 'inspection-r2.json', 'inspection-r3.json', 'inspection-r4.json'):
        key = 'reports/tea-quality-v5/' + name
        ref = committed.get(key)
        if ref is None: continue
        path = inside(upgrade, key)
        if sha256(path) != ref['sha256']: raise ValueError('Precision-history checksum differs')
        report = read_json(path); encoding = report.get('viewer_encoding', 'packed')
        if encoding not in ('packed', 'ext32', 'ext32-full', 'packed-ext'):
            raise ValueError('Unknown precision-history encoding')
        url = asset(path, ref['sha256'])
        for result in report['results']:
            browser = result['browser']; values = [r['psnr'] for r in browser['results']]
            import math
            p95 = browser['benchmark']['p95_frame_interval_ms']
            if not values or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in values + [p95]):
                raise ValueError('Precision-history metrics are invalid')
            rows.append({'encoding': encoding, 'method': result['method'], 'status': report['status'],
                'mean_parity_db': sum(values) / len(values), 'minimum_parity_db': min(values),
                'p95_frame_interval_ms': p95, 'report_url': url})
    return rows
