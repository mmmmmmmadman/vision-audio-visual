#include "breakbeat_engine.h"
#include "compressor.h"
#include <algorithm>
#include <iostream>

namespace breakbeat {

void BreakbeatEngine::generate_pattern(const RealtimeParams& params, std::vector<float>& pattern) {
    int samples_per_step = calculate_samples_per_step(params.bpm);
    int pattern_length = samples_per_step * 64;  // 4 bars

    pattern.assign(pattern_length, 0.0f);

    std::uniform_real_distribution<float> gain_dist(0.0f, 1.0f);

    // Helper lambda to add sample with random variation and dynamic curve
    auto add_sample = [&](int step, const std::string& category, const std::string& variation, float gain) {
        // Get sample
        DrumSample* sample = get_sample(category, variation);

        if (!sample) return;

        int start = step * samples_per_step;

        // Apply swing to 8th note offbeats (步數 2, 6, 10, 14)
        if (params.swing_amount > 0.0f && (step == 2 || step == 6 || step == 10 || step == 14)) {
            start += static_cast<int>(params.swing_amount * samples_per_step);
        }

        if (start >= pattern_length) return;

        // Calculate dynamic curve multiplier based on which bar this step is in
        int bar = step / 16;
        float dynamic_multiplier = get_dynamic_curve(bar);

        // Copy audio and apply gain with dynamic curve
        std::vector<float> audio = sample->audio;
        for (float& s : audio) {
            s *= gain * dynamic_multiplier;
        }

        // Mix into pattern
        int length = std::min(static_cast<int>(audio.size()), pattern_length - start);
        for (int i = 0; i < length; ++i) {
            pattern[start + i] += audio[i];
        }
    };

    // Generate pattern based on type
    switch (params.pattern_type) {
        case PatternType::AMEN: {
            // Generate 4 bars, each bar is 16 steps
            for (int bar = 0; bar < 4; ++bar) {
                int offset = bar * 16;

                // Bar 1 and Bar 3: Standard Amen pattern
                if (bar == 0 || bar == 2) {
                    add_sample(offset + 0, "kick", "", 0.95f + gain_dist(rng_) * 0.15f);
                    add_sample(offset + 0, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 2, "hihat", "A", 0.25f + gain_dist(rng_) * 0.25f);

                    add_sample(offset + 4, "snare", "", 0.9f + gain_dist(rng_) * 0.2f);
                    add_sample(offset + 4, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 6, "hihat", "A", 0.2f + gain_dist(rng_) * 0.25f);

                    add_sample(offset + 8, "kick", "", 0.75f + gain_dist(rng_) * 0.25f);
                    add_sample(offset + 8, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 10, "kick", "", 0.55f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 10, "hihat", "A", 0.25f + gain_dist(rng_) * 0.3f);

                    add_sample(offset + 12, "snare", "", 0.9f + gain_dist(rng_) * 0.2f);
                    add_sample(offset + 13, "roll", "H", 0.6f + gain_dist(rng_) * 0.35f);
                    add_sample(offset + 14, "snare", "Stick", 0.5f + gain_dist(rng_) * 0.35f);
                    add_sample(offset + 15, "kick", "", 0.6f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 12, "hihat", "O", 0.35f + gain_dist(rng_) * 0.3f);
                }

                // Bar 2: Standard pattern with fill on beat 4 (steps 12-15 -> 28-31)
                else if (bar == 1) {
                    // First 3 beats - standard pattern
                    add_sample(offset + 0, "kick", "", 0.95f + gain_dist(rng_) * 0.15f);
                    add_sample(offset + 0, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 2, "hihat", "A", 0.25f + gain_dist(rng_) * 0.25f);

                    add_sample(offset + 4, "snare", "", 0.9f + gain_dist(rng_) * 0.2f);
                    add_sample(offset + 4, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 6, "hihat", "A", 0.2f + gain_dist(rng_) * 0.25f);

                    add_sample(offset + 8, "kick", "", 0.75f + gain_dist(rng_) * 0.25f);
                    add_sample(offset + 8, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 10, "kick", "", 0.55f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 10, "hihat", "A", 0.25f + gain_dist(rng_) * 0.3f);

                    // Beat 4 - Simple fill (steps 28-31) - randomized each time
                    std::vector<std::string> fill_instruments = {"snare", "roll"};
                    for (int i = 12; i <= 15; ++i) {
                        if (gain_dist(rng_) < 0.8f) {  // 80% probability for each hit
                            std::string inst = fill_instruments[static_cast<int>(gain_dist(rng_) * fill_instruments.size())];
                            add_sample(offset + i, inst, "", 0.7f + gain_dist(rng_) * 0.3f);
                        }
                        // Add hihat accents randomly
                        if (gain_dist(rng_) < 0.5f) {
                            std::string hat_type = (gain_dist(rng_) < 0.5f) ? "C" : "A";
                            add_sample(offset + i, "hihat", hat_type, 0.3f + gain_dist(rng_) * 0.2f);
                        }
                    }
                    // Ensure ending kick
                    if (gain_dist(rng_) < 0.7f) {
                        add_sample(offset + 15, "kick", "", 0.7f + gain_dist(rng_) * 0.25f);
                    }
                }

                // Bar 4: Standard pattern first half, complete fill on beats 3-4 (steps 56-63)
                else if (bar == 3) {
                    // First 2 beats - standard pattern
                    add_sample(offset + 0, "kick", "", 0.95f + gain_dist(rng_) * 0.15f);
                    add_sample(offset + 0, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 2, "hihat", "A", 0.25f + gain_dist(rng_) * 0.25f);

                    add_sample(offset + 4, "snare", "", 0.9f + gain_dist(rng_) * 0.2f);
                    add_sample(offset + 4, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);
                    add_sample(offset + 6, "hihat", "A", 0.2f + gain_dist(rng_) * 0.25f);

                    // Beats 3-4 - Complete fill (steps 56-63) - randomized each time
                    std::vector<std::string> fill_main = {"snare", "roll"};

                    for (int i = 8; i <= 15; ++i) {
                        // Main fill hits with varying probability
                        float hit_prob = (i >= 12) ? 0.9f : 0.75f;  // More dense in last beat
                        if (gain_dist(rng_) < hit_prob) {
                            std::string inst = fill_main[static_cast<int>(gain_dist(rng_) * fill_main.size())];
                            add_sample(offset + i, inst, "", 0.75f + gain_dist(rng_) * 0.3f);
                        }

                        // Random hihat accents
                        if (gain_dist(rng_) < 0.6f) {
                            std::vector<std::string> hat_types = {"C", "A", "O"};
                            std::string hat = hat_types[static_cast<int>(gain_dist(rng_) * hat_types.size())];
                            add_sample(offset + i, "hihat", hat, 0.3f + gain_dist(rng_) * 0.25f);
                        }

                        // Occasional kicks for emphasis
                        if ((i == 8 || i == 12 || i == 15) && gain_dist(rng_) < 0.6f) {
                            add_sample(offset + i, "kick", "", 0.7f + gain_dist(rng_) * 0.3f);
                        }
                    }
                }
            }
            break;
        }

        case PatternType::JUNGLE: {
            // Generate 4 bars
            for (int bar = 0; bar < 4; ++bar) {
                int offset = bar * 16;

                // Standard jungle pattern for all bars
                std::vector<int> kick_steps = {0, 6, 10, 13};
                for (int step : kick_steps) {
                    add_sample(offset + step, "kick", "", 0.7f + gain_dist(rng_) * 0.4f);
                }

                add_sample(offset + 4, "snare", "", 0.85f + gain_dist(rng_) * 0.3f);
                add_sample(offset + 12, "snare", "", 0.85f + gain_dist(rng_) * 0.3f);

                for (int step = 0; step < 16; step += 2) {
                    std::string var = (step % 4 == 0) ? "C" : "A";
                    float base_gain = (step % 4 == 0) ? 0.6f : 0.3f;
                    float gain = base_gain * (0.8f + gain_dist(rng_) * 0.5f);
                    add_sample(offset + step, "hihat", var, gain);
                }

                add_sample(offset + 15, "hihat", "C", 0.4f + gain_dist(rng_) * 0.3f);

                if (gain_dist(rng_) < 0.6f) {
                    add_sample(offset + 14, "roll", "", 0.4f + gain_dist(rng_) * 0.35f);
                }
                if (gain_dist(rng_) < 0.5f) {
                    std::vector<int> positions = {7, 11, 15};
                    int pos = positions[static_cast<int>(gain_dist(rng_) * positions.size())];
                    add_sample(offset + pos, "hihat", "A", 0.15f + gain_dist(rng_) * 0.25f);
                }
            }
            break;
        }

        case PatternType::TECHNO: {
            // Generate 4 bars
            for (int bar = 0; bar < 4; ++bar) {
                int offset = bar * 16;

                // 4 on the floor
                for (int beat : {0, 4, 8, 12}) {
                    add_sample(offset + beat, "kick", "H", 0.9f + gain_dist(rng_) * 0.2f);
                }

                add_sample(offset + 4, "snare", "", 0.55f + gain_dist(rng_) * 0.3f);
                add_sample(offset + 12, "snare", "", 0.55f + gain_dist(rng_) * 0.3f);

                for (int step : {2, 6, 10, 14}) {
                    add_sample(offset + step, "hihat", "C", 0.35f + gain_dist(rng_) * 0.3f);
                }

                for (int step : {1, 3, 5, 7, 9, 11, 13, 15}) {
                    if (gain_dist(rng_) < 0.7f) {
                        add_sample(offset + step, "hihat", "C", 0.2f + gain_dist(rng_) * 0.25f);
                    }
                }

                add_sample(offset + 15, "hihat", "O", 0.5f + gain_dist(rng_) * 0.3f);

                if (gain_dist(rng_) < 0.6f) {
                    add_sample(offset + 6, "hihat", "O", 0.3f + gain_dist(rng_) * 0.3f);
                }
                if (gain_dist(rng_) < 0.5f) {
                    for (int step : {0, 8}) {
                        add_sample(offset + step, "ride", "", 0.2f + gain_dist(rng_) * 0.25f);
                    }
                }
            }
            break;
        }

        case PatternType::BOOM_BAP: {
            // Generate 4 bars
            for (int bar = 0; bar < 4; ++bar) {
                int offset = bar * 16;

                add_sample(offset + 0, "kick", "H", 0.9f + gain_dist(rng_) * 0.25f);
                add_sample(offset + 8, "kick", "H", 0.9f + gain_dist(rng_) * 0.25f);

                add_sample(offset + 4, "snare", "H", 0.85f + gain_dist(rng_) * 0.3f);
                add_sample(offset + 12, "snare", "H", 0.85f + gain_dist(rng_) * 0.3f);

                for (int step : {0, 2, 4, 6, 8, 10, 12, 14}) {
                    add_sample(offset + step, "hihat", "C", 0.35f + gain_dist(rng_) * 0.3f);
                }

                add_sample(offset + 15, "hihat", "C", 0.5f + gain_dist(rng_) * 0.3f);

                if (gain_dist(rng_) < 0.7f) {
                    add_sample(offset + 6, "kick", "L", 0.25f + gain_dist(rng_) * 0.3f);
                }
                if (gain_dist(rng_) < 0.7f) {
                    add_sample(offset + 14, "kick", "L", 0.35f + gain_dist(rng_) * 0.3f);
                }
                if (gain_dist(rng_) < 0.6f) {
                    std::vector<int> positions = {1, 3, 5, 7, 9, 11, 13, 15};
                    int pos = positions[static_cast<int>(gain_dist(rng_) * positions.size())];
                    add_sample(offset + pos, "hihat", "O", 0.15f + gain_dist(rng_) * 0.25f);
                }
            }
            break;
        }
    }

    // Add voice segments if enabled
    if (params.voice_enabled) {
        std::lock_guard<std::mutex> lock(voice_mutex_);
        for (const auto& seg : voice_segments_) {
            int start = seg.step * samples_per_step;

            int step = seg.step;
            if (params.swing_amount > 0.0f && (step == 2 || step == 6 || step == 10 || step == 14)) {
                start += static_cast<int>(params.swing_amount * samples_per_step);
            }

            if (start >= pattern_length) continue;

            int length = std::min(static_cast<int>(seg.audio.size()), pattern_length - start);
            for (int i = 0; i < length; ++i) {
                pattern[start + i] += seg.audio[i] * 0.8f;
            }
        }
    }

    // Apply rest pattern with 3ms fade in/out
    if (!rest_pattern_.empty()) {
        // 計算 3ms 的 sample 數量: 3ms * 44100Hz / 1000 = 132.3 samples
        int fade_samples = static_cast<int>(0.003f * sample_rate_);

        for (int rest_step : rest_pattern_) {
            int start = rest_step * samples_per_step;
            int end = start + samples_per_step;
            if (end > pattern_length) end = pattern_length;

            // Fade out 前 3ms
            int fade_out_start = std::max(0, start - fade_samples);
            int fade_out_end = start;
            for (int i = fade_out_start; i < fade_out_end && i < pattern_length; ++i) {
                float ratio = static_cast<float>(fade_out_end - i) / fade_samples;
                pattern[i] *= ratio;
            }

            // Rest 區段靜音
            for (int i = start; i < end; ++i) {
                pattern[i] = 0.0f;
            }

            // Fade in 後 3ms
            int fade_in_start = end;
            int fade_in_end = std::min(pattern_length, end + fade_samples);
            for (int i = fade_in_start; i < fade_in_end; ++i) {
                float ratio = static_cast<float>(i - fade_in_start) / fade_samples;
                pattern[i] *= ratio;
            }
        }
    }

    // Normalize
    float max_val = 0.0f;
    for (float s : pattern) {
        max_val = std::max(max_val, std::abs(s));
    }
    if (max_val > 0.0f) {
        for (float& s : pattern) {
            s = s / max_val * 0.7f;
        }
    }
}

void BreakbeatEngine::generate_latin_pattern(const RealtimeParams& params, std::vector<float>& pattern) {
    int samples_per_step = calculate_samples_per_step(params.bpm);
    int pattern_length = samples_per_step * 16;

    pattern.assign(pattern_length, 0.0f);

    std::uniform_real_distribution<float> gain_dist(0.0f, 1.0f);

    // Latin samples (snare/tom only)
    std::vector<std::string> latin_categories = {"snare", "tom"};
    std::vector<DrumSample*> latin_samples;

    for (const auto& cat : latin_categories) {
        if (samples_.find(cat) != samples_.end()) {
            for (const auto& s : samples_[cat]) {
                latin_samples.push_back(s.get());
            }
        }
    }

    if (latin_samples.empty()) return;

    auto add_mono = [&](int step, float gain) {
        if (latin_samples.empty()) return;

        std::uniform_int_distribution<> dist(0, latin_samples.size() - 1);
        DrumSample* sample = latin_samples[dist(rng_)];

        int start = step * samples_per_step;

        if (params.swing_amount > 0.0f && (step == 2 || step == 6 || step == 10 || step == 14)) {
            start += static_cast<int>(params.swing_amount * samples_per_step);
        }

        if (start >= pattern_length) return;

        std::vector<float> audio = sample->audio;

        // Apply gain
        for (float& s : audio) {
            s *= gain;
        }

        // Monophonic - clear previous
        int length = std::min(static_cast<int>(audio.size()), pattern_length - start);
        for (int i = 0; i < length; ++i) {
            pattern[start + i] = audio[i];
        }
    };

    // Generate pattern
    switch (params.latin_pattern_type) {
        case LatinPatternType::SAMBA: {
            std::vector<int> steps = {0, 2, 4, 6, 7, 9, 11, 13, 14, 15}; // 加入最後一拍
            for (int step : steps) {
                float gain = (step % 4 == 0) ? 0.9f : (0.5f + gain_dist(rng_) * 0.2f);
                add_mono(step, gain);
            }
            break;
        }

        case LatinPatternType::BOSSA: {
            std::vector<int> steps = {0, 3, 6, 8, 11, 13, 15}; // 加入15
            for (int step : steps) {
                float gain = (step % 4 == 0) ? 0.7f : (0.4f + gain_dist(rng_) * 0.2f);
                add_mono(step, gain);
            }
            break;
        }

        case LatinPatternType::SALSA: {
            std::vector<int> steps = {0, 3, 7, 10, 12, 15}; // 加入15
            for (int step : steps) {
                float gain = (step == 0 || step == 7) ? 0.85f : (0.5f + gain_dist(rng_) * 0.2f);
                add_mono(step, gain);
            }
            break;
        }
    }

    // Add voice segments
    if (params.voice_enabled) {
        std::lock_guard<std::mutex> lock(voice_mutex_);
        for (const auto& seg : voice_segments_) {
            int start = seg.step * samples_per_step;

            if (seg.step % 2 == 1 && params.swing_amount > 0.0f) {
                start += static_cast<int>(params.swing_amount * samples_per_step);
            }

            if (start >= pattern_length) continue;

            int length = std::min(static_cast<int>(seg.audio.size()), pattern_length - start);
            for (int i = 0; i < length; ++i) {
                pattern[start + i] += seg.audio[i] * 0.8f;
            }
        }
    }

    // Apply rest pattern with 3ms fade in/out
    if (!rest_pattern_.empty()) {
        // 計算 3ms 的 sample 數量: 3ms * 44100Hz / 1000 = 132.3 samples
        int fade_samples = static_cast<int>(0.003f * sample_rate_);

        for (int rest_step : rest_pattern_) {
            int start = rest_step * samples_per_step;
            int end = start + samples_per_step;
            if (end > pattern_length) end = pattern_length;

            // Fade out 前 3ms
            int fade_out_start = std::max(0, start - fade_samples);
            int fade_out_end = start;
            for (int i = fade_out_start; i < fade_out_end && i < pattern_length; ++i) {
                float ratio = static_cast<float>(fade_out_end - i) / fade_samples;
                pattern[i] *= ratio;
            }

            // Rest 區段靜音
            for (int i = start; i < end; ++i) {
                pattern[i] = 0.0f;
            }

            // Fade in 後 3ms
            int fade_in_start = end;
            int fade_in_end = std::min(pattern_length, end + fade_samples);
            for (int i = fade_in_start; i < fade_in_end; ++i) {
                float ratio = static_cast<float>(i - fade_in_start) / fade_samples;
                pattern[i] *= ratio;
            }
        }
    }

    // Normalize to 50% of main pattern
    float max_val = 0.0f;
    for (float s : pattern) {
        max_val = std::max(max_val, std::abs(s));
    }
    if (max_val > 0.0f) {
        for (float& s : pattern) {
            s = s / max_val * 0.25f;  // 50% of 0.5
        }
    }
}

void BreakbeatEngine::get_audio_chunk(float* output, int num_frames) {
    // 讀取當前參數 (thread-safe)
    RealtimeParams params;
    {
        std::lock_guard<std::mutex> lock(params_mutex_);
        params = params_;
    }

    // 檢查參數是否變化 (在處理音訊之前)
    bool params_changed =
        current_pattern_.empty() ||
        std::abs(params.rest_probability - last_params_.rest_probability) > 0.01f ||
        params.pattern_type != last_params_.pattern_type ||
        std::abs(params.swing_amount - last_params_.swing_amount) > 0.01f ||
        params.latin_enabled != last_params_.latin_enabled ||
        params.latin_pattern_type != last_params_.latin_pattern_type;

    // 計算當前 pattern 長度
    int pattern_length = calculate_pattern_length(params.bpm);

    // 重新生成 pattern 如果參數改變或為空或 BPM 改變
    if (params_changed || current_pattern_.empty() || current_pattern_.size() != static_cast<size_t>(pattern_length)) {
        std::cout << "[REGEN] Regenerating pattern - params_changed: " << params_changed
                  << ", empty: " << current_pattern_.empty()
                  << ", size mismatch: " << (current_pattern_.size() != static_cast<size_t>(pattern_length)) << std::endl;
        generate_rest_pattern(params.rest_probability);
        generate_pattern(params, current_pattern_);
        if (params.latin_enabled) {
            generate_latin_pattern(params, current_latin_pattern_);
        } else {
            current_latin_pattern_.clear();
        }

        // 不要重置 position，讓播放繼續，只在超出範圍時才調整
        if (pattern_position_ >= static_cast<int>(current_pattern_.size())) {
            pattern_position_ = 0;
        }

        last_params_ = params;
        pattern_length = calculate_pattern_length(params.bpm);
        next_param_check_position_ = 0;
    }

    // 計算 1/32 音符的 sample 數 (用於快速參數反應)
    int samples_per_32nd = calculate_samples_per_step(params.bpm) / 2;  // 1/16 / 2 = 1/32

    // Fill output buffer
    for (int i = 0; i < num_frames; ++i) {

        // Clamp position
        if (pattern_position_ >= static_cast<int>(current_pattern_.size())) {
            pattern_position_ = 0;
        }

        float sample = current_pattern_[pattern_position_];

        // Mix latin
        if (params.latin_enabled && !current_latin_pattern_.empty() &&
            pattern_position_ < static_cast<int>(current_latin_pattern_.size())) {
            sample += current_latin_pattern_[pattern_position_];
        }

        output[i] = sample;

        pattern_position_++;

        // Loop pattern at boundary
        if (pattern_position_ >= pattern_length) {
            pattern_position_ = 0;
            bar_count_++;

            // Regenerate for next loop with latest params
            {
                std::lock_guard<std::mutex> lock(params_mutex_);
                params = params_;
            }

            int new_pattern_length = calculate_pattern_length(params.bpm);

            generate_rest_pattern(params.rest_probability);
            generate_pattern(params, current_pattern_);
            if (params.latin_enabled) {
                generate_latin_pattern(params, current_latin_pattern_);
            } else {
                current_latin_pattern_.clear();
            }

            last_params_ = params;
            pattern_length = new_pattern_length;
            next_param_check_position_ = 0;
        }
    }

    // Apply compressor if enabled
    if (params.comp_enabled) {
        compressor_->process(output, num_frames);
    }
}

} // namespace breakbeat
