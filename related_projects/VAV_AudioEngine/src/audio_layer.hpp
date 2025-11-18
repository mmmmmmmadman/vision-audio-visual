#pragma once

#include <vector>
#include <cstring>

/**
 * AudioLayer - Single audio recording/playback layer
 *
 * Features:
 * - Stereo recording (60 seconds @ 48kHz)
 * - Loop playback with variable speed
 * - Sub-sample accurate playback position
 */
class AudioLayer {
public:
    std::vector<float> bufferL;
    std::vector<float> bufferR;

    int playbackPosition;
    float playbackPhase;        // Sub-sample phase (0.0-1.0)
    int recordedLength;
    bool active;

    AudioLayer(int maxSamples = 60 * 48000) {
        bufferL.resize(maxSamples, 0.0f);
        bufferR.resize(maxSamples, 0.0f);
        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
        active = true;
    }

    void clear() {
        std::fill(bufferL.begin(), bufferL.end(), 0.0f);
        std::fill(bufferR.begin(), bufferR.end(), 0.0f);
        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
    }

    void record(float inL, float inR, int position) {
        if (position >= 0 && position < (int)bufferL.size()) {
            bufferL[position] = inL;
            bufferR[position] = inR;
            if (position >= recordedLength) {
                recordedLength = position + 1;
            }
        }
    }

    void playback(float speed, float* outL, float* outR) {
        if (!active || recordedLength == 0) {
            *outL = 0.0f;
            *outR = 0.0f;
            return;
        }

        // Linear interpolation for sub-sample accuracy
        int pos = playbackPosition;
        int nextPos = (pos + 1) % recordedLength;

        float frac = playbackPhase;
        *outL = bufferL[pos] * (1.0f - frac) + bufferL[nextPos] * frac;
        *outR = bufferR[pos] * (1.0f - frac) + bufferR[nextPos] * frac;

        // Advance playback position
        playbackPhase += speed;
        while (playbackPhase >= 1.0f) {
            playbackPhase -= 1.0f;
            playbackPosition = (playbackPosition + 1) % recordedLength;
        }
    }
};
