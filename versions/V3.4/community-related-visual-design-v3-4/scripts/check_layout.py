#!/usr/bin/env python3
"""Check supplied rendered measurements, not pixels or aesthetic quality.

Usage: python check_layout.py layout-measurements.json
Exit 0: supplied checks pass; 1: fail; 2: unknown/invalid input.
No result certifies glyph accuracy, actual visibility, human readability or approval.
"""
import argparse
import json
import math
import re
from pathlib import Path


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    return value


def rect(value, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f'{name} must be [x,y,width,height]')
    for i, v in enumerate(value):
        number(v, f'{name}[{i}]', positive=i >= 2)
    return value


def contains(outer, inner):
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return x >= ox and y >= oy and x+w <= ox+ow and y+h <= oy+oh


def luminance(color):
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
        raise ValueError('sample colors must be opaque #RRGGBB from the actual composite')
    rgb = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
    linear = [c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4 for c in rgb]
    return sum(a*b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(foreground, background):
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b+0.05)/(a+0.05)


def evaluate(data):
    if not isinstance(data, dict):
        raise ValueError('Input must be an object')
    checks = []
    def emit(check, target, status, evidence, **values):
        checks.append(dict(check=check, target=target, status=status, evidence=evidence, **values))
    version = data.get('asset_version')
    if not isinstance(version, str) or not version.strip():
        raise ValueError('asset_version is required to bind measurements')
    canvas = data.get('canvas', {})
    if not isinstance(canvas, dict):
        raise ValueError('canvas must be an object')
    if canvas.get('unit') not in ('px', 'design_px', 'mm'):
        raise ValueError('canvas.unit must be px, design_px or mm; all measurements use this unit')
    width = number(canvas.get('width'), 'canvas.width', True)
    height = number(canvas.get('height'), 'canvas.height', True)
    safe = canvas.get('safe_rect')
    if safe is not None:
        rect(safe, 'safe_rect')
        if not contains([0, 0, width, height], safe):
            raise ValueError('safe_rect must be within canvas')
    expected = data.get('expected_group_ids')
    if expected is not None and (not isinstance(expected, list) or not expected or
        any(not isinstance(i, str) or not i for i in expected) or len(set(expected)) != len(expected)):
        raise ValueError('expected_group_ids must contain unique nonempty IDs')
    groups = data.get('groups', [])
    if not isinstance(groups, list):
        raise ValueError('groups must be a list')
    ids = set()
    for g in groups:
        if not isinstance(g, dict) or not isinstance(g.get('id'), str) or not g['id'] or g['id'] in ids:
            raise ValueError('Each group needs a unique nonempty id')
        gid = g['id']; ids.add(gid)
        rendered = g.get('measurement') == 'rendered'
        bounds = g.get('visible_bounds')
        if bounds is not None:
            rect(bounds, 'visible_bounds')
        if rendered and bounds is not None:
            emit('canvas_bounds', gid, 'pass' if contains([0,0,width,height], bounds) else 'fail', 'supplied visible bounds')
            emit('safe_area', gid, 'unknown' if safe is None else ('pass' if contains(safe,bounds) else 'fail'), 'supplied safe rectangle')
        else:
            emit('canvas_bounds', gid, 'unknown', 'No rendered visible bounds; estimates cannot pass')
            emit('safe_area', gid, 'unknown', 'No rendered visible bounds')
        for check, actual_key, limit_key, is_min in (
            ('capacity', 'required_height', 'available_height', False),
            ('min_glyph_height', 'glyph_height', 'min_glyph_height', True)):
            actual, limit = g.get(actual_key), g.get(limit_key)
            if actual is not None: number(actual,actual_key,True)
            if limit is not None: number(limit,limit_key,True)
            if rendered and actual is not None and limit is not None:
                passed = actual >= limit if is_min else actual <= limit
                emit(check,gid,'pass' if passed else 'fail','supplied rendered measurements',actual=actual,limit=limit)
            else:
                emit(check,gid,'unknown','Missing project limit or rendered measurement')
        samples = g.get('contrast_samples', [])
        if not isinstance(samples,list): raise ValueError('contrast_samples must be a list')
        threshold = g.get('contrast_min',4.5)
        number(threshold,'contrast_min',True)
        if not 1 <= threshold <= 21: raise ValueError('contrast_min must be within 1..21')
        ratios = [contrast(s['foreground'],s['background']) for s in samples]
        # A failing actual sample is sufficient to flag a defect; sparse passing samples are not proof.
        complete = g.get('contrast_region_verified') is True
        if rendered and ratios and min(ratios) < threshold:
            emit('contrast',gid,'fail','At least one supplied composite sample is below threshold',minimum=min(ratios),threshold=threshold)
        elif rendered and ratios and complete:
            emit('contrast',gid,'pass','Caller attests region coverage; script validates only supplied colors',minimum=min(ratios),threshold=threshold)
        else:
            emit('contrast',gid,'unknown','No actual samples or incomplete/unverified region coverage')
    if expected is None:
        emit('measurement_inventory','all','unknown','No expected group inventory; missing groups cannot be detected')
    else:
        emit('measurement_inventory','all','pass' if ids == set(expected) else 'fail','Compare supplied groups with expected inventory',missing=sorted(set(expected)-ids),unexpected=sorted(ids-set(expected)))
    if not groups:
        emit('measurements','all','unknown','No groups measured')
    status = 'fail' if any(c['status']=='fail' for c in checks) else ('unknown' if any(c['status']=='unknown' for c in checks) else 'pass')
    return dict(status=status, asset_version=version, scope='Supplied geometry, capacity, glyph-height limits and composite color samples only; not final poster approval', checks=checks)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurements',type=Path)
    args=parser.parse_args()
    try:
        result=evaluate(json.loads(args.measurements.read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps({'status':'invalid_input','error':str(error)},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return {'pass':0,'fail':1,'unknown':2}[result['status']]


if __name__=='__main__':
    raise SystemExit(main())
