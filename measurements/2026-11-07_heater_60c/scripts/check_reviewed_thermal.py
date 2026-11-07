"""Offline estimates for individually viewed, menu-free original frames.

Do not use this script to silently repair the live journal. The menu heuristic
was a false positive in these explicitly inspected frames. Original records,
including missing live measurements, remain unchanged.
"""
import json
from pathlib import Path
import sys
RUN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RUN.parents[1]/'apps/thermal_monitor'))
import cv2
from vendor.uti260b.decoder import Decoder
from orientation import rotate_thermal

reviewed=[
    'photos/thermal_raw_diagnostic_0247.png',
    'photos/raw_thermal_hold/20261107_025048.png',
    'photos/raw_thermal_hold/20261107_025349.png',
    'photos/raw_thermal_hold/20261107_025850.png',
]
results=[]
for relative in reviewed:
    image=cv2.imread(str(RUN/relative))
    decoder=Decoder();decoder.hold_seconds=decoder.menu_hold_seconds=0
    f=decoder.decode(cv2.rotate(image,cv2.ROTATE_90_COUNTERCLOCKWISE))
    assert f.layout=='screen' and f.range_source=='osd' and f.has_scale
    f=rotate_thermal(f,90)
    values={}
    for label,x,y in [('A',.84,.65),('B',.86,.70)]:
        px,py=round(x*(f.shape[1]-1)),round(y*(f.shape[0]-1))
        values[label]=dict(pixel=[px,py],temperature=f.temp_at(px,py,1))
    results.append(dict(image=relative,visually_reviewed_menu_absent=True,
        decoder_menu_heuristic=f.menu_open,scale_source=f.range_source,
        scale_min=f.t_min,scale_max=f.t_max,center_display=f.center_temp,
        approximate=True,method='Existing palette decoder applied offline; unchanged masks and fresh OSD range; separately reported, never imputed into live data',points=values))
(RUN/'derived').mkdir(exist_ok=True)
(RUN/'derived/reviewed_thermal_estimates.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for r in results:print(r['image'],r['points'])
