import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = __dirname;
const shaderPath = path.join(root, "TC_Hoodie_SDF.glsl");
const htmlPath = path.join(root, "tc_hoodie_preview.html");
const threePath = path.join(
  process.env.USERPROFILE || "",
  ".vscode",
  "extensions",
  "jakearl.shader-toy-web-0.10.17",
  "resources",
  "three.min.js"
);

let threeScriptSrc = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
if (fs.existsSync(threePath)) {
  threeScriptSrc = `file:///${threePath.replace(/\\/g, "/")}`;
}

const rawShader = fs.readFileSync(shaderPath, "utf8");
const shaderBody = rawShader
  .split(/\r?\n/)
  .filter((line) => !line.startsWith("#iChannel") && !line.startsWith("#iUniform"))
  .join("\n");

const fragmentShader = `
uniform vec3 iResolution;
uniform float iTime;
uniform float viewAngle;
uniform float autoRotate;
uniform float rotationSpeed;
uniform float zoom;
uniform float debugMode;
uniform float sliceZ;
uniform sampler2D iChannel0;

${shaderBody}

void main() {
    mainImage(gl_FragColor, gl_FragCoord.xy);
}
`;

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TC Hoodie 3D SDF Preview</title>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #e8e8e8;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      user-select: none;
    }
    canvas {
      display: block;
      width: 100vw;
      height: 100vh;
      cursor: grab;
    }
    canvas:active { cursor: grabbing; }
    #controls {
      position: fixed;
      top: 16px;
      right: 16px;
      z-index: 10;
      background: rgba(255, 255, 255, 0.88);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 12px;
      padding: 16px;
      width: 280px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
      font-size: 13px;
      color: #222;
      transition: opacity 0.2s;
    }
    .control-row {
      margin-bottom: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .control-row.horizontal {
      flex-direction: row;
      justify-content: space-between;
      align-items: center;
    }
    .control-row:last-child { margin-bottom: 0; }
    label {
      font-weight: 600;
      font-size: 12px;
      color: #444;
      display: flex;
      justify-content: space-between;
    }
    span.val { font-weight: normal; color: #666; }
    input[type="range"] {
      width: 100%;
      accent-color: #2563eb;
      cursor: pointer;
    }
    input[type="checkbox"] {
      cursor: pointer;
      width: 16px;
      height: 16px;
      accent-color: #2563eb;
    }
    select {
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid #ccc;
      background: #fff;
      font-size: 12px;
      cursor: pointer;
    }
    #fps-badge {
      position: fixed;
      bottom: 16px;
      left: 16px;
      z-index: 10;
      background: rgba(0, 0, 0, 0.75);
      color: #fff;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-family: monospace;
      letter-spacing: 0.5px;
    }
  </style>
</head>
<body>
  <div id="controls">
    <div style="font-weight:700;font-size:14px;margin-bottom:12px;color:#111;">Hoodie 3D Controls</div>
    
    <div class="control-row horizontal">
      <label for="autoRotate">Auto Rotate</label>
      <input type="checkbox" id="autoRotate" checked />
    </div>

    <div class="control-row">
      <label for="rotationSpeed">Rotation Speed <span class="val" id="speedVal">15°/s</span></label>
      <input type="range" id="rotationSpeed" min="0" max="60" value="15" step="1" />
    </div>

    <div class="control-row">
      <label for="viewAngle">Manual Angle <span class="val" id="angleVal">0°</span></label>
      <input type="range" id="viewAngle" min="0" max="360" value="0" step="1" />
    </div>

    <div class="control-row">
      <label for="zoom">Zoom <span class="val" id="zoomVal">1.0x</span></label>
      <input type="range" id="zoom" min="0.6" max="1.8" value="1.0" step="0.05" />
    </div>

    <div class="control-row">
      <label for="debugMode">Display Mode</label>
      <select id="debugMode">
        <option value="0">Standard 3D Garment</option>
        <option value="1">Raw 2D SDF Atlas</option>
        <option value="2">2D Distance Slice</option>
      </select>
    </div>

    <div class="control-row" id="sliceRow" style="display:none;">
      <label for="sliceZ">Slice Z <span class="val" id="sliceVal">64</span></label>
      <input type="range" id="sliceZ" min="0" max="127" value="64" step="1" />
    </div>
  </div>

  <div id="fps-badge">FPS: -- | Loading texture...</div>

  <script src="${threeScriptSrc}"></script>
  <script>
    const fpsBadge = document.getElementById("fps-badge");
    const query = new URLSearchParams(location.search);

    const autoRotateEl = document.getElementById("autoRotate");
    const speedEl = document.getElementById("rotationSpeed");
    const speedVal = document.getElementById("speedVal");
    const angleEl = document.getElementById("viewAngle");
    const angleVal = document.getElementById("angleVal");
    const zoomEl = document.getElementById("zoom");
    const zoomVal = document.getElementById("zoomVal");
    const debugModeEl = document.getElementById("debugMode");
    const sliceRow = document.getElementById("sliceRow");
    const sliceZEl = document.getElementById("sliceZ");
    const sliceVal = document.getElementById("sliceVal");

    // Init values from query params or defaults
    if (query.has("autoRotate")) autoRotateEl.checked = query.get("autoRotate") === "1";
    if (query.has("viewAngle")) angleEl.value = query.get("viewAngle");
    if (query.has("rotationSpeed")) speedEl.value = query.get("rotationSpeed");
    if (query.has("zoom")) zoomEl.value = query.get("zoom");
    if (query.has("debugMode")) debugModeEl.value = query.get("debugMode");

    const uniforms = {
      iResolution: { value: new THREE.Vector3(window.innerWidth, window.innerHeight, 1) },
      iTime: { value: 0 },
      viewAngle: { value: Number(angleEl.value) },
      autoRotate: { value: autoRotateEl.checked ? 1.0 : 0.0 },
      rotationSpeed: { value: Number(speedEl.value) },
      zoom: { value: Number(zoomEl.value) },
      debugMode: { value: Number(debugModeEl.value) },
      sliceZ: { value: Number(sliceZEl.value) },
      iChannel0: { value: null }
    };

    autoRotateEl.addEventListener("change", () => {
      uniforms.autoRotate.value = autoRotateEl.checked ? 1.0 : 0.0;
    });
    speedEl.addEventListener("input", () => {
      uniforms.rotationSpeed.value = Number(speedEl.value);
      speedVal.textContent = speedEl.value + "°/s";
    });
    angleEl.addEventListener("input", () => {
      uniforms.viewAngle.value = Number(angleEl.value);
      angleVal.textContent = angleEl.value + "°";
    });
    zoomEl.addEventListener("input", () => {
      uniforms.zoom.value = Number(zoomEl.value);
      zoomVal.textContent = Number(zoomEl.value).toFixed(2) + "x";
    });
    debugModeEl.addEventListener("change", () => {
      uniforms.debugMode.value = Number(debugModeEl.value);
      sliceRow.style.display = uniforms.debugMode.value === 2 ? "flex" : "none";
    });
    sliceZEl.addEventListener("input", () => {
      uniforms.sliceZ.value = Number(sliceZEl.value);
      sliceVal.textContent = sliceZEl.value;
    });

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    document.body.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const quad = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({
        uniforms,
        vertexShader: "void main(){gl_Position=vec4(position,1.0);}",
        fragmentShader: ${JSON.stringify(fragmentShader)}
      })
    );
    scene.add(quad);

    const texturePath = "hoodie_sdf_128_atlas.png";
    const textureLoader = new THREE.TextureLoader();

    let textureLoaded = false;
    let start = performance.now();
    let frameCount = 0;
    let lastFpsUpdate = performance.now();

    window.addEventListener("resize", () => {
      renderer.setSize(window.innerWidth, window.innerHeight, false);
      uniforms.iResolution.value.set(window.innerWidth, window.innerHeight, 1);
    });

    // Mouse drag interaction to freely rotate
    let isDragging = false;
    let prevMouseX = 0;
    window.addEventListener("mousedown", (e) => {
      if (e.target.closest("#controls")) return;
      isDragging = true;
      prevMouseX = e.clientX;
    });
    window.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const deltaX = e.clientX - prevMouseX;
      prevMouseX = e.clientX;
      let curAngle = (uniforms.viewAngle.value - deltaX * 0.6) % 360;
      if (curAngle < 0) curAngle += 360;
      uniforms.viewAngle.value = curAngle;
      angleEl.value = Math.round(curAngle);
      angleVal.textContent = Math.round(curAngle) + "°";
    });
    window.addEventListener("mouseup", () => { isDragging = false; });

    textureLoader.load(
      texturePath,
      (texture) => {
        texture.magFilter = THREE.NearestFilter;
        texture.minFilter = THREE.NearestFilter;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.generateMipmaps = false;
        texture.needsUpdate = true;
        uniforms.iChannel0.value = texture;
        textureLoaded = true;
        fpsBadge.textContent = "FPS: -- | Ready";
        requestAnimationFrame(render);
      },
      undefined,
      (err) => {
        fpsBadge.textContent = "Texture load error: " + (err && err.message ? err.message : err);
      }
    );

    function render(now) {
      if (!textureLoaded) return;
      uniforms.iTime.value = (now - start) / 1000;
      renderer.render(scene, camera);

      frameCount++;
      if (now - lastFpsUpdate >= 500) {
        const fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
        fpsBadge.textContent = \`FPS: \${fps} | 3D Raymarching\`;
        frameCount = 0;
        lastFpsUpdate = now;
      }

      // Keep rotating indefinitely
      requestAnimationFrame(render);
    }
  </script>
</body>
</html>
`;

fs.writeFileSync(htmlPath, html, "utf8");
console.log(`Wrote ${htmlPath}`);
