"""Linux Docker experiment. Standard library only. No private input generation or publishing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import struct
import subprocess
import time
import zipfile

LAB = Path('/lab')
FIX = LAB / 'fixtures'
WORK = LAB / 'work'
RESULTS = LAB / 'results'
PRIVATE = LAB / 'private'
O = 'urn:oasis:names:tc:opendocument:xmlns:office:1.0'
T = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
X = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
HEADER = f'<office:document-content xmlns:office="{O}" xmlns:table="{T}" xmlns:text="{X}"><office:body><office:spreadsheet>'
FOOTER = '</office:spreadsheet></office:body></office:document-content>'
MODES = ['baseline', 'serial', '1', '2', '4', '6', 'overlap']

def workbook(sheets):
    return HEADER + ''.join(sheets) + FOOTER

def sheet(body='', name='Sheet'):
    return f'<table:table table:name="{name}">{body}</table:table>'

def cell(value='Value0123456789', attrs=''):
    return f'<table:table-cell {attrs}><text:p>{value}</text:p></table:table-cell>'

def row(body, attrs=''):
    return f'<table:table-row {attrs}>{body}</table:table-row>'

def save(name, content, encoding='utf-8'):
    data = content.encode(encoding) if isinstance(content, str) else content
    path = FIX / (name + '.ods')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('mimetype', 'application/vnd.oasis.opendocument.spreadsheet')
        z.writestr('content.xml', data)
    return {'case': name, 'xml_bytes': len(data), 'ods_bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def generate():
    FIX.mkdir(exist_ok=True)
    inventory = []
    # Exactly 120,000 ordinary cells and 20,000 row templates in each dense case.
    for n in [1, 2, 4, 8, 16, 100, 1000, 5000]:
        rows = 20000 // n
        body = row(cell() * 6) * rows
        inventory.append(save(f'dense-{n}', workbook(sheet(body, f'S{i:04}') for i in range(n))))
    small = row(cell() * 6) * 20
    huge = row(cell() * 6) * (20000 - 91 * 20)
    inventory.append(save('skewed', workbook([sheet(huge, 'Huge')] + [sheet(small, f'S{i}') for i in range(91)])))
    tail = '<table:table-row table:number-rows-repeated="1048575"><table:table-cell table:number-columns-repeated="16384"/></table:table-row>'
    inventory.append(save('empty-tail', workbook(sheet((row(cell()) if i % 2 else '') + tail, f'S{i}') for i in range(1000))))
    repeated = row(cell('Long0123456789 "A"&#9;B&#10;C', 'table:number-columns-repeated="12"'), 'table:number-rows-repeated="20000"')
    inventory.append(save('output-heavy', workbook(sheet(repeated, f'S{i}') for i in range(8))))
    merged = row(cell('M', 'table:number-columns-spanned="2"') + '<table:covered-table-cell/>', 'table:number-rows-repeated="2000"')
    inventory.append(save('merged', workbook(sheet(merged, f'S{i}') for i in range(8))))
    semantic = row(cell('  A  B <text:s text:c="2"/>C<text:tab/>D<text:line-break/>E', 'office:value-type="string" office:string-value="RAW"') + cell('', 'table:formula="of:=1"') + cell('42', 'office:value-type="float" office:value="4.2"'))
    names = ['A/B', 'A?B', 'a_b', 'CON', 'Sheet', 'sheet']
    save('semantics', workbook(sheet(semantic + merged, name) for name in names))
    nsbody = row(cell('αö😀<![CDATA[<table:table>fake</table:table>]]><!-- <table:table> -->' + '<table:table table:name="Nested">' + row(cell('ignored')) + '</table:table>'))
    save('namespaces', workbook([sheet(nsbody, 'Unicode'), '<q:table xmlns:q="' + T + '" q:name="Rebound"><q:table-row><q:table-cell><text:p xmlns:text="urn:wrong">ignored</text:p><p:p xmlns:p="' + X + '">kept</p:p></q:table-cell></q:table-row></q:table>', '<table xmlns="' + T + '" xmlns:t="' + T + '" t:name="Default"><table-row><table-cell><text:p>default</text:p></table-cell></table-row></table>']))
    xml = workbook([sheet(row(cell('café')), 'Enc')])
    for label, enc, decl in [('utf16le', 'utf-16-le', 'UTF-16'), ('utf16be', 'utf-16-be', 'UTF-16'), ('latin1', 'iso-8859-1', 'ISO-8859-1')]:
        raw = ('<?xml version="1.0" encoding="' + decl + '"?>' + xml).encode(enc)
        if label == 'utf16le': raw = b'\xff\xfe' + raw
        if label == 'utf16be': raw = b'\xfe\xff' + raw
        save(label, raw)
    save('bad-trailing', xml + '<bad>')
    save('bad-inside', workbook([sheet(row(cell('ok')), 'First'), sheet('<table:table-row><x></table:table-row>', 'Bad')]))
    save('bad-entity', workbook([sheet(row(cell('&unknown;')))]))
    save('bad-outside-entity', xml.replace('<office:body>', '<office:styles>&unknown;</office:styles><office:body>'))
    save('dtd', '<!DOCTYPE office:document-content [<!ENTITY x "x">]>' + xml)
    save('depth-over', workbook([sheet(row(cell('<x>' * 251 + 'V' + '</x>' * 251)))]))
    save('depth-exact', workbook([sheet(row(cell('<x>' * 249 + 'V' + '</x>' * 249)))]))
    save('cell-over', workbook([sheet(row(cell('V' * (1024 * 1024 + 1))))]))
    save('fields-over', workbook([sheet(row(cell('V', 'table:number-columns-repeated="10000001"')))]))
    save('merges-over', workbook([sheet(row(cell('', 'table:number-columns-spanned="2"') + '<table:covered-table-cell/>', 'table:number-rows-repeated="100001"'))]))
    save('output-over', workbook([sheet(row(cell('V' * 32, 'table:number-columns-repeated="10"'), 'table:number-rows-repeated="1000000"'))]))
    save('merge-budget-over', workbook(sheet(row(cell('', 'table:number-columns-spanned="2"') + '<table:covered-table-cell/>', 'table:number-rows-repeated="100000"'), f'S{i}') for i in range(50)))
    base = xml.encode()
    save('xml-exact', base + b' ' * (64 * 1024 * 1024 - len(base)))
    save('xml-over', base + b' ' * (64 * 1024 * 1024 + 1 - len(base)))
    # Stored ZIP entry: mutate payload without changing CRC, then require full-stream failure.
    crc = FIX / 'bad-crc.ods'
    with zipfile.ZipFile(crc, 'w', compression=zipfile.ZIP_STORED) as z:
        z.writestr('content.xml', xml)
    data = bytearray(crc.read_bytes())
    offset = 30 + struct.unpack_from('<H', data, 26)[0] + struct.unpack_from('<H', data, 28)[0]
    pos = data.index(b'caf', offset)
    data[pos] = ord('C')
    crc.write_bytes(data)
    (RESULTS / 'fixtures.json').write_text(json.dumps(inventory, indent=2))
    return [r['case'] for r in inventory]

def fingerprint(out):
    m = json.loads((out / 'manifest.json').read_bytes())
    timestamp = m.pop('exported_at')
    h = hashlib.sha256(json.dumps(m, sort_keys=True, ensure_ascii=False).encode())
    for p in sorted(out.iterdir()):
        if p.name == 'manifest.json': continue
        data = p.read_bytes()
        if p.name == 'README.txt': data = data.replace(timestamp.encode(), b'<TIME>')
        h.update(p.name.encode()); h.update(data)
    return h.hexdigest(), sum(p.stat().st_size for p in out.glob('*.tsv')), len(m['sheets'])

COUNTER = 0
RUN_ID = str(time.time_ns())
def execute(case, mode, flags=(), private=False):
    global COUNTER
    COUNTER += 1
    WORK.mkdir(exist_ok=True)
    PRIVATE.mkdir(exist_ok=True)
    inp = Path('/private/input.ods') if private else FIX / (case + '.ods')
    out = WORK / f'out-{COUNTER}'
    receipt_dir = PRIVATE if private else RESULTS / 'logs'
    receipt_dir.mkdir(exist_ok=True)
    receipt = receipt_dir / f'{RUN_ID}-{case}-{COUNTER}-{mode}'
    env = dict(os.environ)
    if mode == 'baseline': env.pop('RESEARCH_MODE', None)
    else: env['RESEARCH_MODE'] = mode
    binary = LAB / 'bin' / ('baseline' if mode == 'baseline' else 'prototype')
    args = ['/usr/bin/time', '-f', '{"user_s":%U,"system_s":%S,"peak_rss_kib":%M}', '-o', str(receipt) + '.resource', str(binary), *flags, '--output', str(out), str(inp)]
    t = time.perf_counter()
    with receipt.with_suffix('.stdout').open('wb') as stdout, receipt.with_suffix('.stderr').open('wb') as stderr:
        child = subprocess.Popen(args, env=env, stdout=stdout, stderr=stderr)
        child.wait()
    elapsed = time.perf_counter() - t
    stderr = receipt.with_suffix('.stderr').read_text(errors='replace')
    usage = json.loads(Path(str(receipt) + '.resource').read_text().splitlines()[-1])
    phase = next((json.loads(line[9:]) for line in stderr.splitlines() if line.startswith('RESEARCH ')), None)
    record = {'case': case, 'mode': mode, 'flags': list(flags), 'elapsed_s': elapsed,
              **usage,
              'exit': child.returncode, 'phase': phase, 'cleanup': not out.exists()}
    digest = None
    if child.returncode == 0:
        digest, record['tsv_bytes'], record['sheets'] = fingerprint(out)
        shutil.rmtree(out)
    return record, digest

def append(name, item, private=False):
    with ((PRIVATE if private else RESULTS) / name).open('a') as f:
        f.write(json.dumps(item, sort_keys=True) + '\n')

def timing(cases, repeats=3, start=0, warmup=True):
    for case in cases:
        private = case == 'private-92'
        expected = None
        rotations = ([-1] if warmup else []) + list(range(start, start + repeats))
        for rotation in rotations:
            order = MODES[max(rotation, 0) % len(MODES):] + MODES[:max(rotation, 0) % len(MODES)]
            for mode in order:
                record, digest = execute(case, mode, private=private)
                if expected is None: expected = digest
                record.update(rotation=rotation, warmup=rotation == -1, equal=bool(digest and digest == expected))
                append('measurements.jsonl', record, private)
                assert record['exit'] == 0 and record['equal'], (case, mode, record)
            print('TIMED', case, rotation, flush=True)

def correctness(cases):
    for case in cases:
        private = case == 'private-92'
        for flags in [(), ('--raw',), ('--preserve-whitespace',), ('--raw', '--preserve-whitespace')]:
            reference, digest = execute(case, 'baseline', flags, private)
            assert reference['exit'] == 0, reference
            for mode in ['1', '2', '4', '6', 'overlap']:
                record, actual = execute(case, mode, flags, private)
                record['equal'] = digest == actual
                append('correctness.jsonl', record, private)
                assert record['exit'] == 0 and record['equal'], record
        print('CHECKED', case, flush=True)

def failures():
    cases = ['bad-trailing', 'bad-inside', 'bad-entity', 'bad-outside-entity', 'dtd', 'depth-over', 'cell-over', 'fields-over', 'merges-over', 'bad-crc', 'xml-over', 'output-over', 'merge-budget-over']
    for case in cases:
        for mode in ['baseline', '1', '4', 'overlap']:
            record, _ = execute(case, mode)
            record['expected_rejection'] = record['exit'] == 1 and record['cleanup']
            append('failures.jsonl', record)
            assert record['expected_rejection'], record
        print('REJECTED', case, flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['generate', 'timing', 'correctness', 'failures', 'private', 'all'])
    args = parser.parse_args()
    for p in [FIX, WORK, RESULTS, PRIVATE]: p.mkdir(exist_ok=True)
    cases = [f'dense-{n}' for n in [1, 2, 4, 8, 16, 100, 1000, 5000]] + ['skewed', 'empty-tail', 'output-heavy', 'merged']
    if args.stage in ['all', 'generate']: generate()
    if args.stage in ['all', 'timing']: timing(cases)
    if args.stage in ['all', 'correctness']: correctness(cases + ['semantics', 'namespaces', 'utf16le', 'utf16be', 'latin1', 'depth-exact', 'xml-exact'])
    if args.stage in ['all', 'failures']: failures()
    if args.stage in ['all', 'private']:
        timing(['private-92'])
        correctness(['private-92'])
    print('STAGE_COMPLETE', args.stage, flush=True)

if __name__ == '__main__': main()
