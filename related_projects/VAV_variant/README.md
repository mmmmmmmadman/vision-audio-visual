# VAV - Vision-Audio-Visual System
**Version: VAV_20251018_v2 (with Region Rendering)**

Real-time visual-audio-visual feedback system for Eurorack modular synthesis.

## Quick Start

```bash
# Setup environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python3 main_compact.py
```

## Features

### Vision System
- **MediaPipe Cable Detection**: Real-time cable detection from webcam
- **Multi-camera Support**: HD Webcam, OBS Virtual Camera, Continuity Camera
- **Cable Analysis**: Position tracking and sequence generation

### Audio Processing
- **ES-8 Integration**: 4 input channels, 7 output channels (stereo + 5 CV)
- **Ellen Ripley Effect Chain**: Stereo delay → Grain → Reverb with chaos modulation
- **Audio Analysis**: FFT-based frequency detection for visual feedback

### CV Generation
- **3x Decay Envelopes**: Triggered by cable detection, modulate audio effects
- **2x Sequence CV**: Position-based and length-based sequences (1-16 steps)
- **Real-time Output**: 48kHz sample-accurate CV generation to ES-8

### Visual Rendering
- **Multiverse Renderer**: 4-channel audio-reactive visual synthesis
  - Frequency-to-color mapping (octave-based HSV)
  - Per-channel intensity, angle, curve controls
  - 4 blend modes: Add, Screen, Difference, Color Dodge
  - Numba JIT compilation for real-time 1920x1080@30-60fps
- **Region Rendering** ⭐ NEW: Content-aware dispersed region mapping
  - Each channel renders in different screen regions based on camera input
  - 4 region modes: Brightness, Color, Quadrant, Edge detection
  - Real-time dynamic mapping (3-5ms overhead)
  - Perfect for interactive light/hand-based performances
- **Scope Widget**: Real-time waveform display (30fps)
- **Camera Overlay**: Blended camera input with visual effects

### GUI
- **Compact Interface**: 6-column horizontal layout
- **Real-time Controls**:
  - 4-channel Multiverse sliders (Intensity, Angle, Curve)
  - Global brightness and blend mode
  - Camera mix control
  - Region rendering toggle and mode selector ⭐ NEW
  - Ellen Ripley effect parameters
- **Device Management**: Hot-swappable audio/video device selection

## System Requirements

- macOS 12+ (Monterey or later)
- Python 3.11+
- 8GB RAM minimum (16GB recommended)
- Expert Sleepers ES-8 (audio interface)
- Webcam (built-in or external)

## Project Structure

```
vav/
├── audio/
│   ├── io.py                    # ES-8 audio I/O (4 in, 7 out)
│   ├── mixer.py                 # Stereo mixer with panning
│   ├── analysis.py              # FFT frequency detection
│   └── effects/
│       ├── ellen_ripley.py      # Complete effect chain
│       ├── delay.py             # Stereo delay
│       ├── grain.py             # Granular processor
│       ├── reverb.py            # Stereo reverb
│       └── chaos.py             # Chaos generator
├── vision/
│   ├── camera.py                # Webcam capture (OpenCV)
│   ├── cable_detector.py        # MediaPipe cable detection
│   └── analyzer.py              # Cable analysis for CV
├── cv_generator/
│   ├── envelope.py              # Decay envelope generator
│   ├── sequencer.py             # Sequence CV generator
│   └── signal.py                # Signal utilities
├── visual/
│   ├── numba_renderer.py        # Multiverse renderer (Numba JIT)
│   ├── content_aware_regions.py # Content-aware region mapping ⭐ NEW
│   ├── region_mapper.py         # Static region patterns ⭐ NEW
│   ├── gpu_renderer.py          # GPU fallback renderer
│   └── qt_opengl_renderer.py    # Qt OpenGL renderer
├── gui/
│   ├── compact_main_window.py   # Main GUI window
│   ├── device_dialog.py         # Device selection dialog
│   └── scope_widget.py          # Waveform scope widget
├── core/
│   └── controller.py            # Main system controller
└── utils/
    └── config.py                # Configuration management

main_compact.py                  # Application entry point
```

## Technical Details

### Multiverse Visual Engine
- **Ported from VCV Rack MADZINE Multiverse module**
- **Numba JIT Optimization**: LLVM compilation for CPU parallel processing
- **Color Mapping**: Frequency → Octave position → HSV hue (261.63 Hz base)
- **Curve Effect**: Y-axis dependent X-sampling for waveform bending
- **Rotation**: Reverse mapping with scale compensation (no black borders)
- **Audio Buffer**: 4800 samples (~100ms at 48kHz) per channel

### Performance
- **Rendering**: 1920x1080 @ 30-60 fps (Numba JIT)
- **Audio Latency**: ~5.3ms (256 samples at 48kHz)
- **CV Update Rate**: Sample-accurate at 48kHz
- **Frame Processing**: ~16-33ms per frame

### Known Issues
- AVCaptureDeviceTypeExternal deprecation warning (macOS Continuity Camera)
- First frame may take longer (Numba JIT compilation warmup)

## Recent Updates

### 2025-10-18 v2: Region Rendering ⭐ NEW
- ✓ Added content-aware region rendering system
- ✓ 4 region modes: Brightness (recommended), Color, Quadrant, Edge
- ✓ Brightness mode: Dark→CH1, Medium Dark→CH2, Medium Bright→CH3, Bright→CH4
- ✓ Numba JIT optimized region blending (3-5ms overhead)
- ✓ GUI controls: Region Map checkbox + Region Mode dropdown
- ✓ Perfect for interactive performances with hand/light control

### 2025-10-18 v1: Multiverse Integration
- ✓ Fixed curve implementation (Y-axis bending effect)
- ✓ Fixed color mapping (frequency-only, not waveform-dependent)
- ✓ Fixed angle rotation (reverse mapping)
- ✓ Fixed intensity control (0 = black screen)
- ✓ Fixed input channels (4 channels for ch1-4)

### Code Cleanup
- ✓ Removed 21 unused files (tests, old renderers, old GUI)
- ✓ Fixed import dependencies
- ✓ Verified all core modules load successfully

## Documentation

- **[REGION_RENDERING_GUIDE.md](REGION_RENDERING_GUIDE.md)**: Complete guide for region rendering feature

## License

See LICENSE file for details.

## Author

MADZINE (2025)
