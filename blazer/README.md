# TIMED COLORS — Step 3: render the baked blazer in VS Code

This folder contains a complete mainImage shader and the actual atlas from your
128³ trial SDF bake. It ray-marches your blazer volume. No GLB loader or new mesh
conversion is needed for this step.

## Run

1. Extract the ZIP. In VS Code, choose **File → Open Folder** and open the extracted
   `TC_Blazer_SDF_Step3` folder containing this README and the shader.
2. Keep `TC_Blazer_SDF.glsl` and `blazer_sdf_128_atlas.png` in the same folder.
3. Open `TC_Blazer_SDF.glsl`. This is the complete code to use; do not paste the old
   sampling-helper file by itself, because that file has no camera or mainImage.
4. With `jakearl.shader-toy-web` installed, run **Shader Toy: Show GLSL Preview**
   from the Command Palette. **Show Static GLSL Preview** also works and keeps
   the preview attached when you open another editor.
5. Start with a small preview pane, approximately 500 × 650 pixels. The initial
   view is stationary and front-facing. Compilation can take a moment.
6. Use the extension's custom-uniform controls. If those controls are not visible,
   edit the defaults in the `#iUniform` lines at the top of the shader and save.

| Control | Values / purpose |
|---|---|
| viewAngle | 0 front; 90 side; 180 back; 270 other side |
| autoRotate | 0 stationary; 1 turntable |
| rotationSpeed | Degrees per second; default 12 |
| zoom | Default 1; reduce if cropped |
| debugMode | 0 blazer; 1 raw atlas and green validation strip; 2 distance slice |
| sliceZ | 0–127; used only in distance-slice mode |

The first expected result is a light gray/white blazer with simple directional
shading on a plain gray background. The 128³ grid can leave rough details and
normal ripples. This is an integration trial, not a final product render.

## Texture contract

- PNG is numerical data, not a diffuse/color map. Do not use `shaded.png` or
  `texture_diffuse.png` in its place.
- 2048 × 1024 RGBA8, 16 × 8 tiles, each tile 128 × 128. Tiles are ordered by Z.
- R is the high byte and G the low byte of an unsigned 16-bit value.
- Decode `distance = ((Rbyte*256 + Gbyte)/65535*2 - 1)*1.159999966621`.
- The shader fetches texel centers with nearest filtering and interpolates decoded
  distances manually. Do not enable sRGB conversion or mipmap minification.
- It detects the uploaded image's vertical orientation using three known byte
  pairs; either upload flip convention works. This is specific to the supplied PNG.
- Bounds, cell-center convention and units are in `blazer_sdf_128.json`.
- The original repaired model uses +Y up and +Z front. Physical size is uncalibrated.

## Troubleshooting

**Red checkerboard:** image loading or byte validation failed. Confirm the folder
is open, the relative path is correct and the exact PNG is present. Wait for loading,
then reopen the preview. Check extension error messages. The shader already handles
vertical flipping; do not flip or re-save the PNG to compensate. If the extension
color-converts data textures, Codex must inspect its actual texture setup and disable
conversion using supported mechanisms. Do not weaken the byte check to hide corruption.

**Magenta pixels:** rays reached the 768-step limit. Reduce the preview size for
performance; this alone does not fix capped rays. Codex should inspect those rays
and, if justified, increase the cap to 1000. Do not enlarge the hit threshold enough
to fill the blazer's openings or hide misses.

**GLSL error:** copy the complete error text and line to Codex. The custom `#iChannel`
and `#iUniform` lines are extension directives, not standard GLSL. They must be
preprocessed by the extension. Do not duplicate injected uniforms or add a #version.

**Slow preview:** turn autoRotate off, reduce the pane size, and keep only one
preview open. This shader can sample eight texels per distance query and perform
hundreds of queries per pixel. Actual speed depends on the GPU and extension.

## Validation and scope

`check_atlas.py` independently checks the atlas against the supplied float32 volume,
tests orientation calibration, and makes four CPU reference renders using the
same sampling/camera/marching rules. It requires Python, NumPy, SciPy and Pillow;
these are only for developer verification, not for running the VS Code preview.
See `checks.json` for the measured results and `CPU_Reference.png` for the reference.

The extension documentation was checked for relative input paths, mainImage and
custom uniforms. This package has not been run inside your VS Code installation;
the live GPU/extension check is the first task in `CODEX_TASK.md`. CPU renders do
not prove GPU compilation, extension loading or real-time performance.

This milestone implements distance-volume rendering and camera controls only.
Original UVs, PBR textures and garment zones are not transferred by an SDF bake.
After the live front/back/side check passes, add a simple Indoor world and then
the Indoor/Year 10 garment-effect controls. Their initial values are artistic
prototypes until calibrated against the approved TIMED COLORS property sheet.

Official extension documentation:
https://marketplace.visualstudio.com/items?itemName=jakearl.shader-toy-web
