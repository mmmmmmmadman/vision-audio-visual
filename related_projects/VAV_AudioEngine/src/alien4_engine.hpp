#pragma once

#include "three_band_eq.hpp"
#include "ripley/stereo_delay.hpp"
#include "ripley/reverb_processor.hpp"
#include <vector>
#include <algorithm>
#include <cmath>
#include <random>

/**
 * Slice structure (from VCV Rack Alien4.cpp)
 */
struct Slice {
    int startSample = 0;
    int endSample = 0;
    float peakAmplitude = 0.0f;
    bool active = false;
};

/**
 * Voice structure for polyphonic playback (from VCV Rack Alien4.cpp)
 */
struct Voice {
    int sliceIndex = 0;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    float speedMultiplier = 1.0f;
};

/**
 * Alien4AudioEngine - Complete VCV Rack Alien4 port
 *
 * Signal Flow:
 * Input → REC/LOOP → MIX → FDBK → 3-Band EQ → Delay → Reverb → Output
 */
class Alien4AudioEngine {
private:
    float sampleRate;

    // Loop buffer (mono input, stereo playback)
    static constexpr int LOOP_BUFFER_SIZE = 2880000; // 60 seconds at 48kHz
    std::vector<float> loopBuffer;
    int playbackPosition;
    float playbackPhase;
    int recordedLength;
    int lastScanTargetIndex;

    // Temporary recording buffer (mono)
    std::vector<float> tempBuffer;
    std::vector<Slice> tempSlices;
    int tempRecordPosition;
    int tempRecordedLength;
    float tempLastAmplitude;

    // Slices
    std::vector<Slice> slices;
    int currentSliceIndex;
    float lastAmplitude;
    float lastMinSliceTime;

    // Polyphonic voices
    std::vector<Voice> voices;
    int numVoices;
    std::default_random_engine randomEngine;
    float lastScanValue;

    // State
    bool isRecording;
    bool looping;
    float minSliceTime;
    float scanValue;  // 0.0 to 1.0
    float feedbackAmount;
    float mixAmount;  // 0=input, 1=loop
    float speed;      // -8.0 to +8.0

    // Feedback buffer (stereo)
    float lastOutputL;
    float lastOutputR;

    // 3-Band EQ
    ThreeBandEQ eq;

    // Effects
    StereoDelay delay;
    ReverbProcessor reverb;
    float delayWet;   // Delay wet/dry mix (0=dry, 1=wet)
    float reverbWet;  // Reverb wet/dry mix (0=dry, 1=wet)

    // Helper: Convert MIN_SLICE_TIME knob value (0-1) to actual time (0.001-5.0 seconds)
    float getMinSliceTime(float knobValue) {
        if (knobValue <= 0.5f) {
            // Left half: exponential from 0.001 to 1.0
            float t = knobValue * 2.0f; // 0 to 1
            return 0.001f * std::pow(1000.0f, t); // 0.001 to 1.0
        } else {
            // Right half: linear from 1.0 to 5.0
            float t = (knobValue - 0.5f) * 2.0f; // 0 to 1
            return 1.0f + t * 4.0f; // 1.0 to 5.0
        }
    }

    // Clamp utility
    template<typename T>
    T clamp(T value, T min, T max) {
        return std::max(min, std::min(value, max));
    }

public:
    Alien4AudioEngine(float sr = 48000.0f)
        : sampleRate(sr), playbackPosition(0), playbackPhase(0.0f), recordedLength(0),
          lastScanTargetIndex(-1), tempRecordPosition(0), tempRecordedLength(0),
          tempLastAmplitude(0.0f), currentSliceIndex(0), lastAmplitude(0.0f),
          lastMinSliceTime(0.05f), numVoices(1), lastScanValue(-1.0f),
          isRecording(false), looping(true), minSliceTime(0.05f), scanValue(0.0f),
          feedbackAmount(0.0f), mixAmount(0.5f), speed(1.0f),
          lastOutputL(0.0f), lastOutputR(0.0f),
          eq(sr), delay(sr), reverb(sr), delayWet(0.0f), reverbWet(0.0f) {

        // Initialize buffers
        loopBuffer.resize(LOOP_BUFFER_SIZE, 0.0f);
        tempBuffer.resize(LOOP_BUFFER_SIZE, 0.0f);

        // Initialize random engine
        randomEngine.seed(std::random_device()());
    }

    /**
     * Rescan slices with threshold detection
     * From Alien4.cpp lines 351-399
     */
    void rescanSlices(float threshold, float minSliceTimeSec) {
        if (recordedLength <= 0) return;

        slices.clear();
        int minSliceSamples = (int)(minSliceTimeSec * sampleRate);
        float lastAmp = 0.0f;

        for (int pos = 0; pos < recordedLength; pos++) {
            float currentAmp = std::abs(loopBuffer[pos]);

            if (lastAmp < threshold && currentAmp >= threshold) {
                if (!slices.empty() && slices.back().active) {
                    int sliceLength = pos - slices.back().startSample;
                    if (sliceLength >= minSliceSamples) {
                        slices.back().endSample = pos - 1;
                    } else {
                        slices.pop_back();
                    }
                }

                if (slices.empty() || slices.back().endSample > 0) {
                    Slice newSlice;
                    newSlice.startSample = pos;
                    newSlice.active = true;
                    newSlice.peakAmplitude = 0.0f;
                    slices.push_back(newSlice);
                }
            }

            if (!slices.empty() && slices.back().active && slices.back().endSample == 0) {
                slices.back().peakAmplitude = std::max(slices.back().peakAmplitude, currentAmp);
            }

            lastAmp = currentAmp;
        }

        if (!slices.empty() && slices.back().active && slices.back().endSample == 0) {
            int sliceLength = recordedLength - slices.back().startSample;
            if (sliceLength >= minSliceSamples) {
                slices.back().endSample = recordedLength - 1;
            } else {
                slices.pop_back();
            }
        }

        if (currentSliceIndex >= (int)slices.size()) {
            currentSliceIndex = slices.empty() ? 0 : (int)slices.size() - 1;
        }
    }

    /**
     * Redistribute voices across slices
     * From Alien4.cpp lines 417-444
     */
    void redistributeVoices() {
        if (slices.empty() || numVoices <= 1 || voices.empty()) return;

        std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
        std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

        for (int i = 1; i < numVoices; i++) {
            // Find a valid active slice
            int targetSliceIndex = sliceDist(randomEngine);
            int attempts = 0;
            while (attempts < 20 && (!slices[targetSliceIndex].active ||
                   slices[targetSliceIndex].startSample >= recordedLength)) {
                targetSliceIndex = sliceDist(randomEngine);
                attempts++;
            }

            // Safety check
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

    // === Parameters ===
    void setRecording(bool rec) {
        if (rec && !isRecording) {
            // Start recording: clear temp buffer
            std::fill(tempBuffer.begin(), tempBuffer.end(), 0.0f);
            tempSlices.clear();
            tempRecordPosition = 0;
            tempRecordedLength = 0;
            tempLastAmplitude = 0.0f;
            isRecording = true;
        } else if (!rec && isRecording) {
            // Stop recording: finalize
            float minSliceTimeSec = getMinSliceTime(minSliceTime);
            int minSliceSamples = (int)(minSliceTimeSec * sampleRate);

            // Close the last slice if it exists and is still open
            if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                int sliceLength = tempRecordedLength - tempSlices.back().startSample;
                if (sliceLength >= minSliceSamples) {
                    tempSlices.back().endSample = tempRecordedLength - 1;
                } else {
                    tempSlices.pop_back();
                }
            }

            std::copy(tempBuffer.begin(), tempBuffer.end(), loopBuffer.begin());
            slices = tempSlices;
            recordedLength = tempRecordedLength;
            playbackPosition = 0;
            playbackPhase = 0.0f;
            currentSliceIndex = 0;
            lastAmplitude = 0.0f;

            // Reset all voices to valid initial state
            for (int i = 0; i < (int)voices.size(); i++) {
                voices[i].sliceIndex = 0;
                voices[i].playbackPosition = 0;
                voices[i].playbackPhase = 0.0f;
                voices[i].speedMultiplier = 1.0f;
            }

            // Redistribute voices if in poly mode
            if (numVoices > 1) {
                redistributeVoices();
            }

            isRecording = false;
        }
    }

    void setLooping(bool loop) { looping = loop; }

    void setMinSliceTime(float time) {
        minSliceTime = clamp(time, 0.0f, 1.0f);
        float actualTime = getMinSliceTime(minSliceTime);
        if (!isRecording && recordedLength > 0 && std::abs(actualTime - lastMinSliceTime) > 0.001f) {
            rescanSlices(0.5f, actualTime);
            redistributeVoices();
            lastMinSliceTime = actualTime;
        }
    }

    void setScan(float scan) {
        scanValue = clamp(scan, 0.0f, 1.0f);
        // Check if SCAN value changed
        if (std::abs(scanValue - lastScanValue) > 0.001f) {
            redistributeVoices();
            lastScanValue = scanValue;
        }
    }

    void setFeedback(float amount) { feedbackAmount = clamp(amount, 0.0f, 0.95f); }
    void setMix(float mix) { mixAmount = clamp(mix, 0.0f, 1.0f); }
    void setSpeed(float spd) { speed = clamp(spd, -8.0f, 8.0f); }

    void setPolyVoices(int voices_count) {
        int newNumVoices = clamp(voices_count, 1, 8);

        if (newNumVoices != numVoices) {
            numVoices = newNumVoices;
            voices.resize(numVoices);

            if (!slices.empty() && numVoices > 1) {
                std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
                std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

                for (int i = 0; i < numVoices; i++) {
                    if (i == 0) {
                        voices[i].sliceIndex = currentSliceIndex;
                        voices[i].playbackPosition = playbackPosition;
                        voices[i].playbackPhase = playbackPhase;
                        voices[i].speedMultiplier = 1.0f;
                    } else {
                        // Find a valid active slice
                        int targetSliceIndex = sliceDist(randomEngine);
                        int attempts = 0;
                        while (attempts < 20 && (targetSliceIndex >= (int)slices.size() ||
                               !slices[targetSliceIndex].active ||
                               slices[targetSliceIndex].startSample >= recordedLength)) {
                            targetSliceIndex = sliceDist(randomEngine);
                            attempts++;
                        }

                        // Safety check - use voice 0's slice if no valid slice found
                        if (targetSliceIndex >= (int)slices.size() ||
                            !slices[targetSliceIndex].active ||
                            slices[targetSliceIndex].startSample >= recordedLength) {
                            targetSliceIndex = currentSliceIndex;
                        }

                        voices[i].sliceIndex = targetSliceIndex;
                        voices[i].playbackPosition = slices[targetSliceIndex].startSample;
                        voices[i].playbackPhase = 0.0f;
                        voices[i].speedMultiplier = speedDist(randomEngine);
                    }
                }
            } else {
                for (int i = 0; i < numVoices; i++) {
                    voices[i].sliceIndex = currentSliceIndex;
                    voices[i].playbackPosition = playbackPosition;
                    voices[i].playbackPhase = playbackPhase;
                    voices[i].speedMultiplier = 1.0f;
                }
            }
        }
    }

    // === EQ Parameters ===
    void setEQLow(float gain) { eq.setLowGain(gain); }
    void setEQMid(float gain) { eq.setMidGain(gain); }
    void setEQHigh(float gain) { eq.setHighGain(gain); }

    // === Effects Parameters ===
    void setDelayTime(float timeL, float timeR) { delay.setDelayTime(timeL, timeR); }
    void setDelayFeedback(float fb) { delay.setFeedback(fb); }
    void setDelayWet(float wet) { delayWet = clamp(wet, 0.0f, 1.0f); }
    void setReverbRoom(float room) { reverb.setParameters(room, -1.0f, -1.0f); }
    void setReverbDamping(float damp) { reverb.setParameters(-1.0f, damp, -1.0f); }
    void setReverbDecay(float decay) { reverb.setParameters(-1.0f, -1.0f, decay); }
    void setReverbWet(float wet) { reverbWet = clamp(wet, 0.0f, 1.0f); }

    // === Query functions ===
    int getNumSlices() const { return slices.size(); }
    int getCurrentSlice() const { return currentSliceIndex; }
    int getNumVoices() const { return numVoices; }
    bool getIsRecording() const { return isRecording; }

    /**
     * Main processing function
     */
    void process(const float* inputL, const float* /* inputR */,
                 float* outputL, float* outputR, int numSamples) {

        for (int i = 0; i < numSamples; i++) {
            float input = inputL[i];  // Mono input

            // === RECORDING ===
            if (isRecording && tempRecordPosition < LOOP_BUFFER_SIZE) {
                tempBuffer[tempRecordPosition] = input;
                tempRecordedLength = tempRecordPosition + 1;

                float currentAmp = std::abs(input);
                float threshold = 0.5f;
                float minSliceTimeSec = getMinSliceTime(minSliceTime);
                int minSliceSamples = (int)(minSliceTimeSec * sampleRate);

                if (tempLastAmplitude < threshold && currentAmp >= threshold) {
                    if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                        int sliceLength = tempRecordPosition - tempSlices.back().startSample;
                        if (sliceLength >= minSliceSamples) {
                            tempSlices.back().endSample = tempRecordPosition - 1;
                        } else {
                            tempSlices.pop_back();
                        }
                    }

                    if (tempSlices.empty() || tempSlices.back().endSample > 0) {
                        Slice newSlice;
                        newSlice.startSample = tempRecordPosition;
                        newSlice.active = true;
                        newSlice.peakAmplitude = 0.0f;
                        tempSlices.push_back(newSlice);
                    }
                }

                if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                    tempSlices.back().peakAmplitude = std::max(tempSlices.back().peakAmplitude, currentAmp);
                }

                tempLastAmplitude = currentAmp;
                tempRecordPosition++;
            }

            // === SCAN functionality (from lines 602-632) ===
            if (slices.size() > 1) {
                bool useManualScan = scanValue > 0.01f;

                if (useManualScan) {
                    int targetSliceIndex = (int)std::round(scanValue * (slices.size() - 1));
                    targetSliceIndex = clamp(targetSliceIndex, 0, (int)slices.size() - 1);

                    if (targetSliceIndex != lastScanTargetIndex && slices[targetSliceIndex].active) {
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

            // === PLAYBACK (from lines 634-771) ===
            float loopL = 0.0f;
            float loopR = 0.0f;

            if (recordedLength > 0) {
                float playbackSpeed = speed;
                bool isReverse = playbackSpeed < 0.0f;

                if (numVoices == 1 || voices.empty()) {
                    // Single voice mode
                    playbackPhase += playbackSpeed;
                    int positionDelta = (int)playbackPhase;
                    playbackPhase -= (float)positionDelta;
                    playbackPosition += positionDelta;

                    // Loop current slice
                    if (!slices.empty() && currentSliceIndex < (int)slices.size() && slices[currentSliceIndex].active) {
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

                        float sample = loopBuffer[pos0] * (1.0f - frac) + loopBuffer[pos1] * frac;
                        loopL = sample;
                        loopR = sample;
                    }
                } else {
                    // Multiple voices mode (from lines 692-771)
                    for (int v = 0; v < numVoices; v++) {
                        float voiceSpeed = playbackSpeed * voices[v].speedMultiplier;
                        voiceSpeed = clamp(voiceSpeed, -16.0f, 16.0f);
                        voices[v].playbackPhase += voiceSpeed;

                        int positionDelta = (int)voices[v].playbackPhase;
                        voices[v].playbackPhase -= (float)positionDelta;
                        voices[v].playbackPosition += positionDelta;

                        // Loop current slice for each voice
                        if (!slices.empty() && voices[v].sliceIndex < (int)slices.size() && slices[voices[v].sliceIndex].active) {
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

                        // Read with interpolation and distribute to L/R alternately
                        if (recordedLength > 0) {
                            voices[v].playbackPosition = clamp(voices[v].playbackPosition, 0, recordedLength - 1);
                            int pos0 = voices[v].playbackPosition;
                            int pos1 = (recordedLength > 1) ? ((pos0 + 1) % recordedLength) : pos0;

                            pos0 = clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
                            pos1 = clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

                            float frac = clamp(std::abs(voices[v].playbackPhase), 0.0f, 1.0f);

                            float sample = loopBuffer[pos0] * (1.0f - frac) + loopBuffer[pos1] * frac;

                            if (std::isfinite(sample)) {
                                // Alternate voices between L and R
                                if (v % 2 == 0) {
                                    loopL += sample;
                                } else {
                                    loopR += sample;
                                }
                            }
                        }
                    }

                    // Normalize by sqrt of voices per channel
                    int leftVoices = (numVoices + 1) / 2;  // Round up for left
                    int rightVoices = numVoices / 2;       // Round down for right
                    if (leftVoices > 0) loopL /= std::sqrt((float)leftVoices);
                    if (rightVoices > 0) loopR /= std::sqrt((float)rightVoices);

                    // Update layer position to voice 0
                    if (!voices.empty()) {
                        playbackPosition = voices[0].playbackPosition;
                        playbackPhase = voices[0].playbackPhase;
                        currentSliceIndex = voices[0].sliceIndex;
                    }
                }
            }

            // === MIX ===
            float mixL = input * (1.0f - mixAmount) + loopL * mixAmount;
            float mixR = input * (1.0f - mixAmount) + loopR * mixAmount;

            // === FEEDBACK ===
            float fbL = std::tanh(lastOutputL * 0.3f) / 0.3f;
            float fbR = std::tanh(lastOutputR * 0.3f) / 0.3f;

            mixL += fbL * feedbackAmount;
            mixR += fbR * feedbackAmount;

            // === 3-Band EQ ===
            float eqL, eqR;
            eq.process(mixL, mixR, &eqL, &eqR);

            // === Delay ===
            float delayedL, delayedR;
            delay.process(&eqL, &eqR, &delayedL, &delayedR, 1);

            float delayMixL = eqL * (1.0f - delayWet) + delayedL * delayWet;
            float delayMixR = eqR * (1.0f - delayWet) + delayedR * delayWet;

            // === Reverb ===
            float reverbedL, reverbedR;
            reverb.process(&delayMixL, &delayMixR, &reverbedL, &reverbedR, 1);

            float finalL = delayMixL * (1.0f - reverbWet) + reverbedL * reverbWet;
            float finalR = delayMixR * (1.0f - reverbWet) + reverbedR * reverbWet;

            // Store for feedback
            lastOutputL = finalL;
            lastOutputR = finalR;

            // Output
            outputL[i] = clamp(finalL, -10.0f, 10.0f);
            outputR[i] = clamp(finalR, -10.0f, 10.0f);
        }
    }

    void clear() {
        std::fill(loopBuffer.begin(), loopBuffer.end(), 0.0f);
        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
        isRecording = false;
        lastOutputL = 0.0f;
        lastOutputR = 0.0f;
        slices.clear();
        currentSliceIndex = 0;
        lastAmplitude = 0.0f;
        lastScanTargetIndex = -1;
        voices.clear();
        numVoices = 1;
        eq.clear();
        delay.clear();
        reverb.clear();
    }
};
