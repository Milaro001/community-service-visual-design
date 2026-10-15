#!/usr/bin/env python3
"""Check known text and supplied line geometry; no image reading, OCR or aesthetic certification.

Usage: python3 scripts/check_linebreaks.py linebreak-record.json
Exit 0: supplied checks pass; 1: fail; 2: unknown/invalid input.
"""
import argparse
import json
import math
import re
from pathlib import Path


NO_START = set('，。、；：？！）］｝〉》」』】〕〗〙〛’”﹏,.;:!?)]}')
NO_END = set('（［｛〈《「『【〔〖〘〚‘“([{')


def number(value, name, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric')
    if nonnegative and value < 0:
        raise ValueError(f'{name} must be nonnegative')
    return value


def rect(value, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f'{name} must be [x,y,width,height]')
    for v in value:
        number(v, name)
    if value[2] <= 0 or value[3] <= 0:
        raise ValueError(f'{name} width and height must be positive')
    return value


def contains(outer, inner):
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return ox <= x and oy <= y and x + w <= ox + ow and y + h <= oy + oh


def evaluate(data):
    if not isinstance(data, dict):
        raise ValueError('Input must be an object')
    version = data.get('asset_version')
    if not isinstance(version, str) or not version.strip():
        raise ValueError('asset_version is required')
    groups = data.get('groups')
    if not isinstance(groups, list):
        raise ValueError('groups must be a list')
    expected = data.get('expected_group_ids')
    if expected is not None and (not isinstance(expected, list) or not expected or
            any(not isinstance(x, str) or not x for x in expected) or len(set(expected)) != len(expected)):
        raise ValueError('expected_group_ids must contain unique nonempty IDs')
    checks, hints, ids = [], [], set()

    def emit(check, gid, status, evidence, **values):
        checks.append(dict(check=check, target=gid, status=status, evidence=evidence, **values))

    for group in groups:
        if not isinstance(group, dict):
            raise ValueError('Each group must be an object')
        gid = group.get('id')
        if not isinstance(gid, str) or not gid or gid in ids:
            raise ValueError('Each group needs a unique nonempty ID')
        ids.add(gid)
        master, lines = group.get('master_text'), group.get('lines')
        if not isinstance(master, str) or not master:
            raise ValueError(f'{gid}: master_text must be a nonempty string')
        if not isinstance(lines, list) or not lines:
            raise ValueError(f'{gid}: lines must be nonempty')
        spans, joins, cursor, combined, bounds = [], [], 0, '', []
        for i, line in enumerate(lines):
            if not isinstance(line, dict) or not isinstance(line.get('text'), str) or not line['text'].strip():
                raise ValueError(f'{gid}: each line needs nonempty text')
            join = line.get('join_after')
            if not isinstance(join, str) or any(c not in ' \t' for c in join):
                raise ValueError(f'{gid}: join_after must explicitly preserve original spaces/tabs')
            if i == len(lines) - 1 and join:
                raise ValueError(f'{gid}: final join_after must be empty')
            txt = line['text']
            if '\n' in txt or '\r' in txt:
                raise ValueError(f'{gid}: line text cannot contain embedded line breaks')
            spans.append((cursor, cursor + len(txt)))
            cursor += len(txt) + len(join)
            combined += txt + join
            joins.append(join)
            stripped = txt.strip()
            emit('punctuation_boundary', gid, 'fail' if stripped[0] in NO_START or stripped[-1] in NO_END else 'pass',
                 'Basic horizontal line-start/end punctuation subset only', line=i + 1)
            b = line.get('bounds')
            bounds.append(None if b is None else rect(b, f'{gid}.lines[{i}].bounds'))
        emit('text_reconstruction', gid, 'pass' if combined == master else 'fail',
             'Strict reconstruction includes punctuation and join_after whitespace')
        for i in range(len(lines) - 1):
            left, right = lines[i]['text'], lines[i + 1]['text']
            broken = not joins[i] and (
                (left[-1:].isdigit() and right[:1].isdigit()) or
                (re.fullmatch('[A-Za-z]', left[-1:]) and re.fullmatch('[A-Za-z]', right[:1])))
            emit('number_or_word_split', gid, 'fail' if broken else 'pass',
                 'Adjacent digit/Latin-letter split with no original whitespace', after_line=i + 1)
        units = group.get('unbreakable_units')
        if units is None:
            emit('unbreakable_units', gid, 'unknown', 'No explicit project list; protected phrases cannot be inferred')
        else:
            if not isinstance(units, list) or any(not isinstance(u, str) or not u for u in units):
                raise ValueError(f'{gid}: unbreakable_units must be a list of nonempty strings')
            for unit in units:
                if unit not in master:
                    raise ValueError(f'{gid}: unbreakable unit absent from master_text: {unit}')
            failures = []
            if combined == master:
                for unit in units:
                    start = 0
                    while True:
                        start = master.find(unit, start)
                        if start < 0:
                            break
                        end = start + len(unit)
                        if not any(a <= start and end <= b for a, b in spans):
                            failures.append(unit)
                        start += 1
            emit('unbreakable_units', gid, 'fail' if failures else 'unknown' if combined != master else 'pass',
                 'Check all occurrences against supplied line spans', split_units=sorted(set(failures)))
        available = group.get('available_bounds')
        if available is not None:
            rect(available, f'{gid}.available_bounds')
        rendered = group.get('measurement') == 'rendered'
        complete = rendered and available is not None and all(b is not None for b in bounds)
        if not complete:
            emit('line_geometry', gid, 'unknown', 'Requires current rendered line bounds and available region')
        else:
            for i, b in enumerate(bounds):
                emit('line_bounds', gid, 'pass' if contains(available, b) else 'fail',
                     'Supplied visible bounds; script does not measure image pixels', line=i + 1,
                     left_space=b[0] - available[0], right_space=available[0] + available[2] - b[0] - b[2])
        min_gap = group.get('min_line_gap')
        if min_gap is not None:
            number(min_gap, f'{gid}.min_line_gap', nonnegative=True)
        if len(lines) > 1:
            if not complete or min_gap is None:
                emit('line_gap', gid, 'unknown', 'Needs rendered bounds and a project-specific minimum gap')
            else:
                for i in range(len(bounds) - 1):
                    gap = bounds[i + 1][1] - bounds[i][1] - bounds[i][3]
                    emit('line_gap', gid, 'pass' if gap >= min_gap else 'fail',
                         'Horizontal lines in top-to-bottom reading order', after_line=i + 1, actual=gap, minimum=min_gap)
                last_ratio = bounds[-1][2] / max(b[2] for b in bounds)
                if last_ratio < .35:
                    hints.append(dict(target=gid, hint='short_last_line', ratio=last_ratio,
                                      reason='Review meaning and available width; this ratio is not an aesthetic failure'))
    if expected is None:
        emit('inventory', 'all', 'unknown', 'No expected group inventory')
    else:
        emit('inventory', 'all', 'pass' if ids == set(expected) else 'fail', 'Compare supplied and expected group IDs',
             missing=sorted(set(expected) - ids), unexpected=sorted(ids - set(expected)))
    if not groups:
        emit('lines', 'all', 'unknown', 'No groups supplied')
    statuses = [c['status'] for c in checks]
    status = 'fail' if 'fail' in statuses else 'unknown' if 'unknown' in statuses else 'pass'
    return dict(status=status, asset_version=version, checks=checks, review_hints=hints,
                scope='Known text and caller-supplied horizontal line geometry only; no OCR, pixel measurement or poster approval')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.record.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps(dict(status='invalid_input', error=str(exc)), ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'pass': 0, 'fail': 1, 'unknown': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
