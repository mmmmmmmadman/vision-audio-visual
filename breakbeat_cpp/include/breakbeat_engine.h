#pragma once

#include <vector>
#include <string>
#include <memory>
#include <random>
#include <unordered_map>

namespace breakbeat {

// 鼓組樣本
struct DrumSample {
    std::string name;
    std::vector<float> audio;
    std::string category;

    DrumSample(const std::string& n, const std::vector<float>& a, const std::string& c)
        : name(n), audio(a), category(c) {}
};

// Pattern 類型
enum class PatternType {
    AMEN,
    JUNGLE,
    BOOM_BAP,
    TECHNO
};

// Latin Pattern 類型
enum class LatinPatternType {
    SAMBA,
    BOSSA,
    SALSA
};

// 即時參數結構 - 每次 get_audio_chunk 都會讀取
struct RealtimeParams {
    float bpm = 134.0f;
    PatternType pattern_type = PatternType::AMEN;
    int pattern_variation = 0;        // 0-9, ten variations per style
    LatinPatternType latin_pattern_type = LatinPatternType::SAMBA;
    bool latin_enabled = false;
    float latin_fill_amount = 1.0f;   // 0.0 to 1.0
    float rest_probability = 0.0f;
    float swing_amount = 0.0f;
    float ghost_notes = 0.1f;         // 0.0 to 1.0, default 10%
    bool voice_enabled = false;

    // LA-2A Compressor parameters (Compress mode only)
    bool comp_enabled = false;
    float comp_peak_reduction = 0.0f;  // 0.0 to 1.0
    float comp_gain = 0.0f;            // -20 to 20 dB
    float comp_mix = 1.0f;             // 0.0 to 1.0
};

// 語音片段
struct VoiceSegment {
    int step;
    std::vector<float> audio;

    VoiceSegment(int s, const std::vector<float>& a) : step(s), audio(a) {}
};

class BreakbeatEngine {
public:
    BreakbeatEngine(const std::string& sample_dir, int sample_rate = 44100);
    ~BreakbeatEngine();

    // 即時參數設定 - 直接生效
    void set_bpm(float bpm);
    void set_pattern_type(PatternType type);
    void set_pattern_variation(int variation);
    void set_latin_pattern_type(LatinPatternType type);
    void set_latin_enabled(bool enabled);
    void set_latin_fill_amount(float amount);
    void set_rest_probability(float prob);
    void set_swing_amount(float amount);
    void set_ghost_notes(float amount);
    void set_voice_enabled(bool enabled);

    // Compressor 參數設定 (LA-2A style)
    void set_comp_enabled(bool enabled);
    void set_comp_peak_reduction(float amount);  // 0.0 to 1.0
    void set_comp_gain(float db);                // -20 to 20 dB
    void set_comp_mix(float mix);                // 0.0 to 1.0

    // 語音片段設定
    void set_voice_segments(const std::vector<VoiceSegment>& segments);
    void clear_voice_segments();

    // 音訊生成 - 即時讀取最新參數
    void get_audio_chunk(float* output, int num_frames);

    // 資訊查詢
    int get_sample_rate() const { return sample_rate_; }
    int get_bar_count() const { return bar_count_; }

private:
    // 載入樣本
    void load_samples();

    // Pattern 生成 - 使用即時參數
    void generate_pattern(const RealtimeParams& params, std::vector<float>& pattern);
    void generate_latin_pattern(const RealtimeParams& params, std::vector<float>& pattern);

    // 效果處理
    void apply_pitch_shift(std::vector<float>& audio, float semitones);
    void add_fixed_fills(const RealtimeParams& params, std::vector<float>& pattern);
    float get_dynamic_curve(int bar);

    // 樣本選擇
    DrumSample* get_sample(const std::string& category, const std::string& variation = "");

    // 參數計算
    int calculate_samples_per_step(float bpm) const;
    int calculate_pattern_length(float bpm) const;

    // 成員變數
    std::string sample_dir_;
    int sample_rate_;

    // 即時參數 (atomic for thread-safety)
    RealtimeParams params_;
    std::mutex params_mutex_;

    // 樣本庫
    std::unordered_map<std::string, std::vector<std::shared_ptr<DrumSample>>> samples_;
    std::vector<std::shared_ptr<DrumSample>> all_samples_;

    // 播放狀態
    std::vector<float> current_pattern_;
    std::vector<float> current_latin_pattern_;
    int pattern_position_ = 0;
    int bar_count_ = 0;
    int last_fill_bar_ = -99;

    // 追蹤參數變化 (用於即時反應)
    RealtimeParams last_params_;
    int next_param_check_position_ = 0;

    // Latin Fill 追蹤
    float last_latin_fill_amount_ = 1.0f;
    std::vector<int> latin_active_steps_;

    // 語音片段
    std::vector<VoiceSegment> voice_segments_;
    std::mutex voice_mutex_;

    // Compressor
    std::unique_ptr<class Compressor> compressor_;

    // 隨機數生成器
    std::mt19937 rng_;

    // Rest pattern
    std::vector<int> rest_pattern_;

    void generate_rest_pattern(float probability);
};

} // namespace breakbeat
