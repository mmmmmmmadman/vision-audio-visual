/*
 * Alien4 C++ Extension for Python
 * Complete port of VCV Rack Alien4 module using pybind11
 *
 * Features:
 * - Loop buffer recording (2880000 samples, 60s @ 48kHz)
 * - Slice detection with dynamic threshold
 * - Polyphonic playback (1-8 voices)
 * - 3-band EQ (Low/Mid/High)
 * - Stereo delay with independent L/R times
 * - Reverb with comb/allpass filters
 * - Feedback routing
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <iostream>
#include <random>
#include <utility>

namespace py = pybind11;

// Helper functions
template<typename T>
inline T clamp(T value, T min, T max) {
    return std::max(min, std::min(max, value));
}

// ============================================================================
// Slice structure
// ============================================================================
struct Slice {
    int startSample = 0;
    int endSample = 0;
    float peakAmplitude = 0.0f;
    bool active = false;
};

// ============================================================================
// Voice structure for polyphonic playback
// ============================================================================
struct Voice {
    int sliceIndex = 0;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    float speedMultiplier = 1.0f;
};

// ============================================================================
// Biquad filter for EQ (cut-only, 0 to -20dB)
// ============================================================================
class BiquadFilter {
public:
    enum Type {
        LOWSHELF,
        PEAK,
        HIGHSHELF
    };

    BiquadFilter() : b0(1.0f), b1(0.0f), b2(0.0f), a1(0.0f), a2(0.0f),
                     z1(0.0f), z2(0.0f) {}

    void setParameters(Type type, float normalizedFreq, float Q, float gain) {
        float w0 = 2.0f * M_PI * normalizedFreq;
        float cosw0 = std::cos(w0);
        float sinw0 = std::sin(w0);
        float alpha = sinw0 / (2.0f * Q);
        float A = gain;

        float a0;

        if (type == LOWSHELF) {
            b0 = A * ((A + 1.0f) - (A - 1.0f) * cosw0 + 2.0f * std::sqrt(A) * alpha);
            b1 = 2.0f * A * ((A - 1.0f) - (A + 1.0f) * cosw0);
            b2 = A * ((A + 1.0f) - (A - 1.0f) * cosw0 - 2.0f * std::sqrt(A) * alpha);
            a0 = (A + 1.0f) + (A - 1.0f) * cosw0 + 2.0f * std::sqrt(A) * alpha;
            a1 = -2.0f * ((A - 1.0f) + (A + 1.0f) * cosw0);
            a2 = (A + 1.0f) + (A - 1.0f) * cosw0 - 2.0f * std::sqrt(A) * alpha;
        } else if (type == PEAK) {
            b0 = 1.0f + alpha * A;
            b1 = -2.0f * cosw0;
            b2 = 1.0f - alpha * A;
            a0 = 1.0f + alpha / A;
            a1 = -2.0f * cosw0;
            a2 = 1.0f - alpha / A;
        } else { // HIGHSHELF
            b0 = A * ((A + 1.0f) + (A - 1.0f) * cosw0 + 2.0f * std::sqrt(A) * alpha);
            b1 = -2.0f * A * ((A - 1.0f) + (A + 1.0f) * cosw0);
            b2 = A * ((A + 1.0f) + (A - 1.0f) * cosw0 - 2.0f * std::sqrt(A) * alpha);
            a0 = (A + 1.0f) - (A - 1.0f) * cosw0 + 2.0f * std::sqrt(A) * alpha;
            a1 = 2.0f * ((A - 1.0f) - (A + 1.0f) * cosw0);
            a2 = (A + 1.0f) - (A - 1.0f) * cosw0 - 2.0f * std::sqrt(A) * alpha;
        }

        // Normalize
        b0 /= a0;
        b1 /= a0;
        b2 /= a0;
        a1 /= a0;
        a2 /= a0;
    }

    float process(float input) {
        float output = b0 * input + z1;
        z1 = b1 * input - a1 * output + z2;
        z2 = b2 * input - a2 * output;
        return output;
    }

    void reset() {
        z1 = z2 = 0.0f;
    }

private:
    float b0, b1, b2, a1, a2;
    float z1, z2;
};

// ============================================================================
// Delay processor
// ============================================================================
class DelayProcessor {
public:
    static constexpr int DELAY_BUFFER_SIZE = 96000;

    DelayProcessor() {
        buffer.resize(DELAY_BUFFER_SIZE, 0.0f);
        writeIndex = 0;
    }

    void reset() {
        std::fill(buffer.begin(), buffer.end(), 0.0f);
        writeIndex = 0;
    }

    float process(float input, float delayTime, float feedback, float sampleRate) {
        int delaySamples = static_cast<int>(delayTime * sampleRate);
        delaySamples = clamp(delaySamples, 1, DELAY_BUFFER_SIZE - 1);

        int readIndex = (writeIndex - delaySamples + DELAY_BUFFER_SIZE) % DELAY_BUFFER_SIZE;
        float delayedSignal = buffer[readIndex];

        buffer[writeIndex] = input + delayedSignal * feedback;
        writeIndex = (writeIndex + 1) % DELAY_BUFFER_SIZE;

        return delayedSignal;
    }

private:
    std::vector<float> buffer;
    int writeIndex;
};

// ============================================================================
// Reverb processor (Freeverb-style with stereo spread)
// ============================================================================
class ReverbProcessor {
public:
    // Base sizes for left channel
    static constexpr int COMB_1_BASE = 1557;
    static constexpr int COMB_2_BASE = 1617;
    static constexpr int COMB_3_BASE = 1491;
    static constexpr int COMB_4_BASE = 1422;
    static constexpr int ALLPASS_1_BASE = 556;
    static constexpr int ALLPASS_2_BASE = 441;

    // Stereo spread offset (adds variation for right channel)
    static constexpr int STEREO_SPREAD = 23;

    ReverbProcessor(bool isRightChannel = false)
        : comb1Size(COMB_1_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
          comb2Size(COMB_2_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
          comb3Size(COMB_3_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
          comb4Size(COMB_4_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
          allpass1Size(ALLPASS_1_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
          allpass2Size(ALLPASS_2_BASE + (isRightChannel ? STEREO_SPREAD : 0))
    {
        combBuffer1.resize(comb1Size, 0.0f);
        combBuffer2.resize(comb2Size, 0.0f);
        combBuffer3.resize(comb3Size, 0.0f);
        combBuffer4.resize(comb4Size, 0.0f);
        allpassBuffer1.resize(allpass1Size, 0.0f);
        allpassBuffer2.resize(allpass2Size, 0.0f);
        reset();
    }

    void reset() {
        std::fill(combBuffer1.begin(), combBuffer1.end(), 0.0f);
        std::fill(combBuffer2.begin(), combBuffer2.end(), 0.0f);
        std::fill(combBuffer3.begin(), combBuffer3.end(), 0.0f);
        std::fill(combBuffer4.begin(), combBuffer4.end(), 0.0f);
        std::fill(allpassBuffer1.begin(), allpassBuffer1.end(), 0.0f);
        std::fill(allpassBuffer2.begin(), allpassBuffer2.end(), 0.0f);

        combIndex1 = combIndex2 = combIndex3 = combIndex4 = 0;
        allpassIndex1 = allpassIndex2 = 0;
        combLp1 = combLp2 = combLp3 = combLp4 = 0.0f;
        hpState = 0.0f;
    }

    float processComb(float input, std::vector<float>& buffer, int size,
                     int& index, float feedback, float& lp, float damping) {
        float output = buffer[index];
        lp = lp + (output - lp) * damping;
        buffer[index] = input + lp * feedback;
        index = (index + 1) % size;
        return output;
    }

    float processAllpass(float input, std::vector<float>& buffer, int size,
                        int& index, float gain) {
        float delayed = buffer[index];
        float output = -input * gain + delayed;
        buffer[index] = input + delayed * gain;
        index = (index + 1) % size;
        return output;
    }

    float process(float input, float roomSize, float damping, float decay, float sampleRate) {
        float feedback = 0.5f + decay * 0.485f;
        float dampingCoeff = 0.05f + damping * 0.9f;
        float roomScale = 0.3f + roomSize * 1.4f;

        float roomInput = input * roomScale;
        float combOut = 0.0f;

        combOut += processComb(roomInput, combBuffer1, comb1Size, combIndex1,
                              feedback, combLp1, dampingCoeff);
        combOut += processComb(roomInput, combBuffer2, comb2Size, combIndex2,
                              feedback, combLp2, dampingCoeff);
        combOut += processComb(roomInput, combBuffer3, comb3Size, combIndex3,
                              feedback, combLp3, dampingCoeff);
        combOut += processComb(roomInput, combBuffer4, comb4Size, combIndex4,
                              feedback, combLp4, dampingCoeff);

        combOut *= 0.25f;

        float diffused = combOut;
        diffused = processAllpass(diffused, allpassBuffer1, allpass1Size,
                                 allpassIndex1, 0.5f);
        diffused = processAllpass(diffused, allpassBuffer2, allpass2Size,
                                 allpassIndex2, 0.5f);

        // Highpass filter
        float hpCutoff = 100.0f / (sampleRate * 0.5f);
        hpCutoff = clamp(hpCutoff, 0.001f, 0.1f);
        hpState += (diffused - hpState) * hpCutoff;
        float hpOutput = diffused - hpState;

        return hpOutput;
    }

private:
    std::vector<float> combBuffer1, combBuffer2, combBuffer3, combBuffer4;
    std::vector<float> allpassBuffer1, allpassBuffer2;
    int combIndex1, combIndex2, combIndex3, combIndex4;
    int allpassIndex1, allpassIndex2;
    float combLp1, combLp2, combLp3, combLp4;
    float hpState;

    // Buffer sizes (different for L/R channels for stereo effect)
    int comb1Size, comb2Size, comb3Size, comb4Size;
    int allpass1Size, allpass2Size;
};

// ============================================================================
// Main AudioEngine class
// ============================================================================
class AudioEngine {
public:
    static constexpr int LOOP_BUFFER_SIZE = 2880000; // 60 seconds at 48kHz

    AudioEngine(double sample_rate)
        : sampleRate(sample_rate),
          loopBuffer(LOOP_BUFFER_SIZE, 0.0f),
          tempBuffer(LOOP_BUFFER_SIZE, 0.0f),
          randomEngine(std::random_device()()),
          reverbL(false),  // Left channel
          reverbR(true)    // Right channel with stereo spread
    {
        // Initialize default parameters
        isRecording = false;
        isLooping = true;

        scanValue = 0.0f;
        gateThresholdKnob = 0.2f; // Default 0.2 → ~0.008 threshold - good for medium audio
        mixValue = 0.0f;
        feedbackValue = 0.0f;
        speedValue = 1.0f;

        delayTimeL = 0.25f;
        delayTimeR = 0.25f;
        delayFeedback = 0.3f;
        delayWet = 0.0f;

        reverbRoom = 1.0f;
        reverbDamping = 1.0f;
        reverbDecay = 0.6f;
        reverbWet = 0.0f;

        numVoices = 1;
        voices.resize(1);

        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
        currentSliceIndex = 0;
        lastAmplitude = 0.0f;
        lastScanTargetIndex = -1;
        lastScanValue = -1.0f;

        tempRecordPosition = 0;
        tempRecordedLength = 0;
        tempLastAmplitude = 0.0f;

        lastOutputL = 0.0f;
        lastOutputR = 0.0f;

        // Initialize EQ parameters (cut-only: 0 to -20dB)
        eqLowDb = 0.0f;
        eqMidDb = 0.0f;
        eqHighDb = 0.0f;

        // Initialize smoothed parameters
        smoothMix = mixValue;
        smoothFeedback = feedbackValue;
        smoothSpeed = speedValue;
        smoothEqLow = eqLowDb;
        smoothEqMid = eqMidDb;
        smoothEqHigh = eqHighDb;
        smoothDelayTimeL = delayTimeL;
        smoothDelayTimeR = delayTimeR;
        smoothDelayFeedback = delayFeedback;
        smoothDelayWet = delayWet;
        smoothReverbRoom = reverbRoom;
        smoothReverbDamping = reverbDamping;
        smoothReverbDecay = reverbDecay;
        smoothReverbWet = reverbWet;
    }

    // ========================================================================
    // Recording control
    // ========================================================================
    void set_recording(bool enabled) {
        if (enabled == isRecording) return;

        if (enabled) {
            // Start recording
            std::fill(tempBuffer.begin(), tempBuffer.end(), 0.0f);
            tempSlices.clear();
            tempRecordPosition = 0;
            tempRecordedLength = 0;
            tempLastAmplitude = 0.0f;
            isRecording = true;
        } else {
            // Stop recording: finalize
            std::cout << "[DEBUG] Recording stopped: length=" << tempRecordedLength
                      << " samples (" << tempRecordedLength / sampleRate << "s)" << std::endl;

            // Copy temp to main
            std::copy(tempBuffer.begin(), tempBuffer.end(), loopBuffer.begin());
            recordedLength = tempRecordedLength;

            // Generate fixed-length slices based on current LENGTH parameter
            float sliceLength = getSliceLength();
            std::cout << "[DEBUG] Generating slices with length=" << sliceLength << "s" << std::endl;
            rescanSlices(sliceLength);
            playbackPosition = 0;
            playbackPhase = 0.0f;
            currentSliceIndex = 0;
            lastAmplitude = 0.0f;

            // Reset voices
            for (auto& v : voices) {
                v.sliceIndex = 0;
                v.playbackPosition = 0;
                v.playbackPhase = 0.0f;
                v.speedMultiplier = 1.0f;
            }

            // Redistribute if poly
            if (numVoices > 1) {
                redistributeVoices();
            }

            isRecording = false;
        }
    }

    void set_looping(bool enabled) {
        isLooping = enabled;
    }

    void clear() {
        std::fill(loopBuffer.begin(), loopBuffer.end(), 0.0f);
        std::fill(tempBuffer.begin(), tempBuffer.end(), 0.0f);
        slices.clear();
        tempSlices.clear();
        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
        currentSliceIndex = 0;
        lastAmplitude = 0.0f;
        lastScanTargetIndex = -1;
        tempRecordPosition = 0;
        tempRecordedLength = 0;
        tempLastAmplitude = 0.0f;
        lastOutputL = 0.0f;
        lastOutputR = 0.0f;

        delayL.reset();
        delayR.reset();
        reverbL.reset();
        reverbR.reset();

        // Reset EQ filters
        eqLowL.reset();
        eqLowR.reset();
        eqMidL.reset();
        eqMidR.reset();
        eqHighL.reset();
        eqHighR.reset();
    }

    // ========================================================================
    // Slice control
    // ========================================================================
    void set_scan(double value) {
        scanValue = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_gate_threshold(double value) {
        gateThresholdKnob = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_poly(int voices_count) {
        int newVoices = clamp(voices_count, 1, 8);
        if (newVoices != numVoices) {
            std::cout << "[DEBUG] POLY changed: " << numVoices << " -> " << newVoices
                      << " (slices=" << slices.size() << ", recorded=" << recordedLength << ")" << std::endl;
            numVoices = newVoices;
            voices.resize(numVoices);

            // Initialize all voices
            for (size_t i = 0; i < voices.size(); i++) {
                voices[i].sliceIndex = currentSliceIndex;
                voices[i].playbackPosition = playbackPosition;
                voices[i].playbackPhase = 0.0f;
                voices[i].speedMultiplier = 1.0f;
            }

            if (!slices.empty() && numVoices > 1) {
                // Redistribute voices to random slices
                redistributeVoices();
            } else if (slices.empty() && numVoices > 1 && recordedLength > 0) {
                // No slices but have recording: distribute voices evenly across buffer
                std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);
                for (int i = 1; i < numVoices; i++) {
                    voices[i].playbackPosition = (recordedLength * i) / numVoices;
                    voices[i].playbackPhase = 0.0f;
                    voices[i].speedMultiplier = speedDist(randomEngine);
                }
            }
        }
    }

    // ========================================================================
    // Debug / Query functions
    // ========================================================================
    int get_num_slices() const {
        return static_cast<int>(slices.size());
    }

    int get_num_voices() const {
        return numVoices;
    }

    int get_recorded_length() const {
        return recordedLength;
    }

    // ========================================================================
    // Documenta parameters
    // ========================================================================
    void set_mix(double value) {
        mixValue = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_feedback(double value) {
        // Limit to 0.8 with additional safety scaling in process()
        feedbackValue = clamp(static_cast<float>(value), 0.0f, 0.8f);
    }

    void set_speed(double value) {
        speedValue = clamp(static_cast<float>(value), -8.0f, 8.0f);
    }

    // ========================================================================
    // EQ parameters (cut-only: 0 to -20dB)
    // ========================================================================
    void set_eq_low(double db) {
        eqLowDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
    }

    void set_eq_mid(double db) {
        eqMidDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
    }

    void set_eq_high(double db) {
        eqHighDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
    }

    // ========================================================================
    // Delay parameters
    // ========================================================================
    void set_delay_time(double time_l, double time_r) {
        delayTimeL = clamp(static_cast<float>(time_l), 0.001f, 2.0f);
        delayTimeR = clamp(static_cast<float>(time_r), 0.001f, 2.0f);
    }

    void set_delay_feedback(double value) {
        delayFeedback = clamp(static_cast<float>(value), 0.0f, 0.95f);
    }

    void set_delay_wet(double value) {
        delayWet = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    // ========================================================================
    // Reverb parameters
    // ========================================================================
    void set_reverb_room(double value) {
        reverbRoom = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_reverb_damping(double value) {
        reverbDamping = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_reverb_decay(double value) {
        reverbDecay = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    void set_reverb_wet(double value) {
        reverbWet = clamp(static_cast<float>(value), 0.0f, 1.0f);
    }

    // ========================================================================
    // Process audio
    // ========================================================================
    std::pair<py::array_t<float>, py::array_t<float>>
    process(py::array_t<float> left_in, py::array_t<float> right_in) {
        auto left_buf = left_in.request();
        auto right_buf = right_in.request();

        if (left_buf.ndim != 1 || right_buf.ndim != 1) {
            throw std::runtime_error("Input arrays must be 1-dimensional");
        }

        size_t num_samples = left_buf.shape[0];
        if (right_buf.shape[0] != static_cast<ssize_t>(num_samples)) {
            throw std::runtime_error("Left and right inputs must have same length");
        }

        float* left_in_ptr = static_cast<float*>(left_buf.ptr);
        float* right_in_ptr = static_cast<float*>(right_buf.ptr);

        // Allocate output
        py::array_t<float> left_out(num_samples);
        py::array_t<float> right_out(num_samples);

        auto left_out_buf = left_out.request();
        auto right_out_buf = right_out.request();

        float* left_out_ptr = static_cast<float*>(left_out_buf.ptr);
        float* right_out_ptr = static_cast<float*>(right_out_buf.ptr);

        // ====================================================================
        // Pre-process: Check parameter changes (once per buffer, not per sample)
        // ====================================================================

        // Check if LENGTH or SCAN changed (both affect slicing)
        float sliceLength = getSliceLength();
        static float lastSliceLength = -1.0f;
        static float lastScanForSlicing = -1.0f;

        // Track LENGTH changes separately (don't trigger redistribution)
        bool lengthChanged = std::abs(sliceLength - lastSliceLength) > 0.0001f;
        // Track SCAN changes separately (do trigger redistribution for Seq1 control)
        bool scanChanged = std::abs(scanValue - lastScanForSlicing) > 0.001f;

        if (!isRecording && recordedLength > 0 && (lengthChanged || scanChanged)) {
            std::cout << "[DEBUG] LENGTH or SCAN changed: length=" << sliceLength
                      << "s, scan=" << scanValue << std::endl;
            rescanSlices(sliceLength);
            lastSliceLength = sliceLength;
            lastScanForSlicing = scanValue;

            // After rescan, ensure voice 0 is still valid
            if (numVoices > 1 && !voices.empty() && !slices.empty()) {
                // Keep voice 0 on a valid slice
                if (currentSliceIndex >= static_cast<int>(slices.size())) {
                    currentSliceIndex = 0;
                }
                voices[0].sliceIndex = currentSliceIndex;
                voices[0].playbackPosition = slices[currentSliceIndex].startSample;
                voices[0].playbackPhase = 0.0f;
            }

            // Only SCAN triggers redistribution (for Seq1 control), not LENGTH
            if (scanChanged) {
                redistributeVoices();
            }
        }

        // Apply SCAN parameter to jump to target slice
        if (slices.size() > 1) {
            bool useManualScan = scanValue > 0.01f;

            if (useManualScan) {
                int targetSliceIndex = static_cast<int>(
                    std::round(scanValue * (slices.size() - 1)));
                targetSliceIndex = clamp(targetSliceIndex, 0,
                                       static_cast<int>(slices.size()) - 1);

                if (targetSliceIndex != lastScanTargetIndex &&
                    slices[targetSliceIndex].active) {
                    currentSliceIndex = targetSliceIndex;
                    playbackPosition = slices[targetSliceIndex].startSample;
                    playbackPhase = 0.0f;
                    lastScanTargetIndex = targetSliceIndex;

                    if (numVoices > 1 && !voices.empty()) {
                        voices[0].sliceIndex = targetSliceIndex;
                        voices[0].playbackPosition = slices[targetSliceIndex].startSample;
                        voices[0].playbackPhase = 0.0f;
                    }
                }
            } else {
                lastScanTargetIndex = -1;
            }
        }

        // ====================================================================
        // Smooth parameters (per-buffer)
        // ====================================================================
        const float smoothFactor = 0.2f;  // Smoothing coefficient (higher = faster response)
        const float delayTimeSmoothFactor = 0.05f;  // Much slower for delay time to prevent clicks

        smoothMix += (mixValue - smoothMix) * smoothFactor;
        smoothFeedback += (feedbackValue - smoothFeedback) * smoothFactor;
        smoothSpeed += (speedValue - smoothSpeed) * smoothFactor;
        smoothEqLow += (eqLowDb - smoothEqLow) * smoothFactor;
        smoothEqMid += (eqMidDb - smoothEqMid) * smoothFactor;
        smoothEqHigh += (eqHighDb - smoothEqHigh) * smoothFactor;
        smoothDelayTimeL += (delayTimeL - smoothDelayTimeL) * delayTimeSmoothFactor;
        smoothDelayTimeR += (delayTimeR - smoothDelayTimeR) * delayTimeSmoothFactor;
        smoothDelayFeedback += (delayFeedback - smoothDelayFeedback) * smoothFactor;
        smoothDelayWet += (delayWet - smoothDelayWet) * smoothFactor;
        smoothReverbRoom += (reverbRoom - smoothReverbRoom) * smoothFactor;
        smoothReverbDamping += (reverbDamping - smoothReverbDamping) * smoothFactor;
        smoothReverbDecay += (reverbDecay - smoothReverbDecay) * smoothFactor;
        smoothReverbWet += (reverbWet - smoothReverbWet) * smoothFactor;

        // ====================================================================
        // Update EQ parameters (outside sample loop to prevent instability)
        // ====================================================================
        // Clamp EQ gains to safe range (cut-only: 0 to -20dB) and convert dB to linear gain
        float clampedEqLow = clamp(smoothEqLow, -20.0f, 0.0f);
        float clampedEqMid = clamp(smoothEqMid, -20.0f, 0.0f);
        float clampedEqHigh = clamp(smoothEqHigh, -20.0f, 0.0f);

        float eqLowGain = std::pow(10.0f, clampedEqLow / 20.0f);
        float eqMidGain = std::pow(10.0f, clampedEqMid / 20.0f);
        float eqHighGain = std::pow(10.0f, clampedEqHigh / 20.0f);

        // Update filter coefficients once per buffer
        // Low: 200Hz lowshelf, Mid: 2kHz peaking, High: 8kHz highshelf
        eqLowL.setParameters(BiquadFilter::LOWSHELF, 200.0f / sampleRate, 0.707f, eqLowGain);
        eqLowR.setParameters(BiquadFilter::LOWSHELF, 200.0f / sampleRate, 0.707f, eqLowGain);
        eqMidL.setParameters(BiquadFilter::PEAK, 2000.0f / sampleRate, 0.707f, eqMidGain);
        eqMidR.setParameters(BiquadFilter::PEAK, 2000.0f / sampleRate, 0.707f, eqMidGain);
        eqHighL.setParameters(BiquadFilter::HIGHSHELF, 8000.0f / sampleRate, 0.707f, eqHighGain);
        eqHighR.setParameters(BiquadFilter::HIGHSHELF, 8000.0f / sampleRate, 0.707f, eqHighGain);

        // ====================================================================
        // Process each sample
        // ====================================================================
        for (size_t i = 0; i < num_samples; i++) {
            float input = left_in_ptr[i]; // Mono input

            // Recording (no slice detection during recording - done after stop)
            if (isRecording && tempRecordPosition < LOOP_BUFFER_SIZE) {
                tempBuffer[tempRecordPosition] = input;
                tempRecordedLength = tempRecordPosition + 1;
                tempRecordPosition++;
            }

            // Playback
            float loopL = 0.0f;
            float loopR = 0.0f;

            if (recordedLength > 0) {
                bool isReverse = smoothSpeed < 0.0f;

                if (numVoices == 1) {
                    // Single voice mode
                    playbackPhase += smoothSpeed;
                    int positionDelta = static_cast<int>(playbackPhase);
                    playbackPhase -= static_cast<float>(positionDelta);
                    playbackPosition += positionDelta;

                    // Loop current slice
                    if (!slices.empty() && currentSliceIndex < static_cast<int>(slices.size())
                        && slices[currentSliceIndex].active) {
                        int sliceStart = slices[currentSliceIndex].startSample;
                        int sliceEnd = slices[currentSliceIndex].endSample;

                        if (isReverse) {
                            if (playbackPosition < sliceStart) {
                                playbackPosition = sliceEnd;
                            }
                        } else {
                            if (playbackPosition > sliceEnd) {
                                playbackPosition = sliceStart;
                            }
                        }
                    } else {
                        // No slices: loop entire buffer
                        if (isReverse) {
                            if (playbackPosition < 0) {
                                playbackPosition = recordedLength - 1;
                            }
                        } else {
                            if (playbackPosition >= recordedLength) {
                                playbackPosition = 0;
                            }
                        }
                    }

                    // Read with interpolation
                    if (recordedLength > 0) {
                        playbackPosition = clamp(playbackPosition, 0, recordedLength - 1);
                        int pos0 = playbackPosition;
                        int pos1 = (recordedLength > 1) ? ((pos0 + 1) % recordedLength) : pos0;

                        pos0 = clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
                        pos1 = clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

                        float frac = clamp(std::abs(playbackPhase), 0.0f, 1.0f);

                        float sample = loopBuffer[pos0] * (1.0f - frac) +
                                     loopBuffer[pos1] * frac;
                        loopL = sample;
                        loopR = sample;
                    }
                } else {
                    // Multiple voices mode
                    for (int v = 0; v < numVoices; v++) {
                        float voiceSpeed = smoothSpeed * voices[v].speedMultiplier;
                        voiceSpeed = clamp(voiceSpeed, -16.0f, 16.0f);
                        voices[v].playbackPhase += voiceSpeed;

                        int positionDelta = static_cast<int>(voices[v].playbackPhase);
                        voices[v].playbackPhase -= static_cast<float>(positionDelta);
                        voices[v].playbackPosition += positionDelta;

                        // Loop current slice for each voice
                        if (!slices.empty() && voices[v].sliceIndex < static_cast<int>(slices.size())
                            && slices[voices[v].sliceIndex].active) {
                            int sliceStart = slices[voices[v].sliceIndex].startSample;
                            int sliceEnd = slices[voices[v].sliceIndex].endSample;

                            bool voiceReverse = voiceSpeed < 0.0f;
                            if (voiceReverse) {
                                if (voices[v].playbackPosition < sliceStart) {
                                    voices[v].playbackPosition = sliceEnd;
                                }
                            } else {
                                if (voices[v].playbackPosition > sliceEnd) {
                                    voices[v].playbackPosition = sliceStart;
                                }
                            }
                        } else {
                            // No valid slice: loop entire buffer
                            bool voiceReverse = voiceSpeed < 0.0f;
                            if (voiceReverse) {
                                if (voices[v].playbackPosition < 0) {
                                    voices[v].playbackPosition = recordedLength - 1;
                                }
                            } else {
                                if (voices[v].playbackPosition >= recordedLength) {
                                    voices[v].playbackPosition = 0;
                                }
                            }
                        }

                        // Read with interpolation
                        if (recordedLength > 0) {
                            voices[v].playbackPosition = clamp(voices[v].playbackPosition,
                                                              0, recordedLength - 1);
                            int pos0 = voices[v].playbackPosition;
                            int pos1 = (recordedLength > 1) ? ((pos0 + 1) % recordedLength) : pos0;

                            pos0 = clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
                            pos1 = clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

                            float frac = clamp(std::abs(voices[v].playbackPhase), 0.0f, 1.0f);

                            float sample = loopBuffer[pos0] * (1.0f - frac) +
                                         loopBuffer[pos1] * frac;

                            if (std::isfinite(sample)) {
                                // Fixed stereo pan distribution:
                                // Voice 0: Center, 1: 25%L, 2: 25%R, 3: 50%L, 4: 50%R, 5: 75%L, 6: 75%R, 7: 100%L
                                float panL, panR;

                                switch(v) {
                                    case 0: panL = 0.5f;   panR = 0.5f;   break;  // Center
                                    case 1: panL = 0.75f;  panR = 0.25f;  break;  // 25% Left
                                    case 2: panL = 0.25f;  panR = 0.75f;  break;  // 25% Right
                                    case 3: panL = 1.0f;   panR = 0.0f;   break;  // 50% Left (full L)
                                    case 4: panL = 0.0f;   panR = 1.0f;   break;  // 50% Right (full R)
                                    case 5: panL = 0.875f; panR = 0.125f; break;  // 75% Left
                                    case 6: panL = 0.125f; panR = 0.875f; break;  // 75% Right
                                    case 7: panL = 1.0f;   panR = 0.0f;   break;  // 100% Left
                                    default: panL = 0.5f;  panR = 0.5f;   break;  // Fallback: center
                                }

                                loopL += sample * panL;
                                loopR += sample * panR;
                            }
                        }
                    }

                    // Normalize by RMS energy per channel
                    float totalEnergyL = 0.0f;
                    float totalEnergyR = 0.0f;

                    for (int v = 0; v < numVoices && v < 8; v++) {
                        float panL, panR;
                        switch(v) {
                            case 0: panL = 0.5f;   panR = 0.5f;   break;
                            case 1: panL = 0.75f;  panR = 0.25f;  break;
                            case 2: panL = 0.25f;  panR = 0.75f;  break;
                            case 3: panL = 1.0f;   panR = 0.0f;   break;
                            case 4: panL = 0.0f;   panR = 1.0f;   break;
                            case 5: panL = 0.875f; panR = 0.125f; break;
                            case 6: panL = 0.125f; panR = 0.875f; break;
                            case 7: panL = 1.0f;   panR = 0.0f;   break;
                            default: panL = 0.5f;  panR = 0.5f;   break;
                        }
                        totalEnergyL += panL * panL;
                        totalEnergyR += panR * panR;
                    }

                    if (totalEnergyL > 0.0f) loopL /= std::sqrt(totalEnergyL);
                    if (totalEnergyR > 0.0f) loopR /= std::sqrt(totalEnergyR);

                    // Update layer position to voice 0
                    if (!voices.empty()) {
                        playbackPosition = voices[0].playbackPosition;
                        playbackPhase = voices[0].playbackPhase;
                        currentSliceIndex = voices[0].sliceIndex;
                    }
                }
            }

            // MIX control
            float mixedL = input * (1.0f - smoothMix) + loopL * smoothMix;
            float mixedR = input * (1.0f - smoothMix) + loopR * smoothMix;

            // FEEDBACK (with 0.8x safety scaling)
            float fbL = std::tanh(lastOutputL * 0.3f) / 0.3f;
            float fbR = std::tanh(lastOutputR * 0.3f) / 0.3f;

            // Apply 0.8x scaling for additional safety margin
            mixedL += fbL * smoothFeedback * 0.8f;
            mixedR += fbR * smoothFeedback * 0.8f;

            // 3-Band EQ - just process, parameters are set outside loop
            float eqL = eqLowL.process(mixedL);
            eqL = eqMidL.process(eqL);
            eqL = eqHighL.process(eqL);

            float eqR = eqLowR.process(mixedR);
            eqR = eqMidR.process(eqR);
            eqR = eqHighR.process(eqR);

            // Delay processing - ensure true stereo independence
            // Process left channel delay with left-specific parameters
            float delayedL = delayL.process(eqL, smoothDelayTimeL, smoothDelayFeedback, sampleRate);

            // Process right channel delay with right-specific parameters
            float delayedR = delayR.process(eqR, smoothDelayTimeR, smoothDelayFeedback, sampleRate);

            // Mix delayed signals independently for each channel
            float delayMixL = eqL * (1.0f - smoothDelayWet) + delayedL * smoothDelayWet;
            float delayMixR = eqR * (1.0f - smoothDelayWet) + delayedR * smoothDelayWet;

            // Reverb processing
            float reverbedL = reverbL.process(delayMixL, smoothReverbRoom, smoothReverbDamping,
                                             smoothReverbDecay, sampleRate);
            float reverbedR = reverbR.process(delayMixR, smoothReverbRoom, smoothReverbDamping,
                                             smoothReverbDecay, sampleRate);

            float outputL = delayMixL * (1.0f - smoothReverbWet) + reverbedL * smoothReverbWet;
            float outputR = delayMixR * (1.0f - smoothReverbWet) + reverbedR * smoothReverbWet;

            // Store for feedback
            lastOutputL = outputL;
            lastOutputR = outputR;

            // Output (clamp to safe range)
            left_out_ptr[i] = clamp(outputL, -10.0f, 10.0f);
            right_out_ptr[i] = clamp(outputR, -10.0f, 10.0f);
        }

        return std::make_pair(left_out, right_out);
    }

private:
    double sampleRate;

    // Loop buffer
    std::vector<float> loopBuffer;
    int playbackPosition;
    float playbackPhase;
    int recordedLength;
    int currentSliceIndex;
    float lastAmplitude;
    int lastScanTargetIndex;

    // Temp buffer (during recording)
    std::vector<float> tempBuffer;
    std::vector<Slice> tempSlices;
    int tempRecordPosition;
    int tempRecordedLength;
    float tempLastAmplitude;

    // Slices
    std::vector<Slice> slices;

    // Polyphonic voices
    std::vector<Voice> voices;
    int numVoices;
    std::default_random_engine randomEngine;
    float lastScanValue;

    // EQ filters (stereo, cut-only)
    BiquadFilter eqLowL, eqLowR;
    BiquadFilter eqMidL, eqMidR;
    BiquadFilter eqHighL, eqHighR;

    // Effects processors
    DelayProcessor delayL, delayR;
    ReverbProcessor reverbL, reverbR;

    // State
    bool isRecording;
    bool isLooping;

    // Feedback state
    float lastOutputL;
    float lastOutputR;

    // Parameters (target values)
    float scanValue;
    float gateThresholdKnob;  // Renamed from minSliceTimeKnob
    float mixValue;
    float feedbackValue;
    float speedValue;
    float eqLowDb, eqMidDb, eqHighDb;  // Cut-only: 0 to -20dB
    float delayTimeL, delayTimeR, delayFeedback, delayWet;
    float reverbRoom, reverbDamping, reverbDecay, reverbWet;

    // Smoothed parameters (current values)
    float smoothMix, smoothFeedback, smoothSpeed;
    float smoothEqLow, smoothEqMid, smoothEqHigh;
    float smoothDelayTimeL, smoothDelayTimeR, smoothDelayFeedback, smoothDelayWet;
    float smoothReverbRoom, smoothReverbDamping, smoothReverbDecay, smoothReverbWet;

    // Convert LENGTH knob value (0-1) to actual slice length in seconds (0.001-5.0s)
    // Lower values = shorter slices (more slices)
    // Higher values = longer slices (fewer slices)
    float getSliceLength() {
        // Exponential mapping for better control
        // 0.0 → 0.001s  (1ms, very short)
        // ~0.48 → 0.5s   (500ms, medium)
        // 1.0 → 5.0s   (5 seconds, very long)
        return 0.001f * std::pow(5000.0f, gateThresholdKnob);
    }

    void rescanSlices(float sliceLength) {
        if (recordedLength <= 0) return;

        slices.clear();

        // Fixed-length slicing: divide recording into equal-length slices
        // SCAN parameter determines starting offset (0.0 = start, 1.0 = end)
        int sliceLengthSamples = static_cast<int>(sliceLength * sampleRate);

        // SCAN offset: shift starting position within first slice
        int scanOffsetSamples = static_cast<int>(scanValue * sliceLengthSamples);
        if (scanOffsetSamples >= recordedLength) {
            scanOffsetSamples = recordedLength - 1;
        }

        // Create slices starting from scan offset
        int pos = scanOffsetSamples;

        while (pos < recordedLength) {
            int sliceStart = pos;
            int sliceEnd = std::min(pos + sliceLengthSamples - 1, recordedLength - 1);

            // Calculate peak amplitude for this slice
            float peakAmp = 0.0f;
            for (int i = sliceStart; i <= sliceEnd; i++) {
                peakAmp = std::max(peakAmp, std::abs(loopBuffer[i]));
            }

            Slice newSlice;
            newSlice.startSample = sliceStart;
            newSlice.endSample = sliceEnd;
            newSlice.active = true;
            newSlice.peakAmplitude = peakAmp;
            slices.push_back(newSlice);

            pos += sliceLengthSamples;
        }

        // If scan offset > 0, also create slice for the beginning part (wrap around)
        if (scanOffsetSamples > 0) {
            int wrapStart = 0;
            int wrapEnd = std::min(scanOffsetSamples - 1, recordedLength - 1);

            float peakAmp = 0.0f;
            for (int i = wrapStart; i <= wrapEnd; i++) {
                peakAmp = std::max(peakAmp, std::abs(loopBuffer[i]));
            }

            Slice wrapSlice;
            wrapSlice.startSample = wrapStart;
            wrapSlice.endSample = wrapEnd;
            wrapSlice.active = true;
            wrapSlice.peakAmplitude = peakAmp;
            slices.push_back(wrapSlice);
        }

        std::cout << "[DEBUG] rescanSlices: sliceLength=" << sliceLength << "s"
                  << ", scan=" << scanValue << " (offset=" << scanOffsetSamples << " samples)"
                  << ", found " << slices.size() << " slices";

        if (!slices.empty() && slices.size() <= 10) {
            std::cout << " [lengths: ";
            for (const auto& s : slices) {
                float len = (s.endSample - s.startSample + 1) / sampleRate;
                std::cout << len << "s ";
            }
            std::cout << "]";
        }
        std::cout << std::endl;

        if (currentSliceIndex >= static_cast<int>(slices.size())) {
            currentSliceIndex = slices.empty() ? 0 : static_cast<int>(slices.size()) - 1;
        }
    }

    void redistributeVoices() {
        if (slices.empty() || numVoices <= 1 || voices.empty()) return;

        std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
        std::uniform_real_distribution<float> speedDist(-4.0f, 4.0f);

        for (int i = 1; i < numVoices; i++) {
            int targetSliceIndex = sliceDist(randomEngine);
            int attempts = 0;
            while (attempts < 20 && (!slices[targetSliceIndex].active ||
                   slices[targetSliceIndex].startSample >= recordedLength)) {
                targetSliceIndex = sliceDist(randomEngine);
                attempts++;
            }

            if (!slices[targetSliceIndex].active ||
                slices[targetSliceIndex].startSample >= recordedLength) {
                continue;
            }

            voices[i].sliceIndex = targetSliceIndex;
            voices[i].playbackPosition = slices[targetSliceIndex].startSample;
            voices[i].playbackPhase = 0.0f;
            voices[i].speedMultiplier = speedDist(randomEngine);
        }
    }
};

// ============================================================================
// pybind11 bindings
// ============================================================================
PYBIND11_MODULE(alien4, m) {
    m.doc() = "Alien4 Audio Engine - Complete VCV Rack port";

    py::class_<AudioEngine>(m, "AudioEngine")
        .def(py::init<double>(), py::arg("sample_rate") = 48000.0,
             "Create AudioEngine with specified sample rate")

        // Recording control
        .def("set_recording", &AudioEngine::set_recording,
             py::arg("enabled"),
             "Enable/disable recording")
        .def("set_looping", &AudioEngine::set_looping,
             py::arg("enabled"),
             "Enable/disable looping")
        .def("clear", &AudioEngine::clear,
             "Clear all buffers and reset state")

        // Slice control
        .def("set_scan", &AudioEngine::set_scan,
             py::arg("value"),
             "Set slice scan position (0.0-1.0)")
        .def("set_gate_threshold", &AudioEngine::set_gate_threshold,
             py::arg("value"),
             "Set gate threshold knob (0.0-1.0, lower=more sensitive)")
        .def("set_poly", &AudioEngine::set_poly,
             py::arg("voices"),
             "Set number of polyphonic voices (1-8)")

        // Documenta parameters
        .def("set_mix", &AudioEngine::set_mix,
             py::arg("value"),
             "Set dry/wet mix (0.0-1.0)")
        .def("set_feedback", &AudioEngine::set_feedback,
             py::arg("value"),
             "Set feedback amount (0.0-1.0)")
        .def("set_speed", &AudioEngine::set_speed,
             py::arg("value"),
             "Set playback speed (-8.0 to +8.0)")
        .def("set_eq_low", &AudioEngine::set_eq_low,
             py::arg("db"),
             "Set low EQ gain (-20 to +20 dB)")
        .def("set_eq_mid", &AudioEngine::set_eq_mid,
             py::arg("db"),
             "Set mid EQ gain (-20 to +20 dB)")
        .def("set_eq_high", &AudioEngine::set_eq_high,
             py::arg("db"),
             "Set high EQ gain (-20 to +20 dB)")

        // Delay parameters
        .def("set_delay_time", &AudioEngine::set_delay_time,
             py::arg("time_l"), py::arg("time_r"),
             "Set delay times L/R (0.001-2.0 seconds)")
        .def("set_delay_feedback", &AudioEngine::set_delay_feedback,
             py::arg("value"),
             "Set delay feedback (0.0-0.95)")
        .def("set_delay_wet", &AudioEngine::set_delay_wet,
             py::arg("value"),
             "Set delay wet/dry mix (0.0-1.0)")

        // Reverb parameters
        .def("set_reverb_room", &AudioEngine::set_reverb_room,
             py::arg("value"),
             "Set reverb room size (0.0-1.0)")
        .def("set_reverb_damping", &AudioEngine::set_reverb_damping,
             py::arg("value"),
             "Set reverb damping (0.0-1.0)")
        .def("set_reverb_decay", &AudioEngine::set_reverb_decay,
             py::arg("value"),
             "Set reverb decay (0.0-1.0)")
        .def("set_reverb_wet", &AudioEngine::set_reverb_wet,
             py::arg("value"),
             "Set reverb wet/dry mix (0.0-1.0)")

        // Process audio
        .def("process", &AudioEngine::process,
             py::arg("left_in"), py::arg("right_in"),
             "Process audio buffers. Returns (left_out, right_out)")

        // Debug / query functions
        .def("get_num_slices", &AudioEngine::get_num_slices,
             "Get number of detected slices")
        .def("get_num_voices", &AudioEngine::get_num_voices,
             "Get current number of voices")
        .def("get_recorded_length", &AudioEngine::get_recorded_length,
             "Get recorded buffer length in samples");

    m.attr("__version__") = "1.0.0";
    m.attr("LOOP_BUFFER_SIZE") = AudioEngine::LOOP_BUFFER_SIZE;
}
