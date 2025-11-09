# GPU Multiverse Shader Verification Checklist
**Agent 2: Quality Assurance**

This checklist verifies that the new GPU renderer matches the CPU version exactly.

---

## ✅ Pass 1 Shader Verification

### 1.1 Voltage Normalization
- [ ] Uses `(waveValue + 10.0) * 0.05` (NOT `abs(waveValue) * 0.14`)
- [ ] Includes intensity multiplication: `* intensity`
- [ ] Clamps to [0, 1]: `clamp(..., 0.0, 1.0)`

**Reference:**
```python
# CPU (numba_renderer.py line 166)
normalized = max(0.0, min(1.0, (waveform_val + 10.0) * 0.05 * intensity))
```

**Expected GPU shader:**
```glsl
float normalized = clamp((waveValue + 10.0) * 0.05 * intensity, 0.0, 1.0);
```

---

### 1.2 Audio Texture Y Coordinate
- [ ] Uses `(float(ch) + 0.5) / 4.0` (NOT `float(ch) / 4.0`)
- [ ] The +0.5 centers the sampling on the pixel

**Reference:**
```python
# Correct Y coordinate for pixel center sampling
y_coord = (channel + 0.5) / 4.0
```

**Expected GPU shader:**
```glsl
float y_coord = (float(ch) + 0.5) / 4.0;
float waveValue = texture(audio_tex, vec2(x_sample, y_coord)).r;
```

---

### 1.3 Curve Effect Application
- [ ] Curve is applied BEFORE rotation (in Pass 1, not Pass 2)
- [ ] Uses original (not rotated) coordinates
- [ ] Calculation matches CPU version exactly

**Reference:**
```python
# CPU (numba_renderer.py lines 149-155)
if curve > 0.001:
    bend_shape = math.sin(x_normalized * math.pi)  # 0 to 1 to 0
    bend_amount = y_from_center * bend_shape * curve * 2.0
    x_sample = (x_sample + bend_amount) % 1.0
```

**Expected GPU shader:**
```glsl
float x_sample = x_normalized;
if (curve > 0.001) {
    float bend_shape = sin(x_normalized * PI);
    float bend_amount = y_from_center * bend_shape * curve * 2.0;
    x_sample = fract(x_sample + bend_amount);
}
```

---

### 1.4 Frequency to Hue Conversion
- [ ] Returns value in range 0-360 degrees (or 0-1 if used consistently)
- [ ] Uses log2 for octave calculation
- [ ] Matches CPU algorithm

**Reference:**
```python
# CPU (numba_renderer.py lines 13-20)
freq = max(20.0, min(20000.0, freq))
base_freq = 261.63
octave_position = math.log2(freq / base_freq) % 1.0
if octave_position < 0:
    octave_position += 1.0
return octave_position  # 0-1 range
```

**Expected GPU shader:**
```glsl
float getHueFromFrequency(float freq) {
    freq = clamp(freq, 20.0, 20000.0);
    const float baseFreq = 261.63;
    float octavePosition = fract(log2(freq / baseFreq));
    if (octavePosition < 0.0) octavePosition += 1.0;
    return octavePosition * 360.0;  // 0-360 degrees
}
```

---

### 1.5 HSV to RGB Conversion
- [ ] Uses C++ sector-based algorithm (NOT vectorized formula)
- [ ] Has 6 conditional branches for hue sectors
- [ ] Matches C++ Multiverse.cpp implementation

**Reference:**
```cpp
// C++ (Multiverse.cpp lines 516-532)
float c = 1.0f;
float x = c * (1 - std::abs(std::fmod(hue / 60.0f, 2) - 1));
float r, g, b;
if (hue < 60) { r = c; g = x; b = 0; }
else if (hue < 120) { r = x; g = c; b = 0; }
else if (hue < 180) { r = 0; g = c; b = x; }
else if (hue < 240) { r = 0; g = x; b = c; }
else if (hue < 300) { r = x; g = 0; b = c; }
else { r = c; g = 0; b = x; }
```

**Expected GPU shader:**
```glsl
vec3 hsv2rgb(vec3 c) {
    float h = c.x * 360.0;  // Convert to degrees
    float s = c.y;
    float v = c.z;

    float C = v * s;
    float X = C * (1.0 - abs(mod(h / 60.0, 2.0) - 1.0));
    float m = v - C;

    vec3 rgb;
    if (h < 60.0) rgb = vec3(C, X, 0.0);
    else if (h < 120.0) rgb = vec3(X, C, 0.0);
    else if (h < 180.0) rgb = vec3(0.0, C, X);
    else if (h < 240.0) rgb = vec3(0.0, X, C);
    else if (h < 300.0) rgb = vec3(X, 0.0, C);
    else rgb = vec3(C, 0.0, X);

    return rgb + m;
}
```

---

## ✅ Pass 2 Shader Verification

### 2.1 Scale Compensation Calculation
- [ ] Calculates `scaleX` and `scaleY` correctly
- [ ] Uses `max(scaleX, scaleY)` for final scale
- [ ] Matches C++ Multiverse.cpp exactly

**Reference:**
```cpp
// C++ (Multiverse.cpp lines 562-566)
float absCosA = std::abs(cosA);
float absSinA = std::abs(sinA);
float scaleX = (w * absCosA + h * absSinA) / w;
float scaleY = (w * absSinA + h * absCosA) / h;
float scale = std::max(scaleX, scaleY);
```

**Expected GPU shader:**
```glsl
float rad = radians(angle);
float cosA = cos(rad);
float sinA = sin(rad);
float absCosA = abs(cosA);
float absSinA = abs(sinA);
float scaleX = (width * absCosA + height * absSinA) / width;
float scaleY = (width * absSinA + height * absCosA) / height;
float scale = max(scaleX, scaleY);
```

---

### 2.2 Rotation Matrix Application
- [ ] Scale is applied BEFORE rotation: `centered /= scale`
- [ ] Rotation matrix signs are correct
- [ ] Matches C++ implementation

**Reference:**
```cpp
// C++ (Multiverse.cpp lines 572-575)
float dx = (x - centerX) / scale;
float dy = (y - centerY) / scale;
int srcX = (int)(centerX + dx * cosA + dy * sinA);
int srcY = (int)(centerY - dx * sinA + dy * cosA);
```

**Expected GPU shader:**
```glsl
vec2 uv = (x, y) / (width, height);
vec2 centered = uv - 0.5;
centered /= scale;  // Apply scale BEFORE rotation
vec2 rotated = vec2(
    centered.x * cosA + centered.y * sinA,
    -centered.x * sinA + centered.y * cosA
);
vec2 uv_rotated = rotated + 0.5;
```

---

### 2.3 Bounds Checking
- [ ] Out-of-bounds pixels are set to black (0.0)
- [ ] Checks all four bounds: x, y, width, height

**Expected GPU shader:**
```glsl
if (uv_rotated.x >= 0.0 && uv_rotated.x <= 1.0 &&
    uv_rotated.y >= 0.0 && uv_rotated.y <= 1.0) {
    color = texture(temp_fbo[ch], uv_rotated);
} else {
    color = vec4(0.0);  // Black outside bounds
}
```

---

## ✅ Pass 3 Shader Verification

### 3.1 Region Map Sampling Timing
- [ ] Region map is sampled using FINAL coordinates (after rotation)
- [ ] NOT sampled before rotation
- [ ] Sampled ONCE per pixel, outside channel loop

**Expected GPU shader:**
```glsl
for each pixel (x, y):
    // Sample region map ONCE using final coordinates
    currentRegion = -1;
    if (use_region_map) {
        float regionVal = texture(region_tex, (x, y) / (width, height)).r;
        currentRegion = int(regionVal * 255.0 + 0.5);
    }

    for each channel:
        if (use_region_map && currentRegion != ch) continue;
        // ... blend channel ...
```

---

### 3.2 Region Map Rounding
- [ ] Uses `int(regionVal * 255.0 + 0.5)` for proper rounding
- [ ] NOT `int(regionVal * 255.0)` (which truncates)

**Expected GPU shader:**
```glsl
int currentRegion = int(regionVal * 255.0 + 0.5);  // Proper rounding
```

---

### 3.3 Blend Modes
All 4 blend modes must match CPU version exactly:

#### 3.3.1 Add Blend
- [ ] `min(base + blend, 1.0)` (with clamping)

```glsl
vec3 blendAdd(vec3 base, vec3 blend) {
    return min(base + blend, vec3(1.0));
}
```

#### 3.3.2 Screen Blend
- [ ] `1.0 - (1.0 - base) * (1.0 - blend)`

```glsl
vec3 blendScreen(vec3 base, vec3 blend) {
    return vec3(1.0) - (vec3(1.0) - base) * (vec3(1.0) - blend);
}
```

#### 3.3.3 Difference Blend
- [ ] `abs(base - blend)`

```glsl
vec3 blendDifference(vec3 base, vec3 blend) {
    return abs(base - blend);
}
```

#### 3.3.4 Color Dodge Blend
- [ ] `min(1.0, base / max(0.001, 1.0 - blend))` when blend < 0.999
- [ ] `1.0` when blend >= 0.999
- [ ] NO extra check for `base <= 0.001`

**Reference:**
```python
# CPU (numba_renderer.py lines 216-220)
if layer[y, x, c] < 0.999:
    result = buffer[y, x, c] / max(0.001, 1.0 - layer[y, x, c])
    buffer[y, x, c] = min(1.0, result)
else:
    buffer[y, x, c] = 1.0
```

**Expected GPU shader:**
```glsl
vec3 blendColorDodge(vec3 base, vec3 blend) {
    vec3 result;
    for (int i = 0; i < 3; i++) {
        if (blend[i] >= 0.999) {
            result[i] = 1.0;
        } else {
            result[i] = min(1.0, base[i] / max(0.001, 1.0 - blend[i]));
        }
    }
    return result;
}
```

---

### 3.4 Brightness Application
- [ ] Applied AFTER blending
- [ ] Multiplies RGB channels (not alpha)
- [ ] Clamps final result to [0, 1]

**Expected GPU shader:**
```glsl
result.rgb *= brightness;
result = clamp(result, 0.0, 1.0);
```

---

## 🎯 Critical Success Criteria

The new GPU implementation is APPROVED only if:

1. ✅ All Pass 1 checks (1.1-1.5) pass
2. ✅ All Pass 2 checks (2.1-2.3) pass
3. ✅ All Pass 3 checks (3.1-3.4) pass
4. ✅ Order of operations: Curve → Rotation → Blending
5. ✅ Region map sampled AFTER rotation
6. ✅ No extra checks in Color Dodge
7. ✅ All formulas match CPU version exactly

**If ANY check fails, report to Agent 1 with specific fix needed.**

---

## 📋 Verification Process

For each pass:
1. Read the shader code
2. Check each item in the checklist
3. Compare with CPU reference code
4. Compare with C++ reference code (for rotation/HSV)
5. Document any discrepancies
6. Report findings to Agent 1

---

## 🔍 Common Pitfalls to Watch For

- ❌ Using `abs(waveValue)` instead of signed conversion
- ❌ Missing +0.5 in texture Y coordinate
- ❌ Applying rotation before curve
- ❌ Sampling region map before rotation
- ❌ Wrong scale calculation or missing scale compensation
- ❌ Extra boundary checks in Color Dodge
- ❌ Vectorized HSV formula instead of sector-based
- ❌ Wrong rounding in region map

---

**Status**: Ready for verification
**Agent**: Agent 2 (Quality Assurance)
**Last Updated**: 2025-11-03
