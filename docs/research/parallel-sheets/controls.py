"""Additional compatibility probes; record prototype gaps without relabeling them product bugs."""
import json
import runner as r

ordinary = r.sheet(r.row(r.cell('V')), 'Ordinary')
ignored = '<office:annotation><office:body><office:spreadsheet>' + r.sheet(r.row(r.cell('ignored')), 'Ignored') + '</office:spreadsheet></office:body></office:annotation>'
r.save('probe-ignored-spreadsheet', r.workbook([ordinary]).replace('<office:body>', ignored + '<office:body>', 1))
r.save('probe-namespace-reference', r.workbook([ordinary]).replace(r.T, r.T.replace(':1.0', '&#58;1.0')))
r.save('probe-duplicate-attribute', r.workbook([ordinary]).replace('table:name="Ordinary"', 'table:name="Ordinary" table:name="Duplicate"'))
r.save('probe-utf8-malformed', r.workbook([ordinary]).encode().replace(b'V</text:p>', b'\xc3</text:p>'))
for case in ['probe-ignored-spreadsheet', 'probe-namespace-reference', 'probe-duplicate-attribute', 'probe-utf8-malformed']:
    for flags in [(), ('--raw',), ('--preserve-whitespace',), ('--raw', '--preserve-whitespace')]:
        baseline, digest = r.execute(case, 'baseline', flags)
        for mode in ['1', '4', 'overlap']:
            record, actual = r.execute(case, mode, flags)
            record['baseline_exit'] = baseline['exit']
            record['compatible'] = record['exit'] == baseline['exit'] and (digest == actual if digest else record['cleanup'])
            r.append('probes.jsonl', record)
    print('PROBED', case, flush=True)

# Bounded memory/cost diagnostic: original XML is <200 KiB, but the prototype copies
# and reparses every ancestor start tag for every sheet. This is a prototype design cost.
padding = 'P' * (128 * 1024)
r.save('probe-large-ancestor', r.workbook(r.sheet('', f'S{i}') for i in range(400)).replace('<office:document-content ', '<office:document-content padding="' + padding + '" ', 1))
expected = None
for mode in r.MODES:
    record, digest = r.execute('probe-large-ancestor', mode)
    if expected is None: expected = digest
    record['compatible'] = record['exit'] == 0 and digest == expected
    record['single_memory_diagnostic'] = True
    r.append('probes.jsonl', record)
    assert record['compatible'], record
print('PROBED large-ancestor', flush=True)
