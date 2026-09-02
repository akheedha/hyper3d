"""Developer-only CPU checks; does not compile GLSL or run VS Code/WebGL."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates

root = Path(__file__).resolve().parent
meta = json.loads((root / 'blazer_sdf_128.json').read_text())
im = np.asarray(Image.open(root / 'blazer_sdf_128_atlas.png').convert('RGBA'))
assert im.shape == (1024, 2048, 4)
assert (im[:, :, 2] == 0).all() and (im[:, :, 3] == 255).all()
q = im[:, :, 0].astype(np.float64) * 256 + im[:, :, 1]
atlas_distance = (q / 65535 * 2 - 1) * meta['atlas']['distance_range']
volume = np.stack([atlas_distance[(z//16)*128:(z//16+1)*128,
                                  (z%16)*128:(z%16+1)*128] for z in range(128)])
reference = np.fromfile(root / 'blazer_sdf_128.f32', dtype='<f4').reshape(128,128,128)
roundtrip_error = float(np.abs(volume - reference).max())
assert roundtrip_error < 0.000018
probes = [(37,61,208,127), (1021,387,165,104), (1703,911,204,210)]

def probe_error(upload, flip):
    return sum(abs(upload[1023-y if flip else y, x, :2].astype(float)
                   - [r,g]).sum() for x,y,r,g in probes)

assert probe_error(im, False) == 0 and probe_error(im, True) > 1
assert probe_error(im[::-1], True) == 0 and probe_error(im[::-1], False) > 1
# A representative accidental sRGB-to-linear transfer must fail calibration.
rgb = im.astype(float) / 255
converted = np.rint(np.where(rgb <= .04045, rgb / 12.92,
                            ((rgb + .055) / 1.055)**2.4) * 255)
assert min(probe_error(converted, False), probe_error(converted, True)) > 1
lo = np.array(meta['bounding_box_min']); hi = np.array(meta['bounding_box_max'])
h = meta['voxel_size']; center = (lo + hi) / 2

def sample(p):
    g = (p - lo) / h - .5
    return map_coordinates(volume, g[:,[2,1,0]].T, order=1, mode='nearest', prefilter=False)

def manual(p):
    g = np.clip((p-lo)/h-.5, 0,127); a=np.floor(g).astype(int); f=g-a
    result = np.zeros(len(p))
    for z in range(2):
        for y in range(2):
            for x in range(2):
                index = np.minimum(a + [x,y,z],127)
                px = (index[:,2]%16)*128+index[:,0]
                py = (index[:,2]//16)*128+index[:,1]
                weight=np.prod(np.where(np.array([x,y,z]),f,1-f),axis=1)
                result += atlas_distance[py,px]*weight
    return result

rng = np.random.default_rng(713)
points = rng.uniform(lo-.02, hi+.02, (2000,3))
interpolation_error = float(np.abs(sample(points)-manual(points)).max())
assert interpolation_error < 1e-12

W,H=240,310
def render(angle):
    angle = np.deg2rad(angle)
    right = np.array([np.cos(angle),0,-np.sin(angle)])
    up = np.array([0.,1.,0.]); rd = np.array([-np.sin(angle),0,-np.cos(angle)])
    yy,xx = np.mgrid[0:H,0:W]
    fit=min(H,W/.78)
    x=(xx+.5-W/2).ravel()/fit*2.3
    y=(H-yy-.5-H/2).ravel()/fit*2.3
    ro=center+x[:,None]*right+y[:,None]*up-3*rd
    safe=np.where(rd>=0,1,-1)*np.maximum(np.abs(rd),1e-8)
    ta=(lo-ro)/safe;tb=(hi-ro)/safe
    near=np.maximum(0,np.minimum(ta,tb).max(axis=1));far=np.maximum(ta,tb).min(axis=1)
    active=np.flatnonzero(far>=near);t=near+1e-6;previous=near.copy()
    hits=np.zeros(len(ro),bool);max_steps=768
    for iteration in range(max_steps):
        active=active[t[active]<=far[active]]
        if not len(active):break
        d=sample(ro[active]+rd*t[active,None]);done=d<=h*.004
        just=active[done];hits[just]=True
        crossed=just[d[done]<0]
        left=previous[crossed].copy();rr=t[crossed].copy()
        for _ in range(10):
            mid=(left+rr)*.5
            inside=sample(ro[crossed]+rd*mid[:,None])<0
            rr=np.where(inside,mid,rr);left=np.where(inside,left,mid)
        t[crossed]=(left+rr)*.5
        remaining=active[~done];previous[remaining]=t[remaining]
        t[remaining]+=np.maximum(.65*d[~done],h*.025)
        active=remaining
    capped=active[t[active]<=far[active]]
    p=ro[hits]+rd*t[hits,None];n=[]
    for axis in range(3):
        off=np.zeros(3);off[axis]=h*.35
        n.append(sample(p+off)-sample(p-off))
    n=np.stack(n,axis=1);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-8)
    key=-.4*right+.6*up-rd;key/=np.linalg.norm(key)
    fill=.7*right+.1*up+.7*rd;fill/=np.linalg.norm(fill)
    light=.28+.62*np.maximum(n@key,0)+.10*np.maximum(n@fill,0)
    col=np.full((len(ro),3),.9);col[hits]=.88*light[:,None];col[capped]=[1,0,1]
    stats={'angle_degrees':float(np.rad2deg(angle)), 'hit_pixels':int(hits.sum()),
           'capped_rays':len(capped), 'loop_iterations':iteration+1}
    assert len(capped)==0 and hits.sum()>1000,stats
    return Image.fromarray(np.uint8(np.clip(col.reshape(H,W,3),0,1)*255)),stats

out=Image.new('RGB',(W*4,H+60),(245,245,245));draw=ImageDraw.Draw(out)
draw.text((10,8),'CPU REFERENCE ONLY | 128-cubed atlas | live VS Code test pending', fill=(20,35,40))
views=[]
for i,(angle,label) in enumerate([(0,'FRONT'),(90,'SIDE'),(180,'BACK'),(270,'OTHER SIDE')]):
    preview,stats=render(angle);out.paste(preview,(i*W,50));views.append(stats)
    draw.text((i*W+10,32),label,fill=(20,35,40));print(stats,flush=True)
out.save(root/'CPU_Reference.png')
results={'atlas_dimensions':[2048,1024], 'compared_voxels':128**3,
         'max_distance_roundtrip_error':roundtrip_error,
         'orientation_checks':'pass: original and Y-flipped uploads',
         'simulated_srgb_conversion':'correctly rejected',
         'manual_trilinear_points':len(points),
         'max_manual_vs_reference_interpolation_error':interpolation_error,
         'cpu_render_dimensions_per_view':[W,H], 'views':views,
         'gpu_compilation_tested':False, 'vscode_extension_tested':False,
         'limitations':'CPU numerical checks only; live GPU/extension verification remains required.'}
(root/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
