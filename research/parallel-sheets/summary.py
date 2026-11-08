import json
from pathlib import Path
import statistics as s

root = Path('/lab')
rows = []
for p in [root / 'results/measurements.jsonl', root / 'private/measurements.jsonl']:
    if p.exists(): rows.extend(json.loads(line) for line in p.read_text().splitlines())
summary = []
for case in dict.fromkeys(r['case'] for r in rows):
    for mode in dict.fromkeys(r['mode'] for r in rows if r['case'] == case):
        group = [r for r in rows if r['case'] == case and r['mode'] == mode and not r['warmup']]
        if not group: continue
        times = [r['elapsed_s'] for r in group]
        item = {'case':case, 'mode':mode, 'n':len(group), 'median_s':s.median(times),
                'min_s':min(times), 'max_s':max(times), 'stdev_s':s.stdev(times) if len(times)>1 else 0,
                'median_cpu_s':s.median(r['user_s']+r['system_s'] for r in group),
                'median_rss_mib':s.median(r['peak_rss_kib']/1024 for r in group),
                'max_rss_mib':max(r['peak_rss_kib']/1024 for r in group),
                'all_equal':all(r['equal'] for r in group)}
        phases = [r['phase'] for r in group if r['phase']]
        if phases:
            item['phase_medians_s'] = {key:s.median(p[key] for p in phases) for key in phases[0] if key.endswith('_s')}
        summary.append(item)
(root / 'results/summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
