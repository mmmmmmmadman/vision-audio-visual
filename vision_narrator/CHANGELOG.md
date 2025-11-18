# Changelog

## Future Plans

### VAV Integration
- **Target**: Integrate Vision Narrator into VAV main program
- **Purpose**: Provide real-time visual description and narration capabilities for VAV system
- **Integration Points**:
  - Camera capture module integration
  - Vision model inference pipeline
  - Multi-language TTS system
  - Audio playback and mixing functionality
- **Status**: Standalone development phase, integration pending

## [Unreleased] - 2025-01-17

### Added
- Audio caching system with MD5 hash-based file management
- Parallel audio generation for multilingual mode using asyncio.gather()
- Loop playback functionality to eliminate audio gaps during description generation
- Thread safety for MLX vision model inference with threading.Lock()

### Changed
- GUI text completely translated from Chinese to English
- Language options: Chinese Only, English Only, Japanese Only, Rotate, Random Mix
- FFmpeg mixing optimization: use minimum duration and longer segments (0.5-1.5s)
- Switched from non-blocking to blocking playback with audio looping

### Removed
- Volume fader UI component and all volume control functionality
- Background thread approach for TTS playback (replaced with loop playback)

### Fixed
- Metal command buffer crash when manually closing application
- Audio gaps in multilingual mix mode with continuous loop playback
- FFmpeg freezing issue by reducing segment count and increasing segment length
- Thread safety issues causing GPU command conflicts

### Technical Details
- Audio cache limit: 50 files with 20% LRU eviction
- MLX inference protected by vision_lock to prevent Metal crashes
- Loop playback continuously plays current audio until new audio is ready
- OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES environment variable for stability

## [Previous] - 2025-01-XX

### Initial Features
- Real-time vision description with SmolVLM (2B, 4-bit quantized)
- Multi-language TTS support (Chinese, English, Japanese)
- Edge-TTS integration for high-quality speech synthesis
- MLX-VLM backend for Apple Silicon optimization
- Camera capture with 640x480 resolution
- GUI interface with Tkinter
