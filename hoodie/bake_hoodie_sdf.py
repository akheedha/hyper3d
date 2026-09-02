"""
Bake 128^3 Signed Distance Field volume and 2048x1024 RGBA8 PNG atlas from Hoodie.glb.
"""
import struct
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

root = Path(__file__).resolve().parent
glb_path = root / 'Hoodie.glb'

print(f"Reading {glb_path}...")
with open(glb_path, 'rb') as f:
    f.read(12)
    c_len, _ = struct.unpack('<I4s', f.read(8))
    gltf = json.loads(f.read(c_len).decode('utf-8'))
    b_len, _ = struct.unpack('<I4s', f.read(8))
    bin_data = f.read(b_len)

def get_accessor(acc_id):
    acc = gltf['accessors'][acc_id]
    bv = gltf['bufferViews'][acc['bufferView']]
    offset = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    count = acc['count']
    ctype = acc['componentType']
    atype = acc['type']
    dt = {5126: np.float32, 5123: np.uint16, 5125: np.uint32}[ctype]
    nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[atype]
    arr = np.frombuffer(bin_data, dtype=dt, count=count * nc, offset=offset)
    return arr.reshape((count, nc)) if nc > 1 else arr

prim = gltf['meshes'][0]['primitives'][0]
vertices = get_accessor(prim['attributes']['POSITION']).astype(np.float64)
indices = get_accessor(prim['indices']).astype(np.int32)
triangles = vertices[indices].reshape(-1, 3, 3)

v0 = triangles[:, 0]
v1 = triangles[:, 1]
v2 = triangles[:, 2]
cross = np.cross(v1 - v0, v2 - v0)
area = 0.5 * np.linalg.norm(cross, axis=1)
face_normals = cross / np.maximum(2.0 * area[:, None], 1e-12)

print(f"Mesh loaded: {len(vertices)} vertices, {len(triangles)} triangles.")

# Angle-weighted vertex pseudonormals
vert_normals = np.zeros_like(vertices)
for i in range(len(triangles)):
    t = triangles[i]
    fn = face_normals[i]
    e0 = t[1] - t[0]; e0 /= np.maximum(np.linalg.norm(e0), 1e-12)
    e1 = t[2] - t[1]; e1 /= np.maximum(np.linalg.norm(e1), 1e-12)
    e2 = t[0] - t[2]; e2 /= np.maximum(np.linalg.norm(e2), 1e-12)
    a0 = np.arccos(np.clip(-np.dot(e2, e0), -1.0, 1.0))
    a1 = np.arccos(np.clip(-np.dot(e0, e1), -1.0, 1.0))
    a2 = np.arccos(np.clip(-np.dot(e1, e2), -1.0, 1.0))
    idx = indices.reshape(-1, 3)[i]
    vert_normals[idx[0]] += a0 * fn
    vert_normals[idx[1]] += a1 * fn
    vert_normals[idx[2]] += a2 * fn

vn_len = np.linalg.norm(vert_normals, axis=1, keepdims=True)
vert_normals = np.where(vn_len > 1e-12, vert_normals / np.maximum(vn_len, 1e-12), 0.0)

# Grid parameters
h = 0.016000420153141022
center = np.array([0.0022405, 0.9463835, 0.00109351])
bbox_min = center - 64 * h
bbox_max = center + 64 * h

print(f"Bounding Box Min: {bbox_min}")
print(f"Bounding Box Max: {bbox_max}")
print(f"Voxel Size h: {h}")

# Build uniform spatial grid for fast candidate triangle query
grid_res = 32
cell_size = (bbox_max - bbox_min) / grid_res
tri_min = np.min(triangles, axis=1)
tri_max = np.max(triangles, axis=1)

cell_triangles = [[] for _ in range(grid_res**3)]
for t_idx in range(len(triangles)):
    c_min = np.clip(np.floor((tri_min[t_idx] - bbox_min) / cell_size).astype(int), 0, grid_res - 1)
    c_max = np.clip(np.floor((tri_max[t_idx] - bbox_min) / cell_size).astype(int), 0, grid_res - 1)
    for cx in range(c_min[0], c_max[0] + 1):
        for cy in range(c_min[1], c_max[1] + 1):
            for cz in range(c_min[2], c_max[2] + 1):
                cell_triangles[cx * grid_res**2 + cy * grid_res + cz].append(t_idx)

# Surface sampling for points far from surface
rng = np.random.default_rng(713)
N_samples = 250000
prob = area / area.sum()
tri_choices = rng.choice(len(triangles), size=N_samples, p=prob)
u = rng.uniform(0, 1, size=(N_samples, 1))
v = rng.uniform(0, 1, size=(N_samples, 1))
flip = (u + v) > 1
u[flip] = 1 - u[flip]
v[flip] = 1 - v[flip]
w = 1 - u - v
sample_points = u * v0[tri_choices] + v * v1[tri_choices] + w * v2[tri_choices]
sample_normals = (u * vert_normals[indices.reshape(-1,3)[tri_choices, 0]] +
                  v * vert_normals[indices.reshape(-1,3)[tri_choices, 1]] +
                  w * vert_normals[indices.reshape(-1,3)[tri_choices, 2]])
sample_tree = cKDTree(sample_points)

def point_to_triangles_exact(P, cand_tris, cand_face_normals, cand_vert_normals):
    # P: (N, 3), cand_tris: (K, 3, 3)
    A = cand_tris[:, 0][None, :, :] # (1, K, 3)
    B = cand_tris[:, 1][None, :, :]
    C = cand_tris[:, 2][None, :, :]
    P_exp = P[:, None, :] # (N, 1, 3)
    
    ab = B - A
    ac = C - A
    ap = P_exp - A
    
    d1 = np.sum(ab * ap, axis=-1)
    d2 = np.sum(ac * ap, axis=-1)
    
    cond_a = (d1 <= 0.0) & (d2 <= 0.0)
    
    bp = P_exp - B
    d3 = np.sum(ab * bp, axis=-1)
    d4 = np.sum(ac * bp, axis=-1)
    cond_b = (d3 >= 0.0) & (d4 <= d3)
    
    vc = d1 * d4 - d3 * d2
    cond_ab = (vc <= 0.0) & (d1 >= 0.0) & (d3 <= 0.0)
    v_ab = d1 / np.maximum(d1 - d3, 1e-12)
    
    cp = P_exp - C
    d5 = np.sum(ab * cp, axis=-1)
    d6 = np.sum(ac * cp, axis=-1)
    cond_c = (d6 >= 0.0) & (d5 <= d6)
    
    vb = d5 * d2 - d1 * d6
    cond_ac = (vb <= 0.0) & (d2 >= 0.0) & (d6 <= 0.0)
    w_ac = d2 / np.maximum(d2 - d6, 1e-12)
    
    va = d3 * d6 - d5 * d4
    cond_bc = (va <= 0.0) & ((d4 - d3) >= 0.0) & ((d5 - d6) >= 0.0)
    w_bc = (d4 - d3) / np.maximum((d4 - d3) + (d5 - d6), 1e-12)
    
    denom = 1.0 / np.maximum(va + vb + vc, 1e-12)
    v_face = vb * denom
    w_face = vc * denom
    
    Q = np.where(cond_a[..., None], A,
        np.where(cond_b[..., None], B,
        np.where(cond_ab[..., None], A + v_ab[..., None] * ab,
        np.where(cond_c[..., None], C,
        np.where(cond_ac[..., None], A + w_ac[..., None] * ac,
        np.where(cond_bc[..., None], B + w_bc[..., None] * (C - B),
        A + v_face[..., None] * ab + w_face[..., None] * ac))))))
    
    diff = P_exp - Q
    dists = np.linalg.norm(diff, axis=-1)
    best_k = np.argmin(dists, axis=-1)
    
    N_idx = np.arange(len(P))
    best_dist = dists[N_idx, best_k]
    best_Q = Q[N_idx, best_k, :]
    best_tri_idx = best_k
    
    # Normal at projection point
    # Use face normal if inside face, or vertex normal if at vertex
    best_fn = cand_face_normals[best_tri_idx]
    cond_face = ~(cond_a[:, best_tri_idx] | cond_b[:, best_tri_idx] | cond_c[:, best_tri_idx] |
                  cond_ab[:, best_tri_idx] | cond_ac[:, best_tri_idx] | cond_bc[:, best_tri_idx])
    
    sign_dot = np.sum((P - best_Q) * best_fn, axis=-1)
    sign = np.where(sign_dot < 0, -1.0, 1.0)
    return best_dist * sign

print("Computing 128^3 Signed Distance Field volume...")
t0 = time.time()
sdf_volume = np.zeros((128, 128, 128), dtype=np.float32)

# Generate grid coordinates: z fastest/slowest convention
# Note: binary order: index = x + 128 * (y + 128 * z)
# Array shape in memory: (128, 128, 128) as (z, y, x)
xs = bbox_min[0] + (np.arange(128) + 0.5) * h
ys = bbox_min[1] + (np.arange(128) + 0.5) * h
zs = bbox_min[2] + (np.arange(128) + 0.5) * h

# Process in spatial blocks of 4x4x4 (64 points per block)
block_size = 4
num_blocks = 128 // block_size # 32

for bz in range(num_blocks):
    z_slice = slice(bz * block_size, (bz + 1) * block_size)
    z_vals = zs[z_slice]
    for by in range(num_blocks):
        y_slice = slice(by * block_size, (by + 1) * block_size)
        y_vals = ys[y_slice]
        for bx in range(num_blocks):
            x_slice = slice(bx * block_size, (bx + 1) * block_size)
            x_vals = xs[x_slice]
            
            # Grid points in this block
            ZZ, YY, XX = np.meshgrid(z_vals, y_vals, x_vals, indexing='ij')
            block_pts = np.stack([XX.ravel(), YY.ravel(), ZZ.ravel()], axis=-1)
            
            # Find candidate triangles from current cell and 1-ring neighbors
            cand_set = set()
            for dx in [-1, 0, 1]:
                cx = bx + dx
                if cx < 0 or cx >= grid_res: continue
                for dy in [-1, 0, 1]:
                    cy = by + dy
                    if cy < 0 or cy >= grid_res: continue
                    for dz in [-1, 0, 1]:
                        cz = bz + dz
                        if cz < 0 or cz >= grid_res: continue
                        cell_idx = cx * grid_res**2 + cy * grid_res + cz
                        cand_set.update(cell_triangles[cell_idx])
            
            if len(cand_set) > 0:
                cand_tris_idx = np.array(list(cand_set))
                cand_tris = triangles[cand_tris_idx]
                cand_fn = face_normals[cand_tris_idx]
                cand_vn = vert_normals[indices.reshape(-1, 3)[cand_tris_idx]]
                block_dists = point_to_triangles_exact(block_pts, cand_tris, cand_fn, cand_vn)
                # Any point with distance > 0.03 is outside the fabric shell in the air
                block_dists = np.where(np.abs(block_dists) > 0.03, np.abs(block_dists), block_dists)
            else:
                # Far from local triangles: strictly positive distance in the air
                d_approx, _ = sample_tree.query(block_pts, k=1)
                block_dists = d_approx
            
            sdf_volume[z_slice, y_slice, x_slice] = block_dists.reshape(block_size, block_size, block_size).astype(np.float32)

print(f"Volume computed in {time.time() - t0:.2f}s.")
print(f"Min distance: {sdf_volume.min():.6f}, Max distance: {sdf_volume.max():.6f}")
print(f"Negative voxels: {(sdf_volume < 0).sum()} ({(sdf_volume < 0).mean()*100:.2f}%)")

# Determine distance range
max_abs_dist = float(np.abs(sdf_volume).max())
# Round up slightly with clean decimal
distance_range = float(np.ceil(max_abs_dist * 100) / 100.0)
if distance_range <= max_abs_dist:
    distance_range = max_abs_dist * 1.01
print(f"Distance range: {distance_range:.6f}")

# Save float32 binary volume: order is index = x + 128 * (y + 128 * z)
# In numpy array shape (128, 128, 128) as (z, y, x), C-contiguous flatten matches exactly:
f32_data = sdf_volume.astype('<f4').tobytes()
f32_path = root / 'hoodie_sdf_128.f32'
f32_path.write_bytes(f32_data)
print(f"Saved {f32_path} ({len(f32_data)} bytes)")

# Encode RGBA8 Atlas: 2048 x 1024
# 16 columns x 8 rows of 128x128 tiles
# Tile index = z (0..127): tile_col = z % 16, tile_row = z // 16
# Within tile: image column = x, image row = y (top row = y = 0)
atlas = np.zeros((1024, 2048, 4), dtype=np.uint8)
atlas[:, :, 3] = 255 # Alpha = 255

for z in range(128):
    tile_col = z % 16
    tile_row = z // 16
    py0 = tile_row * 128
    px0 = tile_col * 128
    
    slice_z = sdf_volume[z, :, :] # shape (128, 128) as (y, x)
    # Quantize to 16-bit integer q in [0..65535]
    norm_d = np.clip((slice_z / distance_range + 1.0) / 2.0, 0.0, 1.0)
    q = np.rint(norm_d * 65535.0).astype(np.uint32)
    r = (q // 256).astype(np.uint8)
    g = (q % 256).astype(np.uint8)
    
    atlas[py0:py0+128, px0:px0+128, 0] = r
    atlas[py0:py0+128, px0:px0+128, 1] = g
    atlas[py0:py0+128, px0:px0+128, 2] = 0

atlas_img = Image.fromarray(atlas, 'RGBA')
atlas_path = root / 'hoodie_sdf_128_atlas.png'
atlas_img.save(atlas_path, format='PNG')
print(f"Saved {atlas_path} ({atlas_path.stat().st_size} bytes)")

# Verify atlas roundtrip error against float32 volume
im_read = np.asarray(Image.open(atlas_path).convert('RGBA'))
q_read = im_read[:, :, 0].astype(np.float64) * 256 + im_read[:, :, 1]
decoded = (q_read / 65535.0 * 2.0 - 1.0) * distance_range
volume_decoded = np.stack([decoded[(z//16)*128:(z//16+1)*128, (z%16)*128:(z%16+1)*128] for z in range(128)])
roundtrip_error = float(np.abs(volume_decoded - sdf_volume).max())
print(f"Max roundtrip error: {roundtrip_error:.8f}")

# Select 3 probe pixels for orientation and integrity calibration
probes = [
    (37, 61),
    (1021, 387),
    (1703, 911)
]
probe_info = []
for px, py in probes:
    r_val = int(atlas[py, px, 0])
    g_val = int(atlas[py, px, 1])
    probe_info.append({"x": px, "y": py, "r": r_val, "g": g_val})
    print(f"Probe pixel ({px}, {py}): R={r_val}, G={g_val}")

# Generate hoodie_sdf_128.json
meta = {
    "schema": "timed-colors.sdf-volume",
    "version": 1,
    "source_file": "Hoodie.glb",
    "resolution": [128, 128, 128],
    "bounding_box_min": [float(bbox_min[0]), float(bbox_min[1]), float(bbox_min[2])],
    "bounding_box_max": [float(bbox_max[0]), float(bbox_max[1]), float(bbox_max[2])],
    "voxel_size": float(h),
    "sample_location": "cell centers",
    "coordinate_system": "Original repaired GLB local coordinates; +Y up, +Z front",
    "distance_units": "original model units; no physical size calibration",
    "sign": "negative inside; positive outside",
    "array_shape_zyx": [128, 128, 128],
    "binary_file": "hoodie_sdf_128.f32",
    "binary_type": "IEEE 754 float32 little-endian",
    "binary_order": "x fastest, then y, then z; index=x+128*(y+128*z)",
    "sample_position": "bbox_min + (vec3(x,y,z)+0.5)*voxel_size",
    "source_triangle_count": len(triangles),
    "probes": probe_info,
    "atlas": {
        "file": "hoodie_sdf_128_atlas.png",
        "pixel_size": [2048, 1024],
        "slice_columns": 16,
        "slice_rows": 8,
        "tile_size": [128, 128],
        "slice_order": "z increases left-to-right, then top-to-bottom",
        "within_tile": "image column=x; image row=y; top row=y=0",
        "channels": "R=high byte, G=low byte, B=0, A=255",
        "decode": f"q=round(R*255)*256+round(G*255); distance=(q/65535*2-1)*{distance_range}",
        "distance_range": distance_range,
        "maximum_roundtrip_error": roundtrip_error,
        "texture_settings": "Linear data, no sRGB conversion; no Y flip; no mipmaps. GLSL texelFetch with manual trilinear interpolation."
    }
}

json_path = root / 'hoodie_sdf_128.json'
json_path.write_text(json.dumps(meta, indent=2) + '\n')
print(f"Saved {json_path}")
