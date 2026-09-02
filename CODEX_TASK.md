# Codex task — verify TIMED COLORS Step 3, then implement Prototype 01

Work in this folder. I use the VS Code extension `jakearl.shader-toy-web`.
Our repaired Hyper3D blazer has already been baked to a 128³ signed distance
volume. The immediate task is to run the supplied ray-marched blazer shader
inside this extension and verify front/back/side views.

## Inputs and constraints

- Read README.md, TC_Blazer_SDF.glsl, blazer_sdf_128.json and checks.json first.
- `blazer_sdf_128_atlas.png` is the actual distance data; use it as iChannel0.
- `blazer_sdf_128.f32` is the float32 reference, not an image texture.
- Preserve the canonical geometry, atlas bytes, axis convention and bounds.
- Do not regenerate Hyper3D assets, rebake, decimate or smooth geometry for a
  shader integration error. Do not substitute an analytic blazer-shaped proxy.
- Keep this milestone in the existing extension. Use supported syntax from the
  installed version; inspect its package/source if documented behavior differs.
- Maintain a mainImage entry point and local relative texture paths.
- Keep the data texture unconverted, nearest-filtered and sampled at texel centers.
  Decode RG16 first, then interpolate distances. Preserve automatic Y calibration.
- Keep ray queries within the volume AABB. The clamped sampler is not a valid
  exterior distance function for arbitrary points beyond the volume bounds.

## Immediate work: live verification

1. Open TC_Blazer_SDF.glsl using Shader Toy: Show GLSL Preview in this workspace.
   If you cannot operate the VS Code UI, say so and give me the exact command to
   run. Continue all file-level checks and fixes you can perform locally.
2. Resolve actual compile or texture-loading errors. Record the extension version,
   available WebGL version and GPU if accessible. Do not assume a sampler3D input
   path exists; this package intentionally uses a 2D atlas.
3. Check debugMode=1: atlas visible, green strip, no red checkerboard. If it fails,
   diagnose path, image loading, color conversion, filters and precision. Keep
   the byte check; do not simply bypass it.
4. At debugMode=0 and autoRotate=0, capture front 0°, side 90°, back 180° and side
   270°. Compare with CPU_Reference.png. Check lapels, arm separation, cuffs and
   hem. Record magenta capped rays, clipping or changed orientation.
5. Test autoRotate=1, then turn it off for reproducible screenshots. Measure frame
   time or FPS and state preview resolution. Do not invent performance results.
6. Make a brief validation note with changes, errors fixed, screenshots and any
   remaining limitations. Preserve the working Step 3 shader as the baseline.

## Continue after the live baseline works

Create a separate `TC_Indoor_Y10.glsl` using the verified renderer:

1. Add a minimal Indoor world: floor, restrained ambient/key lighting and optional
   fog. Keep one camera convention and depth comparison between garment and world.
   Trace the bounded blazer separately and compare its hit distance with world
   hits, or implement a mathematically sound bound before unifying scene queries.
   Do not call the clamped blazer sampler outside its volume and treat the result
   as an unbounded scene SDF.
2. Separate world appearance from accumulated garment appearance. Add controls for
   effectIntensity, yearIntensity, effectScale and irregularity. Initially use
   object-space procedural color on the blazer only; leave its SDF unchanged.
3. Use deterministic patterns for the same configuration. Keep animation time
   separate from simulated garment age. A Year 10 preset must not animate aging
   with iTime. Label all provisional effect values as uncalibrated.
4. Set effect intensity to zero and verify restoration of the clean baseline.
   Front/back/turntable views must render the same canonical asset.
5. Leave exact lapel/collar/cuff zoning as a separate attribute-map task. SDF data
   alone does not contain original UVs or semantic zones. Any provisional geometric
   mask must be labeled approximate; do not claim property-sheet zone compliance.

Do not implement all eight environments or the 28 combinations yet. Do not
automatically upgrade to 256³ before identifying a specific 128³ quality failure.
Deliver the verified Step 3 baseline first, then the separate Indoor/Year 10 trial
and a concise run/test report. If live UI verification is blocked, stop advancement
at that gate and tell me the exact action or error output needed from my machine.
