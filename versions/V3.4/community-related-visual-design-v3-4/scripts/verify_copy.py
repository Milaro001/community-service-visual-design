#!/usr/bin/env python3
"""Compare text snapshots, not pixels. Usage: verify_copy.py MASTER.json ACTUAL.json.
Both files are JSON lists of {id, language, text}. Actual text must come from
real text objects/exports; whitespace and punctuation are not normalized.
Layout wrapping belongs in a separate record, not in these text values.
"""
import argparse, json, re, sys
from pathlib import Path

def read(path):
    rows=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(rows,list): raise ValueError('Expected a JSON list')
    out={}
    for row in rows:
        if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k] for k in ('id','language','text')):
            raise ValueError('Each item needs nonempty string id, language, text')
        key=(row['language'],row['id'])
        if key in out: raise ValueError('Duplicate item: '+str(key))
        out[key]=row['text']
    if not out: raise ValueError('Empty text snapshot')
    return out

def compare(master,actual):
    issues=[]
    for key in sorted(master.keys()-actual.keys()): issues.append({'item':key,'error':'missing'})
    for key in sorted(actual.keys()-master.keys()): issues.append({'item':key,'error':'unexpected'})
    for key in sorted(master.keys() & actual.keys()):
        if master[key]!=actual[key]: issues.append({'item':key,'error':'text_changed','expected':master[key],'actual':actual[key]})
    for key,txt in actual.items():
        if re.search(r'\{\{[^{}]*\}\}',txt): issues.append({'item':key,'error':'unresolved_placeholder'})
    return issues

def review_hints(actual):
    # These words can be legitimate copy (for example a named status list).
    # Field provenance and unresolved facts remain a separate master-copy review.
    return [{'item':key,'hint':'possible_placeholder_language','text':txt}
            for key,txt in actual.items() if re.search(r'待确认|待填写|待补充',txt)]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('actual');a=p.parse_args()
    try:
        actual=read(a.actual);issues=compare(read(a.master),actual)
    except (ValueError,OSError,TypeError) as e:
        print(json.dumps({'status':'invalid_input','error':str(e)},ensure_ascii=False));return 2
    print(json.dumps({'status':'pass' if not issues else 'fail','issues':issues,'review_hints':review_hints(actual),'scope':'text snapshots only; no pixel, truth, layout, licensing or approval verification'},ensure_ascii=False,indent=2))
    return 1 if issues else 0
if __name__=='__main__':sys.exit(main())
