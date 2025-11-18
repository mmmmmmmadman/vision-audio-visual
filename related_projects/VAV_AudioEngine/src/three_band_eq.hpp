#pragma once

#include <cmath>
#include <algorithm>

/**
 * ThreeBandEQ - Simple 3-band equalizer
 *
 * Low shelf, Peak (mid), High shelf
 * Based on simple biquad filters
 */
class ThreeBandEQ {
private:
    float sampleRate;

    // Biquad coefficients for each band (stereo)
    struct BiquadCoeffs {
        float b0, b1, b2, a1, a2;
    };

    struct BiquadState {
        float x1, x2, y1, y2;  // State for left channel
        float x1r, x2r, y1r, y2r;  // State for right channel

        BiquadState() : x1(0), x2(0), y1(0), y2(0),
                        x1r(0), x2r(0), y1r(0), y2r(0) {}
    };

    BiquadCoeffs lowShelf;
    BiquadCoeffs midPeak;
    BiquadCoeffs highShelf;

    BiquadState lowState;
    BiquadState midState;
    BiquadState highState;

    float lowGain;   // -20dB to +20dB
    float midGain;
    float highGain;

    void calculateLowShelf(float freq, float gain) {
        float w0 = 2.0f * M_PI * freq / sampleRate;
        float A = std::pow(10.0f, gain / 40.0f);
        float S = 1.0f;
        float alpha = std::sin(w0) / 2.0f * std::sqrt((A + 1.0f / A) * (1.0f / S - 1.0f) + 2.0f);
        float cos_w0 = std::cos(w0);

        lowShelf.b0 = A * ((A + 1.0f) - (A - 1.0f) * cos_w0 + 2.0f * std::sqrt(A) * alpha);
        lowShelf.b1 = 2.0f * A * ((A - 1.0f) - (A + 1.0f) * cos_w0);
        lowShelf.b2 = A * ((A + 1.0f) - (A - 1.0f) * cos_w0 - 2.0f * std::sqrt(A) * alpha);
        float a0 = (A + 1.0f) + (A - 1.0f) * cos_w0 + 2.0f * std::sqrt(A) * alpha;
        lowShelf.a1 = -2.0f * ((A - 1.0f) + (A + 1.0f) * cos_w0) / a0;
        lowShelf.a2 = ((A + 1.0f) + (A - 1.0f) * cos_w0 - 2.0f * std::sqrt(A) * alpha) / a0;
        lowShelf.b0 /= a0;
        lowShelf.b1 /= a0;
        lowShelf.b2 /= a0;
    }

    void calculatePeaking(float freq, float gain, float Q) {
        float w0 = 2.0f * M_PI * freq / sampleRate;
        float A = std::pow(10.0f, gain / 40.0f);
        float alpha = std::sin(w0) / (2.0f * Q);
        float cos_w0 = std::cos(w0);

        midPeak.b0 = 1.0f + alpha * A;
        midPeak.b1 = -2.0f * cos_w0;
        midPeak.b2 = 1.0f - alpha * A;
        float a0 = 1.0f + alpha / A;
        midPeak.a1 = -2.0f * cos_w0 / a0;
        midPeak.a2 = (1.0f - alpha / A) / a0;
        midPeak.b0 /= a0;
        midPeak.b1 /= a0;
        midPeak.b2 /= a0;
    }

    void calculateHighShelf(float freq, float gain) {
        float w0 = 2.0f * M_PI * freq / sampleRate;
        float A = std::pow(10.0f, gain / 40.0f);
        float S = 1.0f;
        float alpha = std::sin(w0) / 2.0f * std::sqrt((A + 1.0f / A) * (1.0f / S - 1.0f) + 2.0f);
        float cos_w0 = std::cos(w0);

        highShelf.b0 = A * ((A + 1.0f) + (A - 1.0f) * cos_w0 + 2.0f * std::sqrt(A) * alpha);
        highShelf.b1 = -2.0f * A * ((A - 1.0f) + (A + 1.0f) * cos_w0);
        highShelf.b2 = A * ((A + 1.0f) + (A - 1.0f) * cos_w0 - 2.0f * std::sqrt(A) * alpha);
        float a0 = (A + 1.0f) - (A - 1.0f) * cos_w0 + 2.0f * std::sqrt(A) * alpha;
        highShelf.a1 = 2.0f * ((A - 1.0f) - (A + 1.0f) * cos_w0) / a0;
        highShelf.a2 = ((A + 1.0f) - (A - 1.0f) * cos_w0 - 2.0f * std::sqrt(A) * alpha) / a0;
        highShelf.b0 /= a0;
        highShelf.b1 /= a0;
        highShelf.b2 /= a0;
    }

    float processBiquad(float input, const BiquadCoeffs& coeffs, BiquadState& state, bool rightChannel = false) {
        float& x1 = rightChannel ? state.x1r : state.x1;
        float& x2 = rightChannel ? state.x2r : state.x2;
        float& y1 = rightChannel ? state.y1r : state.y1;
        float& y2 = rightChannel ? state.y2r : state.y2;

        float output = coeffs.b0 * input + coeffs.b1 * x1 + coeffs.b2 * x2
                     - coeffs.a1 * y1 - coeffs.a2 * y2;

        x2 = x1;
        x1 = input;
        y2 = y1;
        y1 = output;

        return output;
    }

public:
    ThreeBandEQ(float sr = 48000.0f) : sampleRate(sr), lowGain(0), midGain(0), highGain(0) {
        // Default frequencies: 250Hz, 1kHz, 4kHz
        calculateLowShelf(250.0f, 0.0f);
        calculatePeaking(1000.0f, 0.0f, 1.0f);
        calculateHighShelf(4000.0f, 0.0f);
    }

    void setLowGain(float gain) {
        lowGain = std::max(-20.0f, std::min(20.0f, gain));
        calculateLowShelf(250.0f, lowGain);
    }

    void setMidGain(float gain) {
        midGain = std::max(-20.0f, std::min(20.0f, gain));
        calculatePeaking(1000.0f, midGain, 1.0f);
    }

    void setHighGain(float gain) {
        highGain = std::max(-20.0f, std::min(20.0f, gain));
        calculateHighShelf(4000.0f, highGain);
    }

    void process(float inL, float inR, float* outL, float* outR) {
        // Process left channel
        float tmpL = processBiquad(inL, lowShelf, lowState, false);
        tmpL = processBiquad(tmpL, midPeak, midState, false);
        tmpL = processBiquad(tmpL, highShelf, highState, false);

        // Process right channel
        float tmpR = processBiquad(inR, lowShelf, lowState, true);
        tmpR = processBiquad(tmpR, midPeak, midState, true);
        tmpR = processBiquad(tmpR, highShelf, highState, true);

        *outL = tmpL;
        *outR = tmpR;
    }

    void clear() {
        lowState = BiquadState();
        midState = BiquadState();
        highState = BiquadState();
    }
};
