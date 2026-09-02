import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = __dirname;
const shaderPath = path.join(root, "TC_Blazer_SDF.glsl");
const htmlPath = path.join(root, "tc_blazer_preview.html");
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
  <title>TC Blazer Preview</title>
  <style>
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #dcdcdc;
      font-family: Consolas, monospace;
    }
    #status {
      position: fixed;
      left: 8px;
      top: 8px;
      z-index: 2;
      max-width: calc(100% - 16px);
      background: rgba(255, 255, 255, 0.92);
      color: #111;
      padding: 8px 10px;
      white-space: pre-wrap;
      font-size: 12px;
      line-height: 1.35;
    }
    canvas {
      display: block;
      width: 100vw;
      height: 100vh;
    }
  </style>
</head>
<body>
  <div id="status">initializing...</div>
  <script src="${threeScriptSrc}"></script>
  <script>
    const statusEl = document.getElementById("status");
    const errors = [];
    const query = new URLSearchParams(location.search);
    const framesToMeasure = Number(query.get("frames") || "120");
    const compileMessages = [];

    const note = (label, value) => {
      const line = value === undefined ? String(label) : label + ": " + value;
      compileMessages.push(line);
      statusEl.textContent = compileMessages.join("\\n");
    };

    const originalError = console.error.bind(console);
    console.error = (...args) => {
      errors.push(args.map((item) => String(item)).join(" "));
      originalError(...args);
      note("console.error", errors[errors.length - 1]);
    };
    window.addEventListener("error", (event) => {
      errors.push(String(event.message || event.error || "window error"));
      note("window.error", errors[errors.length - 1]);
    });

    const uniforms = {
      iResolution: { value: new THREE.Vector3(window.innerWidth, window.innerHeight, 1) },
      iTime: { value: 0 },
      viewAngle: { value: Number(query.get("viewAngle") || "0") },
      autoRotate: { value: Number(query.get("autoRotate") || "0") },
      rotationSpeed: { value: Number(query.get("rotationSpeed") || "12") },
      zoom: { value: Number(query.get("zoom") || "1") },
      debugMode: { value: Number(query.get("debugMode") || "0") },
      sliceZ: { value: Number(query.get("sliceZ") || "64") },
      iChannel0: { value: null }
    };

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: true
    });
    renderer.setPixelRatio(1);
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    document.body.appendChild(renderer.domElement);

    const gl = renderer.getContext();
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

    const texturePath = ${JSON.stringify(`file:///${path.join(root, "blazer_sdf_128_atlas.png").replace(/\\/g, "/")}`)};
    const textureLoader = new THREE.TextureLoader();

    let textureLoaded = false;
    let start = performance.now();
    let measuredFrames = 0;
    let totalFrameMs = 0;
    let previousFrame = 0;

    const emitStatus = () => {
      const avgFrameMs = measuredFrames > 0 ? totalFrameMs / measuredFrames : null;
      const payload = {
        textureLoaded,
        measuredFrames,
        avgFrameMs,
        approxFps: avgFrameMs ? 1000 / avgFrameMs : null,
        webglContext: gl instanceof WebGL2RenderingContext ? "WebGL2" : "WebGL1",
        glVersion: gl.getParameter(gl.VERSION),
        glRenderer: gl.getParameter(gl.RENDERER),
        glVendor: gl.getParameter(gl.VENDOR),
        shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
        errors
      };
      statusEl.textContent = JSON.stringify(payload, null, 2);
    };

    const onResize = () => {
      renderer.setSize(window.innerWidth, window.innerHeight, false);
      uniforms.iResolution.value.set(window.innerWidth, window.innerHeight, 1);
    };
    window.addEventListener("resize", onResize);

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
        note("texture", "loaded");
        requestAnimationFrame(render);
      },
      undefined,
      (err) => {
        errors.push("Texture load failed: " + (err && err.message ? err.message : err));
        emitStatus();
      }
    );

    function render(now) {
      if (!textureLoaded) {
        emitStatus();
        return;
      }
      uniforms.iTime.value = (now - start) / 1000;
      if (measuredFrames > 0) {
        totalFrameMs += now - previousFrame;
      }
      previousFrame = now;
      measuredFrames += 1;
      renderer.render(scene, camera);
      if (measuredFrames >= framesToMeasure) {
        emitStatus();
        return;
      }
      requestAnimationFrame(render);
    }
  </script>
</body>
</html>
`;

fs.writeFileSync(htmlPath, html, "utf8");
console.log(`Wrote ${htmlPath}`);
