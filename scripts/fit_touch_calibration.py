"""Fit provisional axis mapping from manually verified video samples. No device I/O."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'evidence/calibration-video'
record=json.loads((folder/'observation.json').read_text())
samples=record['samples']

def fit(raw_axis, screen_axis):
    pairs=[(int(s['raw_hex'][raw_axis],16),s['xy'][screen_axis]) for s in samples]
    mean_raw=sum(v for v,_ in pairs)/len(pairs)
    mean_screen=sum(v for _,v in pairs)/len(pairs)
    slope=sum((r-mean_raw)*(s-mean_screen) for r,s in pairs)/sum((r-mean_raw)**2 for r,_ in pairs)
    offset=mean_screen-slope*mean_raw
    residuals=[slope*r+offset-s for r,s in pairs]
    return {'raw_axis':raw_axis,'scale':slope,'offset':offset,
            'max_fit_residual_pixels':max(map(abs,residuals)),
            'rms_fit_residual_pixels':(sum(e*e for e in residuals)/len(residuals))**0.5}

result={'status':'PROVISIONAL; video target positions are nominal, no independent accuracy validation',
        'x':fit(1,0),'y':fit(0,1),'samples':len(samples),
        'do_not_infer':'Fit residuals are not touchscreen accuracy measurements or error bounds.',
        'next_validation':'Current calibration program: center hold then horizontal/vertical center drags; confirm readable raw values and sample dropout behavior.'}
(folder/'provisional-fit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
