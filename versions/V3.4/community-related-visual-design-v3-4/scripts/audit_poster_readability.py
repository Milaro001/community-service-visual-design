#!/usr/bin/env python3
"""Original pixel audit for layered posters; requires Pillow and NumPy.
Does not do OCR, recover a flattened background, or certify human readability.
"""
import argparse,json,hashlib,math
from pathlib import Path
np = Image = ImageDraw = None

def load_pixel_dependencies():
    global np, Image, ImageDraw
    if np is not None and Image is not None:
        return
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ImportError('Pixel audit requires Pillow and NumPy; use a Python environment with both dependencies.') from exc

def luminance(a):
    load_pixel_dependencies()
    v=np.asarray(a,dtype=np.float64)/255
    v=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
    return v[...,0]*.2126+v[...,1]*.7152+v[...,2]*.0722

def opaque_rgb(path,label):
    load_pixel_dependencies()
    # Alpha is part of the displayed result; dropping it invents a known backdrop.
    # RGBA conversion also exposes palette/colour-key transparency.
    with Image.open(path) as original:
        rgba=original.convert('RGBA')
        if rgba.getchannel('A').getextrema()[0] < 255:
            raise ValueError(f'{label} must be fully opaque; composite on the actual display background before measuring contrast.')
        return rgba.convert('RGB')

def audit(manifest_path,out_dir):
    load_pixel_dependencies()
    manifest_path=Path(manifest_path).resolve();root=manifest_path.parent
    m=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if not isinstance(m,dict) or not isinstance(m.get('groups'),list):raise ValueError('Manifest must contain a groups list')
    ids=[g.get('id') for g in m['groups'] if isinstance(g,dict)]
    if len(ids)!=len(m['groups']) or any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Groups require unique nonempty IDs')
    expected=m.get('expected_group_ids')
    if expected is not None and (not isinstance(expected,list) or not expected or any(not isinstance(i,str) or not i for i in expected) or len(set(expected))!=len(expected)):
        raise ValueError('expected_group_ids must be a nonempty list of unique IDs')
    inventory={'status':'unknown','reason':'No expected group inventory; omitted layers cannot be detected.'} if expected is None else {'status':'pass' if set(ids)==set(expected) else 'fail','missing':sorted(set(expected)-set(ids)),'unexpected':sorted(set(ids)-set(expected))}
    out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    def resolve(p):return (root/p).resolve()
    poster_path=resolve(m['poster']);poster=opaque_rgb(poster_path,'Poster')
    bg_path=resolve(m['background']) if m.get('background') else None
    bg=opaque_rgb(bg_path,'Background') if bg_path else None
    if bg is not None and bg.size!=poster.size:raise ValueError('Background must match the final canvas exactly; do not silently resize during audit.')
    # Reuse full-canvas pixels for all groups instead of copying both images per group.
    poster_pixels=np.asarray(poster) if bg is not None else None
    background_pixels=np.asarray(bg) if bg is not None else None
    findings=[];annotated=poster.copy();draw=ImageDraw.Draw(annotated)
    for g in m['groups']:
        r={'id':g['id'],'kind':g.get('kind','text'),'bbox':g['bbox'],'status':'unknown'}
        x,y,x2,y2=g['bbox'];threshold=g.get('threshold',m.get('threshold',4.5))
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 1<=threshold<=21:raise ValueError('Contrast threshold must be finite within 1..21')
        if any(isinstance(v,bool) or not isinstance(v,int) for v in [x,y,x2,y2]) or not(0<=x<x2<=poster.width and 0<=y<y2<=poster.height):
            r.update(status='fail',reason='Invalid or clipped bounds');findings.append(r);continue
        if bg is None or not g.get('placed_asset'):
            r['reason']='Exact background or registered final-size alpha asset unavailable; local contrast not verifiable.';findings.append(r);continue
        path=resolve(g['placed_asset']);asset=Image.open(path).convert('RGBA')
        if asset.size!=(x2-x,y2-y):raise ValueError(f"{g['id']}: registered asset dimensions differ from bbox")
        asset_pixels=np.asarray(asset)
        rgb=asset_pixels[...,:3].astype(float);alpha=asset_pixels[...,3].astype(float)/255
        fg=poster_pixels[y:y2,x:x2];background=background_pixels[y:y2,x:x2]
        expected=np.rint(rgb*alpha[...,None]+background*(1-alpha[...,None]))
        registered=alpha>.1
        error=float(np.max(np.abs(expected[registered]-fg[registered]))) if registered.any() else None
        # Significant disagreement means the source mask no longer represents this export.
        if error is None or error>3:
            r.update(reason='Current poster pixels do not match registered layer/background; re-export or re-register layers.',composite_max_channel_error=error);findings.append(r);continue
        core=alpha>240/255
        if not core.any():
            r['reason']='No sufficiently opaque core pixels; visual/opacity review required.';findings.append(r);continue
        f=luminance(fg);b=luminance(background)
        c=(np.maximum(f,b)+.05)/(np.minimum(f,b)+.05);values=c[core]
        bad=core&(c<threshold);coords=np.argwhere(core);idx=int(np.argmin(values));wy,wx=coords[idx]
        colored=rgb[core]/255;mx=colored.max(axis=1);mn=colored.min(axis=1);sat=np.divide(mx-mn,mx,out=np.zeros_like(mx),where=mx>0)
        r.update(status='fail' if bad.any() else 'pass',threshold=threshold,core_pixels=int(core.sum()),contrast_min=float(values.min()),contrast_p01=float(np.percentile(values,1)),contrast_median=float(np.median(values)),below_threshold_fraction=float(bad.sum()/core.sum()),worst_pixel=[x+int(wx),y+int(wy)],saturation_median=float(np.median(sat)),brightness_median=float(np.median(mx)),composite_max_channel_error=error,asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if r['status']=='fail':
            draw.rectangle((x,y,x2-1,y2-1),outline='#ff00ff',width=5);draw.ellipse((x+wx-12,y+wy-12,x+wx+12,y+wy+12),outline='#ff00ff',width=5)
        findings.append(r)
    statuses=[r['status'] for r in findings]
    result={'poster':str(poster_path),'poster_sha256':hashlib.sha256(poster_path.read_bytes()).hexdigest(),'canvas_px':list(poster.size),'pixel_contrast_status':'fail' if 'fail' in statuses else 'unknown' if 'unknown' in statuses or not statuses else 'pass','groups':findings,'human_readability_status':'unknown','color_preference_status':'unknown','limits':['Only registered opaque core pixels are measured; antialiasing edges and transparent strokes are excluded.','Saturation and brightness are descriptive measurements, not automatic vividness or readability verdicts.','No OCR, character-integrity, viewing-distance, print, or overall accessibility certification.','Passing contrast never overrides user reports of dark, tiring or hard-to-read lettering.']}
    result['inventory']=inventory
    result['audit_status']='fail' if 'fail' in (result['pixel_contrast_status'],inventory['status']) else 'unknown' if 'unknown' in (result['pixel_contrast_status'],inventory['status']) else 'pass'
    result['limits'].append('Pixel contrast status covers submitted groups only; audit_status also requires a matching expected inventory. Neither is final poster approval.')
    (out_dir/'readability-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    annotated.save(out_dir/'contrast-findings.png')
    preview=poster.copy();preview.thumbnail((1600,900));preview.save(out_dir/'reading-preview.png')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--out-dir',required=True);a=p.parse_args()
    try:
        r=audit(a.manifest,a.out_dir)
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        print(json.dumps({'audit_status':'unknown','pixel_contrast_status':'unknown','error':str(exc)},ensure_ascii=False))
        return 2
    print(json.dumps({'audit_status':r['audit_status'],'pixel_contrast_status':r['pixel_contrast_status'],'inventory_status':r['inventory']['status'],'groups':len(r['groups']),'failed_groups':[g['id'] for g in r['groups'] if g['status']=='fail'],'unverified_groups':[g['id'] for g in r['groups'] if g['status']=='unknown']},ensure_ascii=False))
    return {'pass':0,'fail':1,'unknown':2}[r['audit_status']]
if __name__=='__main__':raise SystemExit(main())
