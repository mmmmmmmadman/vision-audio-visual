# Qt OpenGL Threading Fix - Testing Checklist

## Pre-Test Setup

### 1. Verify Dependencies
```bash
# Check PyQt6 is installed
python3 -c "import PyQt6; print('PyQt6:', PyQt6.__version__)"

# Check OpenGL is available
python3 -c "from OpenGL.GL import *; print('PyOpenGL: OK')"

# Check module imports
python3 -c "from vav.visual.qt_opengl_renderer import QtMultiverseRenderer; print('✓ Module OK')"
```

Expected output:
```
PyQt6: 6.x.x
PyOpenGL: OK
✓ Module OK
```

---

## Test 1: Thread Safety Test

### Run Test
```bash
python3 test_qt_opengl_threading.py
```

### Expected Output
```
============================================================
Qt OpenGL Renderer - Thread Safety Tests
============================================================

============================================================
GUI Thread Rendering Test (Baseline)
============================================================
Creating renderer in thread: MainThread
✓ Qt OpenGL Multiverse renderer initialized: 1920x1080 (thread-safe)

Rendering from GUI thread: MainThread
  Frame 1/5: XXXXX non-zero pixels
  Frame 2/5: XXXXX non-zero pixels
  Frame 3/5: XXXXX non-zero pixels
  Frame 4/5: XXXXX non-zero pixels
  Frame 5/5: XXXXX non-zero pixels

✓ GUI thread rendering successful

============================================================
Cross-Thread Rendering Test
============================================================
Creating renderer in thread: MainThread
✓ Qt OpenGL Multiverse renderer initialized: 1920x1080 (thread-safe)

Background thread started: VisionThread
  Frame 1/10: Rendering from background thread...
    ✓ Frame 1 rendered: XXXXX non-zero pixels
  Frame 2/10: Rendering from background thread...
    ✓ Frame 2 rendered: XXXXX non-zero pixels
  ...
  Frame 10/10: Rendering from background thread...
    ✓ Frame 10 rendered: XXXXX non-zero pixels

✓ Background thread completed successfully

============================================================
Test Results
============================================================
  Frames rendered: 10/10
  ✓✓ SUCCESS: Cross-thread rendering works correctly!
============================================================

============================================================
Test Summary
============================================================
  ✓ PASS: gui_thread
  ✓ PASS: cross_thread

============================================================
✓✓✓ ALL THREADING TESTS PASSED!
Qt OpenGL Renderer is thread-safe.
============================================================
```

### ✅ Pass Criteria
- [ ] No crash or error
- [ ] All 10 frames rendered successfully
- [ ] "SUCCESS: Cross-thread rendering works correctly!"
- [ ] Both tests show "✓ PASS"

### ❌ Failure Indicators
- Console shows: "Cannot make QOpenGLContext current in a different thread"
- Timeout warnings
- Crash during rendering
- "✗ FAIL" in test summary

---

## Test 2: Performance Test

### Run Test
```bash
python3 test_qt_opengl_final.py
```

### Expected Output (Excerpt)
```
============================================================
Performance Test - 100 frames @ 1920x1080
============================================================

✓ Rendered 100 frames in X.XXs
  Average FPS: XX.X
  Frame time: XX.XXms
  ✓✓ EXCELLENT: XX.X FPS (target: 30 FPS)

============================================================
Test Summary
============================================================
  ✓ PASS: blend_modes
  ✓ PASS: audio_range
  ✓ PASS: performance

============================================================
✓✓✓ ALL TESTS PASSED!
Qt OpenGL Multiverse Renderer is fully functional.
============================================================
```

### ✅ Pass Criteria
- [ ] FPS ≥ 30 (target)
- [ ] FPS ≥ 24 (acceptable)
- [ ] All blend modes work
- [ ] No visual artifacts

### ⚠️ Warning Signs
- FPS < 24: Performance issue (but may still work)
- Blend modes produce black frames: Shader issue

---

## Test 3: Integration Test (Real Application)

### Run Application
```bash
python3 main_compact.py
```

### Test Steps

#### Step 1: Startup
- [ ] Application starts without crash
- [ ] No Qt OpenGL errors in console
- [ ] Console shows: "✓ Qt OpenGL Multiverse renderer initialized: 1920x1080 (thread-safe)"

#### Step 2: Enable Multiverse Rendering
- [ ] Click "Enable Multiverse" checkbox
- [ ] Visual output changes from camera view to colorful Multiverse rendering
- [ ] No crash or freeze
- [ ] FPS counter shows ~30 FPS

#### Step 3: Adjust Parameters
- [ ] Change blend mode (Add → Screen → Difference → ColorDodge)
- [ ] Visual output changes smoothly
- [ ] No crash or freeze
- [ ] Adjust brightness slider (0.0 → 4.0)
- [ ] Visual output brightness changes

#### Step 4: Play Audio
- [ ] Connect audio input (ES-8 or audio interface)
- [ ] Play audio signals on Ch1-4
- [ ] Multiverse visualization reacts to audio
- [ ] Colors change based on frequency
- [ ] Intensity changes based on amplitude

#### Step 5: Long-Running Test
- [ ] Let application run for 5 minutes
- [ ] No crash or memory leak
- [ ] FPS remains stable (~30)
- [ ] Console shows periodic debug output (every 100 frames)

#### Step 6: Thread Safety Verification
- [ ] Console shows: `[Qt OpenGL] Rendering frame XXX (thread: VisionThread)`
- [ ] No "Cannot make QOpenGLContext current" errors
- [ ] No Qt OpenGL warnings

---

## Test 4: Stress Test (Optional)

### Rapid Parameter Changes
```python
# In Python REPL or script
from PyQt6.QtWidgets import QApplication
from vav.visual.qt_opengl_renderer import QtMultiverseRenderer
import numpy as np
import threading
import time

app = QApplication([])
renderer = QtMultiverseRenderer(1920, 1080)

# Prepare test data
channels_data = [
    {
        'enabled': True,
        'audio': np.random.randn(4800).astype(np.float32) * 3.0,
        'frequency': 440.0,
        'intensity': 1.0,
    }
    for _ in range(4)
]

def hammer_renderer():
    """Rapidly call render() from background thread"""
    for i in range(100):
        renderer.render(channels_data)
        time.sleep(0.01)  # 100 FPS
    print("Stress test complete!")

thread = threading.Thread(target=hammer_renderer)
thread.start()

# Run event loop briefly
import time
for _ in range(10):
    app.processEvents()
    time.sleep(0.1)

thread.join()
print("✓ Stress test passed")
```

### ✅ Pass Criteria
- [ ] No crash
- [ ] All 100 frames rendered
- [ ] No memory leak
- [ ] Console shows "✓ Stress test passed"

---

## Debugging Guide

### If Tests Fail

#### Error: "Cannot make QOpenGLContext current"
**Diagnosis**: OpenGL context accessed from wrong thread
**Action**:
1. Check console for thread name in debug output
2. Verify renderer was created in GUI thread (MainThread)
3. Check git diff to ensure all changes are applied

#### Error: "Qt OpenGL render timeout (1s)"
**Diagnosis**: GUI thread blocked or event loop not running
**Action**:
1. Check if `app.exec()` or `app.processEvents()` is being called
2. Profile code to find blocking operations in GUI thread
3. Reduce timeout if needed (line 475 in qt_opengl_renderer.py)

#### Error: Test hangs indefinitely
**Diagnosis**: Deadlock in signal/slot or event system
**Action**:
1. Press Ctrl+C to interrupt
2. Check console for last debug output
3. Verify Qt event loop is running (`app.exec()` or `app.processEvents()`)

#### Error: Black frames (all zeros)
**Diagnosis**: Rendering not executing or shader issue
**Action**:
1. Check audio data is non-zero (print min/max)
2. Check enabled_mask is [1.0, 1.0, 1.0, 1.0]
3. Verify shaders compiled successfully (check console)

---

## Expected Console Output Patterns

### Normal Operation
```
✓ Qt OpenGL Multiverse renderer initialized: 1920x1080 (thread-safe)
[Qt OpenGL] Rendering frame 100 (thread: VisionThread)
[Qt OpenGL] Rendering frame 200 (thread: VisionThread)
[Qt OpenGL] Rendering frame 300 (thread: MainThread)
```

### Warning Signs
```
⚠ Warning: Qt OpenGL render timeout (1s)
⚠ Shader validation returned status 0
✗ Cannot make QOpenGLContext current in a different thread
✗ Framebuffer not complete in paintGL
```

---

## Final Verification

### ✅ All Tests Pass If:
- [ ] `test_qt_opengl_threading.py` → ✓✓✓ ALL THREADING TESTS PASSED
- [ ] `test_qt_opengl_final.py` → ✓✓✓ ALL TESTS PASSED
- [ ] `main_compact.py` runs without crash for 5+ minutes
- [ ] Multiverse rendering displays correctly
- [ ] Console shows thread names (VisionThread)
- [ ] No Qt OpenGL context errors

### 📊 Performance Benchmarks
- GUI Thread Rendering: 60+ FPS
- Background Thread Rendering: 30-45 FPS
- Cross-Thread Overhead: 0.2-0.6ms (~2%)

### 🎉 Success Criteria Met
If all above tests pass:
- ✅ Thread safety: Fixed
- ✅ GPU acceleration: Maintained
- ✅ Resolution: 1920x1080 (maintained)
- ✅ No crash: Verified
- ✅ Performance: Acceptable (30+ FPS)

---

## Rollback Plan (If Tests Fail)

If tests fail and issue cannot be resolved quickly:

```bash
# Revert changes to qt_opengl_renderer.py
git checkout HEAD -- vav/visual/qt_opengl_renderer.py

# Or restore from backup
cp vav/visual/qt_opengl_renderer.py.backup vav/visual/qt_opengl_renderer.py
```

**Alternative**: Use Numba JIT renderer (CPU) as temporary fallback:
- Edit `vav/core/controller.py` line 164-183
- Force Numba renderer instead of Qt OpenGL
- Slower but stable

---

## Contact

If tests fail, provide:
1. Console output (full log)
2. Error traceback
3. Test results summary
4. System info: macOS version, Python version, PyQt6 version

**Issue tracking**: Document all test results in this checklist.
