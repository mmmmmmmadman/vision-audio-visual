#pragma once

#include "audio_layer.hpp"
#include "three_band_eq.hpp"
#include "ripley/stereo_delay.hpp"
#include "ripley/reverb_processor.hpp"
#include <vector>
#include <algorithm>
#include <cmath>

/**
 * Alien4AudioEngine - Complete audio processing engine
 *
 * Combines Documenta sampler with simplified Ellen Ripley effects
 *
 * Signal Flow:
 * Input → REC/LOOP → MIX → FDBK → 3-Band EQ → Send → (Delay + Reverb) → Return → SPEED → Output
 */
class Alien4AudioEngine {
private:
    float sampleRate;

    // Documenta Core
    static constexpr int MAX_LAYERS = 4;
    AudioLayer layers[MAX_LAYERS];

    bool recording;
    bool looping;
    int recordPosition;
    int activeLayer;

    float minSliceTime;
    int scanIndex;
    float feedbackAmount;
    float mixAmount;  // 0=input, 1=loop
    float speed;

    // Feedback buffer
    std::vector<float> feedbackBufferL;
    std::vector<float> feedbackBufferR;

    // 3-Band EQ
    ThreeBandEQ eq;

    // Ellen Ripley (simplified)
    StereoDelay delay;
    ReverbProcessor reverb;
    float delayWet;   // Delay wet/dry mix (0=dry, 1=wet)
    float reverbWet;  // Reverb wet/dry mix (0=dry, 1=wet)

public:
    Alien4AudioEngine(float sr = 48000.0f)
        : sampleRate(sr), recording(false), looping(true), recordPosition(0),
          activeLayer(0), minSliceTime(0.1f), scanIndex(0), feedbackAmount(0.0f),
          mixAmount(0.5f), speed(1.0f), eq(sr), delay(sr), reverb(sr),
          delayWet(0.0f), reverbWet(0.0f) {

        // Initialize layers
        int maxSamples = (int)(60.0f * sampleRate);  // 60 seconds
        for (int i = 0; i < MAX_LAYERS; i++) {
            layers[i] = AudioLayer(maxSamples);
        }

        // Initialize feedback buffer (1 second)
        int fbSize = (int)sampleRate;
        feedbackBufferL.resize(fbSize, 0.0f);
        feedbackBufferR.resize(fbSize, 0.0f);
    }

    // === Documenta Parameters ===
    void setRecording(bool rec) { recording = rec; }
    void setLooping(bool loop) { looping = loop; }
    void setMinSliceTime(float time) { minSliceTime = std::max(0.01f, time); }
    void setScan(int index) { scanIndex = std::max(0, std::min(MAX_LAYERS - 1, index)); }
    void setFeedback(float amount) { feedbackAmount = std::max(0.0f, std::min(0.95f, amount)); }
    void setMix(float mix) { mixAmount = std::max(0.0f, std::min(1.0f, mix)); }
    void setSpeed(float spd) { speed = std::max(0.25f, std::min(4.0f, spd)); }

    // === EQ Parameters ===
    void setEQLow(float gain) { eq.setLowGain(gain); }
    void setEQMid(float gain) { eq.setMidGain(gain); }
    void setEQHigh(float gain) { eq.setHighGain(gain); }

    // === Ellen Ripley Parameters ===
    void setDelayTime(float timeL, float timeR) { delay.setDelayTime(timeL, timeR); }
    void setDelayFeedback(float fb) { delay.setFeedback(fb); }
    void setDelayWet(float wet) { delayWet = std::max(0.0f, std::min(1.0f, wet)); }
    void setReverbRoom(float room) { reverb.setParameters(room, -1.0f, -1.0f); }
    void setReverbDamping(float damp) { reverb.setParameters(-1.0f, damp, -1.0f); }
    void setReverbDecay(float decay) { reverb.setParameters(-1.0f, -1.0f, decay); }
    void setReverbWet(float wet) { reverbWet = std::max(0.0f, std::min(1.0f, wet)); }

    // === Main Processing ===
    void process(const float* inputL, const float* inputR,
                 float* outputL, float* outputR, int numSamples) {

        // Temporary buffers
        std::vector<float> tmpL(numSamples);
        std::vector<float> tmpR(numSamples);
        std::vector<float> loopL(numSamples);
        std::vector<float> loopR(numSamples);

        for (int i = 0; i < numSamples; i++) {
            // 1. REC/LOOP
            if (recording && activeLayer < MAX_LAYERS) {
                layers[activeLayer].record(inputL[i], inputR[i], recordPosition);
                recordPosition++;
            }

            // Playback from active layer
            float playL, playR;
            if (looping && activeLayer < MAX_LAYERS) {
                layers[activeLayer].playback(speed, &playL, &playR);
            } else {
                playL = playR = 0.0f;
            }

            loopL[i] = playL;
            loopR[i] = playR;

            // 2. MIX (Input / Loop)
            float mixL = inputL[i] * (1.0f - mixAmount) + loopL[i] * mixAmount;
            float mixR = inputR[i] * (1.0f - mixAmount) + loopR[i] * mixAmount;

            // 3. FDBK (simple feedback mixing)
            float fbL = feedbackBufferL[i % feedbackBufferL.size()];
            float fbR = feedbackBufferR[i % feedbackBufferR.size()];
            float fbMixL = mixL + fbL * feedbackAmount;
            float fbMixR = mixR + fbR * feedbackAmount;

            tmpL[i] = fbMixL;
            tmpR[i] = fbMixR;
        }

        // 4. 3-Band EQ
        std::vector<float> eqL(numSamples);
        std::vector<float> eqR(numSamples);
        for (int i = 0; i < numSamples; i++) {
            eq.process(tmpL[i], tmpR[i], &eqL[i], &eqR[i]);
        }

        // 5. Delay (with wet/dry mix)
        std::vector<float> delayedL(numSamples);
        std::vector<float> delayedR(numSamples);
        delay.process(eqL.data(), eqR.data(), delayedL.data(), delayedR.data(), numSamples);

        std::vector<float> delayMixL(numSamples);
        std::vector<float> delayMixR(numSamples);
        for (int i = 0; i < numSamples; i++) {
            delayMixL[i] = eqL[i] * (1.0f - delayWet) + delayedL[i] * delayWet;
            delayMixR[i] = eqR[i] * (1.0f - delayWet) + delayedR[i] * delayWet;
        }

        // 6. Reverb (with wet/dry mix)
        std::vector<float> reverbedL(numSamples);
        std::vector<float> reverbedR(numSamples);
        reverb.process(delayMixL.data(), delayMixR.data(), reverbedL.data(), reverbedR.data(), numSamples);

        std::vector<float> returnL(numSamples);
        std::vector<float> returnR(numSamples);
        for (int i = 0; i < numSamples; i++) {
            returnL[i] = delayMixL[i] * (1.0f - reverbWet) + reverbedL[i] * reverbWet;
            returnR[i] = delayMixR[i] * (1.0f - reverbWet) + reverbedR[i] * reverbWet;
        }

        // 6. SPEED (already applied in playback)
        // 7. Output
        for (int i = 0; i < numSamples; i++) {
            outputL[i] = returnL[i];
            outputR[i] = returnR[i];

            // Store for feedback
            feedbackBufferL[i % feedbackBufferL.size()] = returnL[i];
            feedbackBufferR[i % feedbackBufferR.size()] = returnR[i];
        }
    }

    void clear() {
        for (int i = 0; i < MAX_LAYERS; i++) {
            layers[i].clear();
        }
        std::fill(feedbackBufferL.begin(), feedbackBufferL.end(), 0.0f);
        std::fill(feedbackBufferR.begin(), feedbackBufferR.end(), 0.0f);
        eq.clear();
        delay.clear();
        reverb.clear();
        recordPosition = 0;
    }
};
