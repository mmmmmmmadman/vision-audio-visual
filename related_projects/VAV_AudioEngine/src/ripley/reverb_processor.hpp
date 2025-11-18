#pragma once

#include <vector>
#include <algorithm>
#include <cmath>

/**
 * ReverbProcessor - Freeverb style stereo reverb
 *
 * Ported from VAV Python version (Ellen Ripley)
 * Uses comb filters with lowpass damping and allpass diffusion
 */
class ReverbProcessor {
private:
    float sampleRate;

    // Comb filter sizes (samples at 48kHz)
    static constexpr int COMB_SIZES[8] = {1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116};
    static constexpr int ALLPASS_SIZES[4] = {556, 441, 341, 225};

    // Comb filters (4 per channel)
    std::vector<float> combBuffersL[4];
    std::vector<float> combBuffersR[4];
    int combIndicesL[4];
    int combIndicesR[4];
    float combLpL[4];  // Lowpass states
    float combLpR[4];

    // Allpass filters (shared stereo)
    std::vector<float> allpassBuffers[4];
    int allpassIndices[4];

    // Highpass filter states
    float hpStateL;
    float hpStateR;

    // Parameters
    float roomSize;
    float damping;
    float decay;

    float processCombFilter(float input, std::vector<float>& buffer, int& index,
                           float& lpState, float feedback, float dampingCoeff) {
        int size = buffer.size();
        float output = buffer[index];

        // Lowpass filter on feedback
        lpState += (output - lpState) * dampingCoeff;

        // Write input + filtered feedback
        buffer[index] = input + lpState * feedback;
        index = (index + 1) % size;

        return output;
    }

    float processAllpassFilter(float input, std::vector<float>& buffer, int& index) {
        constexpr float gain = 0.5f;
        int size = buffer.size();
        float delayed = buffer[index];
        float output = -input * gain + delayed;
        buffer[index] = input + delayed * gain;
        index = (index + 1) % size;
        return output;
    }

public:
    ReverbProcessor(float sr = 48000.0f)
        : sampleRate(sr), hpStateL(0.0f), hpStateR(0.0f),
          roomSize(0.5f), damping(0.4f), decay(0.6f) {

        // Initialize comb filters
        for (int i = 0; i < 4; i++) {
            combBuffersL[i].resize(COMB_SIZES[i], 0.0f);
            combBuffersR[i].resize(COMB_SIZES[i + 4], 0.0f);
            combIndicesL[i] = 0;
            combIndicesR[i] = 0;
            combLpL[i] = 0.0f;
            combLpR[i] = 0.0f;
        }

        // Initialize allpass filters
        for (int i = 0; i < 4; i++) {
            allpassBuffers[i].resize(ALLPASS_SIZES[i], 0.0f);
            allpassIndices[i] = 0;
        }
    }

    void setParameters(float room, float damp, float dec) {
        roomSize = std::max(0.0f, std::min(1.0f, room));
        damping = std::max(0.0f, std::min(1.0f, damp));
        decay = std::max(0.0f, std::min(1.0f, dec));
    }

    void process(const float* leftIn, const float* rightIn,
                 float* leftOut, float* rightOut, int numSamples) {

        // Calculate feedback from decay
        float feedback = 0.5f + decay * 0.485f;  // 0.5 to 0.985
        feedback = std::max(0.0f, std::min(0.995f, feedback));

        // Damping coefficient
        float dampingCoeff = 0.05f + damping * 0.9f;

        // Room size scaling
        float roomScale = 0.3f + roomSize * 1.4f;

        for (int i = 0; i < numSamples; i++) {
            // Scale input by room size
            float inputL = leftIn[i] * roomScale;
            float inputR = rightIn[i] * roomScale;

            // Process left channel comb filters
            float combOutL = 0.0f;
            for (int j = 0; j < 4; j++) {
                combOutL += processCombFilter(inputL, combBuffersL[j], combIndicesL[j],
                                             combLpL[j], feedback, dampingCoeff);
            }

            // Process right channel comb filters
            float combOutR = 0.0f;
            for (int j = 0; j < 4; j++) {
                combOutR += processCombFilter(inputR, combBuffersR[j], combIndicesR[j],
                                             combLpR[j], feedback, dampingCoeff);
            }

            // Scale comb output
            combOutL *= 0.25f;
            combOutR *= 0.25f;

            // Series allpass diffusion (shared for stereo)
            float diffusedL = combOutL;
            float diffusedR = combOutR;

            for (int j = 0; j < 4; j++) {
                diffusedL = processAllpassFilter(diffusedL, allpassBuffers[j], allpassIndices[j]);
                diffusedR = processAllpassFilter(diffusedR, allpassBuffers[j], allpassIndices[j]);
            }

            // Highpass filter (remove sub-100Hz)
            float hpCutoff = 100.0f / (sampleRate * 0.5f);
            hpCutoff = std::max(0.001f, std::min(0.1f, hpCutoff));

            hpStateL += (diffusedL - hpStateL) * hpCutoff;
            hpStateR += (diffusedR - hpStateR) * hpCutoff;

            leftOut[i] = diffusedL - hpStateL;
            rightOut[i] = diffusedR - hpStateR;
        }
    }

    void clear() {
        for (int i = 0; i < 4; i++) {
            std::fill(combBuffersL[i].begin(), combBuffersL[i].end(), 0.0f);
            std::fill(combBuffersR[i].begin(), combBuffersR[i].end(), 0.0f);
            std::fill(allpassBuffers[i].begin(), allpassBuffers[i].end(), 0.0f);
            combIndicesL[i] = 0;
            combIndicesR[i] = 0;
            allpassIndices[i] = 0;
            combLpL[i] = 0.0f;
            combLpR[i] = 0.0f;
        }
        hpStateL = 0.0f;
        hpStateR = 0.0f;
    }
};
