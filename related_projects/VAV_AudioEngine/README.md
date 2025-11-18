# Alien4 Audio Engine

Complete C++ audio processing engine combining Documenta sampler with simplified Ellen Ripley effects.

## Features

### Documenta Sampler
- 4-layer stereo recording/playback
- Loop playback with variable speed (0.25x - 4x)
- Slice scanning
- Input/Loop mix control
- Feedback system

### 3-Band Equalizer
- Low shelf (250 Hz)
- Mid peak (1 kHz)
- High shelf (4 kHz)
- ±20dB gain range

### Ellen Ripley Effects (Simplified)
- **Stereo Delay**: Independent L/R times, feedback control
- **Freeverb Reverb**: Room size, damping, decay control
- Send/Return routing

## Signal Flow

```
Input → REC/LOOP → MIX → FDBK → 3-Band EQ → Send → (Delay + Reverb) → Return → SPEED → Output
```

## Building

```bash
cd VAV_AudioEngine
mkdir build && cd build
cmake ..
make
```

## Running Test

```bash
./test_alien4
```

## Project Structure

```
VAV_AudioEngine/
├── src/
│   ├── alien4_engine.hpp       # Main audio engine
│   ├── audio_layer.hpp          # Audio recording/playback layer
│   ├── three_band_eq.hpp        # 3-band equalizer
│   └── ripley/
│       ├── stereo_delay.hpp     # Stereo delay effect
│       └── reverb_processor.hpp # Freeverb reverb
├── test/
│   └── test_alien4.cpp          # Test program
└── CMakeLists.txt               # Build configuration
```

## API Example

```cpp
#include "alien4_engine.hpp"

// Create engine
Alien4AudioEngine engine(48000.0f);

// Configure Documenta
engine.setRecording(true);
engine.setLooping(true);
engine.setMix(0.5f);         // 50% input, 50% loop
engine.setFeedback(0.3f);
engine.setSpeed(1.0f);

// Configure EQ
engine.setEQLow(3.0f);       // +3dB
engine.setEQMid(0.0f);       // 0dB
engine.setEQHigh(-3.0f);     // -3dB

// Configure Ellen Ripley
engine.setDelayTime(0.25f, 0.3f);
engine.setDelayFeedback(0.4f);
engine.setReverbRoom(0.7f);
engine.setReverbDamping(0.5f);
engine.setSendAmount(0.3f);  // 30% wet

// Process audio
float inputL[512], inputR[512];
float outputL[512], outputR[512];
engine.process(inputL, inputR, outputL, outputR, 512);
```

## Future Work

- [ ] Python bindings with Pybind11
- [ ] Slice detection and management
- [ ] Polyphonic output
- [ ] MIDI control integration
- [ ] Real-time audio I/O

## License

To be determined

## Author

Madzine - 2025
