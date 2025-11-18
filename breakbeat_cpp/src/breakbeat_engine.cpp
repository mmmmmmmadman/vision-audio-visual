#include "breakbeat_engine.h"
#include "compressor.h"
#include <sndfile.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <numeric>

namespace fs = std::filesystem;

namespace breakbeat {

BreakbeatEngine::BreakbeatEngine(const std::string& sample_dir, int sample_rate)
    : sample_dir_(sample_dir), sample_rate_(sample_rate) {

    // 初始化隨機數生成器
    rng_.seed(std::random_device{}());

    // 初始化 Compressor
    compressor_ = std::make_unique<Compressor>(sample_rate);

    // 載入樣本
    load_samples();

    std::cout << "BreakbeatEngine initialized: " << samples_.size()
              << " categories loaded" << std::endl;
}

BreakbeatEngine::~BreakbeatEngine() {
}

void BreakbeatEngine::load_samples() {
    // Category 映射
    std::unordered_map<std::string, std::vector<std::string>> category_map = {
        {"kick", {"1_Kick", "0_Trummer"}},
        {"snare", {"2_SN"}},
        {"roll", {"3_Roll"}},
        {"hihat", {"6_HH"}},
        {"ride", {"4_Ride"}},
        {"crash", {"5_Crash"}},
        {"tom", {"6_TM"}}
    };

    // 遍歷目錄
    for (const auto& entry : fs::directory_iterator(sample_dir_)) {
        if (entry.path().extension() != ".wav") continue;

        std::string filepath = entry.path().string();
        std::string filename = entry.path().filename().string();

        // 載入 WAV
        SF_INFO sf_info;
        SNDFILE* sf = sf_open(filepath.c_str(), SFM_READ, &sf_info);

        if (!sf) {
            std::cerr << "Failed to load: " << filename << std::endl;
            continue;
        }

        // 讀取音訊
        std::vector<float> audio(sf_info.frames * sf_info.channels);
        sf_readf_float(sf, audio.data(), sf_info.frames);
        sf_close(sf);

        // 轉換為 mono
        if (sf_info.channels > 1) {
            std::vector<float> mono(sf_info.frames);
            for (sf_count_t i = 0; i < sf_info.frames; ++i) {
                float sum = 0;
                for (int ch = 0; ch < sf_info.channels; ++ch) {
                    sum += audio[i * sf_info.channels + ch];
                }
                mono[i] = sum / sf_info.channels;
            }
            audio = std::move(mono);
        }

        // Resample 如果需要
        if (sf_info.samplerate != sample_rate_) {
            float ratio = static_cast<float>(sample_rate_) / sf_info.samplerate;
            size_t new_length = static_cast<size_t>(audio.size() * ratio);
            std::vector<float> resampled(new_length);

            // 簡單線性插值
            for (size_t i = 0; i < new_length; ++i) {
                float pos = i / ratio;
                size_t idx = static_cast<size_t>(pos);
                float frac = pos - idx;

                if (idx + 1 < audio.size()) {
                    resampled[i] = audio[idx] * (1.0f - frac) + audio[idx + 1] * frac;
                } else if (idx < audio.size()) {
                    resampled[i] = audio[idx];
                }
            }
            audio = std::move(resampled);
        }

        // Normalize
        float max_val = 0.0f;
        for (float sample : audio) {
            max_val = std::max(max_val, std::abs(sample));
        }
        if (max_val > 0.0f) {
            for (float& sample : audio) {
                sample /= max_val;
            }
        }

        // 判斷 category
        std::string category = "other";
        for (const auto& [cat, patterns] : category_map) {
            for (const auto& pattern : patterns) {
                if (filename.find(pattern) != std::string::npos) {
                    category = cat;
                    break;
                }
            }
            if (category != "other") break;
        }

        // 建立樣本
        auto sample = std::make_shared<DrumSample>(
            filename.substr(0, filename.length() - 4), // remove .wav
            audio,
            category
        );

        samples_[category].push_back(sample);
        all_samples_.push_back(sample);
    }

    std::cout << "Loaded " << all_samples_.size() << " samples" << std::endl;
}

DrumSample* BreakbeatEngine::get_sample(const std::string& category, const std::string& variation) {
    if (samples_.find(category) == samples_.end() || samples_[category].empty()) {
        return nullptr;
    }

    auto& candidates = samples_[category];

    // 過濾 variation
    if (!variation.empty()) {
        std::vector<std::shared_ptr<DrumSample>> filtered;
        for (const auto& s : candidates) {
            if (s->name.find(variation) != std::string::npos) {
                filtered.push_back(s);
            }
        }
        if (!filtered.empty()) {
            std::uniform_int_distribution<> dist(0, filtered.size() - 1);
            auto* selected = filtered[dist(rng_)].get();
            std::cout << "[SAMPLE] " << category << " + '" << variation << "' -> " << selected->name << std::endl;
            return selected;
        }
    }

    // 隨機選擇
    std::uniform_int_distribution<> dist(0, candidates.size() - 1);
    auto* selected = candidates[dist(rng_)].get();
    std::cout << "[SAMPLE] " << category << " (all) -> " << selected->name << std::endl;
    return selected;
}

int BreakbeatEngine::calculate_samples_per_step(float bpm) const {
    float beat_duration = 60.0f / bpm;
    float step_duration = beat_duration / 4.0f;
    return static_cast<int>(step_duration * sample_rate_);
}

int BreakbeatEngine::calculate_pattern_length(float bpm) const {
    return calculate_samples_per_step(bpm) * 64;  // 4 bars = 64 steps
}

void BreakbeatEngine::set_bpm(float bpm) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.bpm = bpm;
}

void BreakbeatEngine::set_pattern_type(PatternType type) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.pattern_type = type;
}

void BreakbeatEngine::set_latin_pattern_type(LatinPatternType type) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.latin_pattern_type = type;
}

void BreakbeatEngine::set_latin_enabled(bool enabled) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.latin_enabled = enabled;
}

void BreakbeatEngine::set_latin_fill_amount(float amount) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.latin_fill_amount = std::clamp(amount, 0.0f, 1.0f);
}

void BreakbeatEngine::set_rest_probability(float prob) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.rest_probability = std::clamp(prob, 0.0f, 1.0f);
}

void BreakbeatEngine::set_swing_amount(float amount) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.swing_amount = std::clamp(amount, 0.0f, 0.33f);
}

void BreakbeatEngine::set_ghost_notes(float amount) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.ghost_notes = std::clamp(amount, 0.0f, 1.0f);
}

void BreakbeatEngine::set_pattern_variation(int variation) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.pattern_variation = std::clamp(variation, 0, 9);
}

void BreakbeatEngine::set_voice_enabled(bool enabled) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.voice_enabled = enabled;
}

void BreakbeatEngine::set_voice_segments(const std::vector<VoiceSegment>& segments) {
    std::lock_guard<std::mutex> lock(voice_mutex_);
    voice_segments_ = segments;
}

void BreakbeatEngine::clear_voice_segments() {
    std::lock_guard<std::mutex> lock(voice_mutex_);
    voice_segments_.clear();
}

void BreakbeatEngine::set_comp_enabled(bool enabled) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.comp_enabled = enabled;
}

void BreakbeatEngine::set_comp_peak_reduction(float amount) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.comp_peak_reduction = std::clamp(amount, 0.0f, 1.0f);
    compressor_->set_peak_reduction(params_.comp_peak_reduction);
}

void BreakbeatEngine::set_comp_gain(float db) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.comp_gain = std::clamp(db, -20.0f, 20.0f);
    compressor_->set_gain(params_.comp_gain);
}

void BreakbeatEngine::set_comp_mix(float mix) {
    std::lock_guard<std::mutex> lock(params_mutex_);
    params_.comp_mix = std::clamp(mix, 0.0f, 1.0f);
    compressor_->set_mix(params_.comp_mix);
}

void BreakbeatEngine::apply_pitch_shift(std::vector<float>& audio, float semitones) {
    if (audio.empty() || std::abs(semitones) < 0.01f) return;

    // 計算 pitch shift ratio: 2^(semitones/12)
    float ratio = std::pow(2.0f, semitones / 12.0f);

    size_t new_length = static_cast<size_t>(audio.size() / ratio);
    if (new_length == 0) return;

    std::vector<float> shifted(new_length);

    // 使用線性插值重新採樣
    for (size_t i = 0; i < new_length; ++i) {
        float pos = i * ratio;
        size_t idx = static_cast<size_t>(pos);
        float frac = pos - idx;

        if (idx + 1 < audio.size()) {
            shifted[i] = audio[idx] * (1.0f - frac) + audio[idx + 1] * frac;
        } else if (idx < audio.size()) {
            shifted[i] = audio[idx];
        }
    }

    audio = std::move(shifted);
}

float BreakbeatEngine::get_dynamic_curve(int bar) {
    // 四小節動態曲線：1.0 -> 0.95 -> 1.05 -> 1.1
    switch (bar) {
        case 0: return 1.0f;   // Bar 1: 正常
        case 1: return 0.95f;  // Bar 2: 稍弱
        case 2: return 1.05f;  // Bar 3: 稍強
        case 3: return 1.1f;   // Bar 4: 最強
        default: return 1.0f;
    }
}

void BreakbeatEngine::generate_rest_pattern(float probability) {
    rest_pattern_.clear();

    if (probability <= 0.0f) return;

    // num_rests is based on steps within ONE bar (16 steps)
    int num_rests = static_cast<int>(16 * probability);
    if (num_rests == 0) return;

    // Build weak and strong beat lists for ONE bar
    std::vector<int> weak_beats = {1, 3, 5, 7, 9, 11, 13, 15};
    std::vector<int> strong_beats = {0, 2, 4, 6, 8, 10, 12, 14};

    // Create weighted selection (weak beats have 2x weight)
    std::vector<int> available_steps;
    available_steps.insert(available_steps.end(), weak_beats.begin(), weak_beats.end());
    available_steps.insert(available_steps.end(), weak_beats.begin(), weak_beats.end()); // 2x weight
    available_steps.insert(available_steps.end(), strong_beats.begin(), strong_beats.end());

    std::shuffle(available_steps.begin(), available_steps.end(), rng_);

    // Select steps within one bar
    std::vector<int> selected_steps;
    for (int i = 0; i < std::min(num_rests, static_cast<int>(available_steps.size())); ++i) {
        selected_steps.push_back(available_steps[i]);
    }

    // Apply these steps to all 4 bars, excluding fill positions
    // Fill positions: bar 1 beat 4 (steps 28-31), bar 3 beats 3-4 (steps 56-63)
    for (int bar = 0; bar < 4; ++bar) {
        int offset = bar * 16;
        for (int step : selected_steps) {
            int absolute_step = offset + step;

            // Skip fill positions
            bool is_fill_position = (absolute_step >= 28 && absolute_step <= 31) ||  // Bar 2 beat 4
                                   (absolute_step >= 56 && absolute_step <= 63);     // Bar 4 beats 3-4

            if (!is_fill_position) {
                rest_pattern_.push_back(absolute_step);
            }
        }
    }

    std::sort(rest_pattern_.begin(), rest_pattern_.end());
}

void BreakbeatEngine::add_fixed_fills(const RealtimeParams& params, std::vector<float>& pattern) {
    // 固定過門：
    // Bar 2 beat 4 (steps 28-31): 簡單過門
    // Bar 4 beats 3-4 (steps 56-63): 完整過門

    std::cout << "[FILL] add_fixed_fills called" << std::endl;

    int samples_per_step = calculate_samples_per_step(params.bpm);
    int pattern_length = pattern.size();
    std::uniform_real_distribution<float> prob_dist(0.0f, 1.0f);

    // Bar 2 過門：最後一拍
    {
        // 清空 bar 2 最後一拍
        for (int step = 28; step < 32; ++step) {
            int start_sample = step * samples_per_step;
            int end_sample = std::min((step + 1) * samples_per_step, pattern_length);
            for (int i = start_sample; i < end_sample; ++i) {
                pattern[i] = 0.0f;
            }
        }

        // 加入簡單的snare fill
        for (int step = 28; step < 32; ++step) {
            if (prob_dist(rng_) < 0.7f) {  // 70% 機率
                DrumSample* sample = get_sample("snare");
                if (sample) {
                    int start = step * samples_per_step;
                    if (step % 2 == 1 && params.swing_amount > 0.0f) {
                        start += static_cast<int>(params.swing_amount * samples_per_step);
                    }
                    if (start < pattern_length) {
                        std::vector<float> audio = sample->audio;
                        float gain = 0.65f + prob_dist(rng_) * 0.25f;
                        for (float& s : audio) s *= gain;

                        int length = std::min(static_cast<int>(audio.size()), pattern_length - start);
                        for (int j = 0; j < length; ++j) {
                            pattern[start + j] += audio[j];
                        }
                    }
                }
            }
        }
    }

    // Bar 4 過門：最後兩拍
    {
        // 清空 bar 4 最後兩拍
        for (int step = 56; step < 64; ++step) {
            int start_sample = step * samples_per_step;
            int end_sample = std::min((step + 1) * samples_per_step, pattern_length);
            for (int i = start_sample; i < end_sample; ++i) {
                pattern[i] = 0.0f;
            }
        }

        // 加入混合的fill（snare, tom, kick）
        std::vector<std::string> fill_cats = {"snare", "tom", "kick"};
        for (int step = 56; step < 64; ++step) {
            if (prob_dist(rng_) < 0.85f) {  // 85% 機率
                std::uniform_int_distribution<> cat_dist(0, fill_cats.size() - 1);
                DrumSample* sample = get_sample(fill_cats[cat_dist(rng_)]);

                if (sample) {
                    int start = step * samples_per_step;
                    if (step % 2 == 1 && params.swing_amount > 0.0f) {
                        start += static_cast<int>(params.swing_amount * samples_per_step);
                    }
                    if (start < pattern_length) {
                        std::vector<float> audio = sample->audio;
                        float gain = 0.7f + prob_dist(rng_) * 0.3f;
                        for (float& s : audio) s *= gain;

                        int length = std::min(static_cast<int>(audio.size()), pattern_length - start);
                        for (int j = 0; j < length; ++j) {
                            pattern[start + j] += audio[j];
                        }
                    }
                }
            }
        }

        // Bar 4 結尾加crash
        if (prob_dist(rng_) < 0.8f) {
            DrumSample* crash = get_sample("crash");
            if (crash) {
                int step = 63;
                int start = step * samples_per_step;
                if (step % 2 == 1 && params.swing_amount > 0.0f) {
                    start += static_cast<int>(params.swing_amount * samples_per_step);
                }
                if (start < pattern_length) {
                    std::vector<float> audio = crash->audio;
                    for (float& s : audio) s *= 0.6f;

                    int length = std::min(static_cast<int>(audio.size()), pattern_length - start);
                    for (int j = 0; j < length; ++j) {
                        pattern[start + j] += audio[j];
                    }
                }
            }
        }
    }
}

} // namespace breakbeat
