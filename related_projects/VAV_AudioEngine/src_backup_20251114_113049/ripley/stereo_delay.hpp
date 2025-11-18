#pragma once

#include <vector>
#include <algorithm>
#include <cmath>

/**
 * StereoDelay - Stereo delay with independent L/R times and feedback
 *
 * Ported from VAV Python version (Ellen Ripley)
 */
class StereoDelay {
private:
    float sampleRate;
    float maxDelay;
    int bufferSize;

    std::vector<float> leftBuffer;
    std::vector<float> rightBuffer;
    int writeIndex;

    float delayTimeL;  // seconds
    float delayTimeR;
    float feedback;

public:
    StereoDelay(float sr = 48000.0f, float maxDel = 2.0f)
        : sampleRate(sr), maxDelay(maxDel), writeIndex(0),
          delayTimeL(0.25f), delayTimeR(0.25f), feedback(0.3f) {

        bufferSize = (int)(maxDelay * sampleRate);
        leftBuffer.resize(bufferSize, 0.0f);
        rightBuffer.resize(bufferSize, 0.0f);
    }

    void setDelayTime(float left, float right) {
        delayTimeL = std::max(0.001f, std::min(maxDelay, left));
        delayTimeR = std::max(0.001f, std::min(maxDelay, right));
    }

    void setFeedback(float fb) {
        feedback = std::max(0.0f, std::min(0.95f, fb));
    }

    void process(const float* leftIn, const float* rightIn,
                 float* leftOut, float* rightOut, int numSamples) {

        int delaySamplesL = (int)(delayTimeL * sampleRate);
        int delaySamplesR = (int)(delayTimeR * sampleRate);

        delaySamplesL = std::max(1, std::min(bufferSize - 1, delaySamplesL));
        delaySamplesR = std::max(1, std::min(bufferSize - 1, delaySamplesR));

        for (int i = 0; i < numSamples; i++) {
            // Calculate read indices
            int readIndexL = (writeIndex - delaySamplesL + bufferSize) % bufferSize;
            int readIndexR = (writeIndex - delaySamplesR + bufferSize) % bufferSize;

            // Read delayed signals
            float leftDelayed = leftBuffer[readIndexL];
            float rightDelayed = rightBuffer[readIndexR];

            // Write input + feedback to buffer
            leftBuffer[writeIndex] = leftIn[i] + leftDelayed * feedback;
            rightBuffer[writeIndex] = rightIn[i] + rightDelayed * feedback;

            // Output delayed signals
            leftOut[i] = leftDelayed;
            rightOut[i] = rightDelayed;

            // Advance write index
            writeIndex = (writeIndex + 1) % bufferSize;
        }
    }

    void clear() {
        std::fill(leftBuffer.begin(), leftBuffer.end(), 0.0f);
        std::fill(rightBuffer.begin(), rightBuffer.end(), 0.0f);
        writeIndex = 0;
    }
};
