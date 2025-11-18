#pragma once

// LA-2A style optical compressor
// Based on sndfilter by Sean Connelly (0BSD license)
// Simplified and adapted for breakbeat engine

namespace breakbeat {

class Compressor {
public:
    Compressor(int sample_rate);
    ~Compressor();

    // LA-2A style parameters (Compress mode only)
    void set_peak_reduction(float amount);  // 0.0 to 1.0 (controls threshold)
    void set_gain(float db);                // Output makeup gain (-20 to 20 dB)
    void set_mix(float mix);                // 0.0 (dry) to 1.0 (wet)

    // Process mono audio
    void process(float* buffer, int num_samples);

    // Get current gain reduction in dB
    float get_gain_reduction() const { return gain_reduction_db_; }

private:
    int sample_rate_;

    // LA-2A characteristics (Compress mode: 3:1 ratio)
    float peak_reduction_;  // 0.0 to 1.0
    float gain_;            // Output makeup gain
    float threshold_;       // Computed from peak_reduction
    float mix_;

    // Fixed compress mode ratio
    static constexpr float COMPRESS_RATIO = 3.0f;

    // Attack/Release (LA-2A fixed values)
    static constexpr float ATTACK_MS = 10.0f;
    static constexpr float RELEASE_FAST_MS = 60.0f;    // First 50% of release
    static constexpr float RELEASE_SLOW_MS = 1500.0f;  // Last 50% of release

    // State variables
    float envelope_;
    float gain_reduction_db_;

    // Computed coefficients
    float attack_coeff_;
    float release_fast_coeff_;
    float release_slow_coeff_;

    void update_coefficients();
    float compute_gain_reduction(float input_level);
};

} // namespace breakbeat
