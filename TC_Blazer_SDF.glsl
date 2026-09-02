#iChannel0 "file://blazer_sdf_128_atlas.png"
#iChannel0::MinFilter "Nearest"
#iChannel0::MagFilter "Nearest"
#iChannel0::WrapMode "Clamp"

#iUniform float viewAngle = 0.0 in { 0.0, 360.0 } step 1.0
#iUniform float autoRotate = 0.0 in { 0.0, 1.0 } step 1.0
#iUniform float rotationSpeed = 12.0 in { 0.0, 45.0 }
#iUniform float zoom = 1.0 in { 0.6, 1.8 }
#iUniform float debugMode = 0.0 in { 0.0, 2.0 } step 1.0
#iUniform float sliceZ = 64.0 in { 0.0, 127.0 } step 1.0

// TIMED COLORS / Step 3 / exact supplied 128-cubed atlas.
// The extension supplies uniforms and wraps mainImage. Do not add #version.
// debugMode: 0=blazer, 1=atlas + green status strip, 2=distance slice.
// Red checkerboard: atlas missing/changed or color-converted. Magenta: step cap.
// White shading is a preview material; original GLB textures are not sampled.

precision highp float;
const vec3 TC_MIN = vec3(-1.023646910191, -0.075853843689, -1.023566846251);
const vec3 TC_MAX = vec3(1.024406869411, 1.972199935913, 1.024486933351);
const float TC_H = 0.016000420153;
const float TC_RANGE = 1.159999966621;
const vec2 ATLAS_SIZE = vec2(2048.0, 1024.0);
const int MAX_STEPS = 768;
float tcFlipY;

vec2 atlasBytes(vec2 pixel, float flipY) {
    vec2 uv = (pixel + 0.5) / ATLAS_SIZE;
    uv.y = mix(uv.y, 1.0 - uv.y, flipY);
    return floor(texture2D(iChannel0, uv).rg * 255.0 + 0.5);
}

float atlasError(float flipY) {
    // Known bytes from three widely separated pixels of this exact PNG.
    vec2 a = abs(atlasBytes(vec2(37.0, 61.0), flipY) - vec2(208.0, 127.0));
    vec2 b = abs(atlasBytes(vec2(1021.0, 387.0), flipY) - vec2(165.0, 104.0));
    vec2 c = abs(atlasBytes(vec2(1703.0, 911.0), flipY) - vec2(204.0, 210.0));
    return dot(a + b + c, vec2(1.0));
}

float voxel(vec3 p) {
    p = clamp(p, vec3(0.0), vec3(127.0));
    vec2 tile = vec2(mod(p.z, 16.0), floor(p.z / 16.0));
    vec2 bytes = atlasBytes(tile * 128.0 + p.xy, tcFlipY);
    return ((bytes.x * 256.0 + bytes.y) / 65535.0 * 2.0 - 1.0) * TC_RANGE;
}

float blazerSDF(vec3 p) {
    // Cell-centred samples. Decode each texel BEFORE interpolation.
    vec3 g = clamp((p - TC_MIN) / TC_H - 0.5, vec3(0.0), vec3(127.0));
    vec3 a = floor(g);
    vec3 t = fract(g);
    float z0 = mix(
        mix(voxel(a), voxel(a + vec3(1,0,0)), t.x),
        mix(voxel(a + vec3(0,1,0)), voxel(a + vec3(1,1,0)), t.x), t.y);
    float z1 = mix(
        mix(voxel(a + vec3(0,0,1)), voxel(a + vec3(1,0,1)), t.x),
        mix(voxel(a + vec3(0,1,1)), voxel(a + vec3(1,1,1)), t.x), t.y);
    return mix(z0, z1, t.z);
}

bool intersectBox(vec3 ro, vec3 rd, out float nearT, out float farT) {
    // Stable for exactly front/back/side orthographic rays.
    vec3 safeDir = mix(vec3(-1.0), vec3(1.0), step(vec3(0.0), rd))
                 * max(abs(rd), vec3(0.00000001));
    vec3 ta = (TC_MIN - ro) / safeDir;
    vec3 tb = (TC_MAX - ro) / safeDir;
    vec3 lo = min(ta, tb), hi = max(ta, tb);
    nearT = max(0.0, max(lo.x, max(lo.y, lo.z)));
    farT = min(hi.x, min(hi.y, hi.z));
    return farT >= nearT;
}

// Return 1=hit, 0=miss, -1=iteration cap. Do not silently hide capped rays.
float traceBlazer(vec3 ro, vec3 rd, out float t) {
    float nearT, farT;
    t = 0.0;
    if (!intersectBox(ro, rd, nearT, farT)) return 0.0;
    t = nearT + 0.000001;
    float previousT = nearT;
    for (int i = 0; i < MAX_STEPS; ++i) {
        if (t > farT) return 0.0;
        float d = blazerSDF(ro + rd * t);
        if (d <= TC_H * 0.004) {
            if (d < 0.0) {
                float leftT = previousT, rightT = t;
                for (int j = 0; j < 10; ++j) {
                    float midT = 0.5 * (leftT + rightT);
                    if (blazerSDF(ro + rd * midT) < 0.0) rightT = midT;
                    else leftT = midT;
                }
                t = 0.5 * (leftT + rightT);
            }
            return 1.0;
        }
        previousT = t;
        // Practical conservative step for this sampled field, not a proof
        // of a continuous exact SDF or preservation of sub-voxel details.
        t += max(0.65 * d, TC_H * 0.025);
    }
    return t > farT ? 0.0 : -1.0;
}

vec3 blazerNormal(vec3 p) {
    float e = TC_H * 0.35;
    vec3 n = vec3(
        blazerSDF(p + vec3(e,0,0)) - blazerSDF(p - vec3(e,0,0)),
        blazerSDF(p + vec3(0,e,0)) - blazerSDF(p - vec3(0,e,0)),
        blazerSDF(p + vec3(0,0,e)) - blazerSDF(p - vec3(0,0,e)));
    return n / max(length(n), 0.00000001);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 screenUV = fragCoord / iResolution.xy;
    float error0 = atlasError(0.0), error1 = atlasError(1.0);
    tcFlipY = error1 < error0 ? 1.0 : 0.0;
    if (min(error0, error1) > 1.0) {
        float check = mod(floor(fragCoord.x / 24.0) + floor(fragCoord.y / 24.0), 2.0);
        fragColor = vec4(mix(vec3(0.25,0.01,0.02), vec3(0.9,0.08,0.05), check), 1.0);
        return;
    }
    if (debugMode > 0.5 && debugMode < 1.5) {
        vec2 pixel = floor(clamp(vec2(screenUV.x, 1.0-screenUV.y), 0.0, 0.999999) * ATLAS_SIZE);
        vec3 col = vec3(atlasBytes(pixel, tcFlipY) / 255.0, 0.0);
        if (screenUV.y < 0.035) col = vec3(0.05, 0.8, 0.25);
        fragColor = vec4(col, 1.0);
        return;
    }
    if (debugMode > 1.5) {
        vec3 p = TC_MIN + (TC_MAX - TC_MIN) * vec3(screenUV, (floor(sliceZ)+0.5)/128.0);
        float d = blazerSDF(p);
        vec3 col = d < 0.0 ? vec3(0.1,0.35,0.85) : vec3(0.88);
        col = mix(vec3(1.0,0.5,0.0), col, smoothstep(0.0, TC_H * 0.5, abs(d)));
        fragColor = vec4(col, 1.0);
        return;
    }

    float angle = radians(viewAngle + autoRotate * iTime * rotationSpeed);
    vec3 right = vec3(cos(angle), 0.0, -sin(angle));
    vec3 up = vec3(0.0, 1.0, 0.0);
    vec3 rd = vec3(-sin(angle), 0.0, -cos(angle));
    float fit = max(1.0, min(iResolution.y, iResolution.x / 0.78));
    vec2 q = (fragCoord - 0.5 * iResolution.xy) / fit * 2.30 / zoom;
    vec3 ro = 0.5 * (TC_MIN + TC_MAX) + q.x * right + q.y * up - 3.0 * rd;
    float t;
    float status = traceBlazer(ro, rd, t);
    vec3 col = vec3(0.90);
    if (status > 0.5) {
        vec3 n = blazerNormal(ro + rd * t);
        vec3 key = normalize(-0.4 * right + 0.6 * up - rd);
        vec3 fill = normalize(0.7 * right + 0.1 * up + 0.7 * rd);
        float light = 0.28 + 0.62 * max(dot(n, key), 0.0) + 0.10 * max(dot(n, fill), 0.0);
        col = vec3(0.88) * light;
    } else if (status < -0.5) {
        col = vec3(1.0, 0.0, 1.0);
    }
    fragColor = vec4(col, 1.0);
}
