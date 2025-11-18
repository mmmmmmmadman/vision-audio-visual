#include "compressor.h"
#include <cmath>
#include <algorithm>

namespace breakbeat {

Compressor::Compressor(int sample_rate)
    : sample_rate_(sample_rate)
    , peak_reduction_(0.0f)
    , gain_(1.0f)
    , threshold_(1.0f)  // No compression at 0% peak reduction
    , mix_(1.0f)
    , envelope_(0.0f)
    , gain_reduction_db_(0.0f)
{
    update_coefficients();
}

Compressor::~Compressor() {
}

void Compressor::set_peak_reduction(float amount) {
    // 0.0 = no compression (threshold at 0 dB)
    // 1.0 = max compression (threshold at -40 dB)
    peak_reduction_ = std::clamp(amount, 0.0f, 1.0f);

    // Map peak reduction to threshold: 0 dB to -40 dB
    float threshold_db = -40.0f * peak_reduction_;
    threshold_ = std::pow(10.0f, threshold_db / 20.0f);
}

void Compressor::set_gain(float db) {
    gain_ = std::pow(10.0f, db / 20.0f);
}

void Compressor::set_mix(float mix) {
    mix_ = std::clamp(mix, 0.0f, 1.0f);
}

void Compressor::update_coefficients() {
    // Convert attack/release times to coefficients
    // coefficient = exp(-1 / (time_in_seconds * sample_rate))

    float attack_samples = (ATTACK_MS / 1000.0f) * sample_rate_;
    attack_coeff_ = std::exp(-1.0f / attack_samples);

    float release_fast_samples = (RELEASE_FAST_MS / 1000.0f) * sample_rate_;
    release_fast_coeff_ = std::exp(-1.0f / release_fast_samples);

    float release_slow_samples = (RELEASE_SLOW_MS / 1000.0f) * sample_rate_;
    release_slow_coeff_ = std::exp(-1.0f / release_slow_samples);
}

float Compressor::compute_gain_reduction(float input_level) {
    if (input_level <= threshold_) {
        return 1.0f;  // No compression
    }

    // Calculate how much over threshold
    float over_db = 20.0f * std::log10(input_level / threshold_);

    // Apply fixed 3:1 compress ratio
    float compressed_db = over_db / COMPRESS_RATIO;

    // Gain reduction needed
    float reduction_db = over_db - compressed_db;

    // Convert to linear gain (less than 1.0)
    return std::pow(10.0f, -reduction_db / 20.0f);
}

void Compressor::process(float* buffer, int num_samples) {
    for (int i = 0; i < num_samples; ++i) {
        // Store original for dry/wet mix
        float dry = buffer[i];

        // Get input level (absolute value)
        float input_level = std::abs(dry);

        // Update envelope detector
        if (input_level > envelope_) {
            // Attack: fast response
            envelope_ = attack_coeff_ * envelope_ + (1.0f - attack_coeff_) * input_level;
        } else {
            // Release: two-stage (fast then slow)
            // Use fast release if envelope is high, slow release as it decreases
            float release_blend = envelope_ / threshold_;
            release_blend = std::clamp(release_blend, 0.0f, 1.0f);

            float release_coeff = release_fast_coeff_ * release_blend +
                                 release_slow_coeff_ * (1.0f - release_blend);

            envelope_ = release_coeff * envelope_ + (1.0f - release_coeff) * input_level;
        }

        // Compute gain reduction based on envelope
        float gain = compute_gain_reduction(envelope_);

        // Store gain reduction for metering
        gain_reduction_db_ = -20.0f * std::log10(gain);

        // Apply compression
        float compressed = dry * gain;

        // Apply makeup gain
        compressed *= gain_;

        // Apply soft saturation (tube-like)
        compressed = std::tanh(compressed * 0.5f) * 2.0f;

        // Mix dry and wet
        buffer[i] = dry * (1.0f - mix_) + compressed * mix_;
    }
}

} // namespace breakbeat
