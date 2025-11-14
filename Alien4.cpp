#include "plugin.hpp"
#include "widgets/Knobs.hpp"
#include "widgets/PanelTheme.hpp"
#include <random>

using namespace rack;
using namespace rack::engine;
using namespace rack::math;

struct EnhancedTextLabel : TransparentWidget {
    std::string text;
    float fontSize;
    NVGcolor color;
    bool bold;

    EnhancedTextLabel(Vec pos, Vec size, std::string text, float fontSize = 12.f,
                      NVGcolor color = nvgRGB(255, 255, 255), bool bold = true) {
        box.pos = pos;
        box.size = size;
        this->text = text;
        this->fontSize = fontSize;
        this->color = color;
        this->bold = bold;
    }

    void draw(const DrawArgs &args) override {
        nvgFontSize(args.vg, fontSize);
        nvgFontFaceId(args.vg, APP->window->uiFont->handle);
        nvgTextAlign(args.vg, NVG_ALIGN_CENTER | NVG_ALIGN_MIDDLE);
        nvgFillColor(args.vg, color);

        if (bold) {
            float offset = 0.3f;
            nvgText(args.vg, box.size.x / 2.f - offset, box.size.y / 2.f, text.c_str(), NULL);
            nvgText(args.vg, box.size.x / 2.f + offset, box.size.y / 2.f, text.c_str(), NULL);
            nvgText(args.vg, box.size.x / 2.f, box.size.y / 2.f - offset, text.c_str(), NULL);
            nvgText(args.vg, box.size.x / 2.f, box.size.y / 2.f + offset, text.c_str(), NULL);
            nvgText(args.vg, box.size.x / 2.f, box.size.y / 2.f, text.c_str(), NULL);
        } else {
            nvgText(args.vg, box.size.x / 2.f, box.size.y / 2.f, text.c_str(), NULL);
        }
    }
};

// Slice structure
struct Slice {
    int startSample = 0;
    int endSample = 0;
    float peakAmplitude = 0.0f;
    bool active = false;
};

// Voice structure for polyphonic playback
struct Voice {
    int sliceIndex = 0;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    float speedMultiplier = 1.0f;
};

// Custom ParamQuantity for MIN_SLICE_TIME with exponential curve
struct MinSliceTimeParamQuantity : ParamQuantity {
    float getDisplayValue() override {
        float knobValue = getValue();
        if (knobValue <= 0.5f) {
            // Left half: exponential from 0.001 to 1.0
            float t = knobValue * 2.0f;
            return 0.001f * std::pow(1000.0f, t);
        } else {
            // Right half: linear from 1.0 to 5.0
            float t = (knobValue - 0.5f) * 2.0f;
            return 1.0f + t * 4.0f;
        }
    }

    void setDisplayValue(float displayValue) override {
        if (displayValue <= 1.0f) {
            // Left half: inverse of exponential
            float t = std::log(displayValue / 0.001f) / std::log(1000.0f);
            setValue(t * 0.5f);
        } else {
            // Right half: inverse of linear
            float t = (displayValue - 1.0f) / 4.0f;
            setValue(0.5f + t * 0.5f);
        }
    }
};

// Delay processor
struct DelayProcessor {
    static constexpr int DELAY_BUFFER_SIZE = 96000;
    float buffer[DELAY_BUFFER_SIZE];
    int writeIndex = 0;

    DelayProcessor() { reset(); }

    void reset() {
        for (int i = 0; i < DELAY_BUFFER_SIZE; i++) {
            buffer[i] = 0.0f;
        }
        writeIndex = 0;
    }

    float process(float input, float delayTime, float feedback, float sampleRate) {
        int delaySamples = (int)(delayTime * sampleRate);
        delaySamples = clamp(delaySamples, 1, DELAY_BUFFER_SIZE - 1);

        int readIndex = (writeIndex - delaySamples + DELAY_BUFFER_SIZE) % DELAY_BUFFER_SIZE;
        float delayedSignal = buffer[readIndex];

        buffer[writeIndex] = input + delayedSignal * feedback;
        writeIndex = (writeIndex + 1) % DELAY_BUFFER_SIZE;

        return delayedSignal;
    }
};

// Reverb processor
struct ReverbProcessor {
    static constexpr int COMB_1_SIZE = 1557;
    static constexpr int COMB_2_SIZE = 1617;
    static constexpr int COMB_3_SIZE = 1491;
    static constexpr int COMB_4_SIZE = 1422;

    float combBuffer1[COMB_1_SIZE];
    float combBuffer2[COMB_2_SIZE];
    float combBuffer3[COMB_3_SIZE];
    float combBuffer4[COMB_4_SIZE];

    int combIndex1 = 0, combIndex2 = 0, combIndex3 = 0, combIndex4 = 0;
    float combLp1 = 0.0f, combLp2 = 0.0f, combLp3 = 0.0f, combLp4 = 0.0f;
    float hpState = 0.0f;

    static constexpr int ALLPASS_1_SIZE = 556;
    static constexpr int ALLPASS_2_SIZE = 441;

    float allpassBuffer1[ALLPASS_1_SIZE];
    float allpassBuffer2[ALLPASS_2_SIZE];

    int allpassIndex1 = 0, allpassIndex2 = 0;

    ReverbProcessor() { reset(); }

    void reset() {
        for (int i = 0; i < COMB_1_SIZE; i++) combBuffer1[i] = 0.0f;
        for (int i = 0; i < COMB_2_SIZE; i++) combBuffer2[i] = 0.0f;
        for (int i = 0; i < COMB_3_SIZE; i++) combBuffer3[i] = 0.0f;
        for (int i = 0; i < COMB_4_SIZE; i++) combBuffer4[i] = 0.0f;
        for (int i = 0; i < ALLPASS_1_SIZE; i++) allpassBuffer1[i] = 0.0f;
        for (int i = 0; i < ALLPASS_2_SIZE; i++) allpassBuffer2[i] = 0.0f;

        combIndex1 = combIndex2 = combIndex3 = combIndex4 = 0;
        allpassIndex1 = allpassIndex2 = 0;
        combLp1 = combLp2 = combLp3 = combLp4 = 0.0f;
        hpState = 0.0f;
    }

    float processComb(float input, float* buffer, int size, int& index, float feedback, float& lp, float damping) {
        float output = buffer[index];
        lp = lp + (output - lp) * damping;
        buffer[index] = input + lp * feedback;
        index = (index + 1) % size;
        return output;
    }

    float processAllpass(float input, float* buffer, int size, int& index, float gain) {
        float delayed = buffer[index];
        float output = -input * gain + delayed;
        buffer[index] = input + delayed * gain;
        index = (index + 1) % size;
        return output;
    }

    float process(float input, float roomSize, float damping, float decay, float sampleRate) {
        float feedback = 0.5f + decay * 0.485f;
        float dampingCoeff = 0.05f + damping * 0.9f;
        float roomScale = 0.3f + roomSize * 1.4f;

        float roomInput = input * roomScale;
        float combOut = 0.0f;
        combOut += processComb(roomInput, combBuffer1, COMB_1_SIZE, combIndex1, feedback, combLp1, dampingCoeff);
        combOut += processComb(roomInput, combBuffer2, COMB_2_SIZE, combIndex2, feedback, combLp2, dampingCoeff);
        combOut += processComb(roomInput, combBuffer3, COMB_3_SIZE, combIndex3, feedback, combLp3, dampingCoeff);
        combOut += processComb(roomInput, combBuffer4, COMB_4_SIZE, combIndex4, feedback, combLp4, dampingCoeff);

        combOut *= 0.25f;

        float diffused = combOut;
        diffused = processAllpass(diffused, allpassBuffer1, ALLPASS_1_SIZE, allpassIndex1, 0.5f);
        diffused = processAllpass(diffused, allpassBuffer2, ALLPASS_2_SIZE, allpassIndex2, 0.5f);

        float hpCutoff = 100.0f / (sampleRate * 0.5f);
        hpCutoff = clamp(hpCutoff, 0.001f, 0.1f);
        hpState += (diffused - hpState) * hpCutoff;
        float hpOutput = diffused - hpState;

        return hpOutput;
    }
};

struct Alien4 : Module {
    int panelTheme = 0;

    enum ParamIds {
        REC_PARAM,
        SCAN_PARAM,
        MIN_SLICE_TIME_PARAM,
        MIX_PARAM,
        FDBK_PARAM,
        EQ_LOW_PARAM,
        EQ_MID_PARAM,
        EQ_HIGH_PARAM,
        SPEED_PARAM,
        POLY_PARAM,
        DELAY_TIME_L_PARAM,
        DELAY_TIME_R_PARAM,
        DELAY_FEEDBACK_PARAM,
        DELAY_WET_PARAM,
        REVERB_DECAY_PARAM,
        REVERB_WET_PARAM,
        NUM_PARAMS
    };

    enum InputIds {
        LEFT_INPUT,
        NUM_INPUTS
    };

    enum OutputIds {
        LEFT_OUTPUT,
        RIGHT_OUTPUT,
        NUM_OUTPUTS
    };

    enum LightIds {
        REC_LIGHT,
        NUM_LIGHTS
    };

    // Loop buffer (mono)
    static constexpr int LOOP_BUFFER_SIZE = 2880000; // 60 seconds at 48kHz
    std::vector<float> loopBuffer;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    int recordedLength = 0;
    int lastScanTargetIndex = -1;

    // Temporary recording buffer (mono)
    std::vector<float> tempBuffer;
    std::vector<Slice> tempSlices;
    int tempRecordPosition = 0;
    int tempRecordedLength = 0;
    float tempLastAmplitude = 0.0f;

    // Slices
    std::vector<Slice> slices;
    int currentSliceIndex = 0;
    float lastAmplitude = 0.0f;
    float lastMinSliceTime = 0.05f;

    // Polyphonic voices
    std::vector<Voice> voices;
    int numVoices = 1;
    std::default_random_engine randomEngine;
    float lastScanValue = -1.0f;

    // EQ filters (stereo)
    dsp::TBiquadFilter<> eqLowL, eqLowR;
    dsp::TBiquadFilter<> eqMidL, eqMidR;
    dsp::TBiquadFilter<> eqHighL, eqHighR;

    // Effects processors
    DelayProcessor delayL, delayR;
    ReverbProcessor reverbL, reverbR;

    // State
    bool isRecording = false;
    dsp::SchmittTrigger recTrigger;

    // Feedback state
    float lastOutputL = 0.0f;
    float lastOutputR = 0.0f;

    Alien4() {
        config(NUM_PARAMS, NUM_INPUTS, NUM_OUTPUTS, NUM_LIGHTS);

        configParam(REC_PARAM, 0.0f, 1.0f, 0.0f, "Record");
        configParam(SCAN_PARAM, 0.0f, 1.0f, 0.0f, "Slice Scan", "%", 0.f, 100.f);
        // Use internal range 0-1, convert to exponential 0.001-5.0 when reading
        configParam<MinSliceTimeParamQuantity>(MIN_SLICE_TIME_PARAM, 0.0f, 1.0f, 0.5f, "Min Slice Time", " s");
        configParam(MIX_PARAM, 0.0f, 1.0f, 0.0f, "Mix", "%", 0.f, 100.f);
        configParam(FDBK_PARAM, 0.0f, 1.0f, 0.0f, "Feedback", "%", 0.f, 100.f);
        configParam(EQ_LOW_PARAM, -20.0f, 20.0f, 0.0f, "Low EQ", " dB");
        configParam(EQ_MID_PARAM, -20.0f, 20.0f, 0.0f, "Mid EQ", " dB");
        configParam(EQ_HIGH_PARAM, -20.0f, 20.0f, 0.0f, "High EQ", " dB");
        configParam(SPEED_PARAM, -8.0f, 8.0f, 1.0f, "Speed", "x");
        configParam(POLY_PARAM, 1.0f, 8.0f, 1.0f, "Polyphonic Voices");
        paramQuantities[POLY_PARAM]->snapEnabled = true;
        configParam(DELAY_TIME_L_PARAM, 0.001f, 2.0f, 0.25f, "Delay Time L", " s");
        configParam(DELAY_TIME_R_PARAM, 0.001f, 2.0f, 0.25f, "Delay Time R", " s");
        configParam(DELAY_FEEDBACK_PARAM, 0.0f, 0.95f, 0.3f, "Delay Feedback", "%", 0.f, 100.f);
        configParam(DELAY_WET_PARAM, 0.0f, 1.0f, 0.5f, "Delay Wet/Dry", "%", 0.f, 100.f);
        configParam(REVERB_DECAY_PARAM, 0.0f, 1.0f, 0.6f, "Decay");
        configParam(REVERB_WET_PARAM, 0.0f, 1.0f, 0.5f, "Reverb Wet/Dry", "%", 0.f, 100.f);

        configInput(LEFT_INPUT, "Audio");
        configOutput(LEFT_OUTPUT, "Left Audio");
        configOutput(RIGHT_OUTPUT, "Right Audio");

        configLight(REC_LIGHT, "Recording");

        loopBuffer.resize(LOOP_BUFFER_SIZE, 0.0f);
        tempBuffer.resize(LOOP_BUFFER_SIZE, 0.0f);

        randomEngine.seed(std::random_device()());
    }

    void onReset() override {
        std::fill(loopBuffer.begin(), loopBuffer.end(), 0.0f);
        playbackPosition = 0;
        playbackPhase = 0.0f;
        recordedLength = 0;
        isRecording = false;
        lastOutputL = 0.0f;
        lastOutputR = 0.0f;
        slices.clear();
        currentSliceIndex = 0;
        lastAmplitude = 0.0f;
        lastScanTargetIndex = -1;
        voices.clear();
        numVoices = 1;
        delayL.reset();
        delayR.reset();
        reverbL.reset();
        reverbR.reset();
    }

    json_t* dataToJson() override {
        json_t* rootJ = json_object();
        json_object_set_new(rootJ, "panelTheme", json_integer(panelTheme));
        return rootJ;
    }

    void dataFromJson(json_t* rootJ) override {
        json_t* themeJ = json_object_get(rootJ, "panelTheme");
        if (themeJ) {
            panelTheme = json_integer_value(themeJ);
        }
    }

    void rescanSlices(float threshold, float minSliceTime, float sampleRate) {
        if (recordedLength <= 0) return;

        slices.clear();
        int minSliceSamples = (int)(minSliceTime * sampleRate);
        float lastAmp = 0.0f;

        for (int pos = 0; pos < recordedLength; pos++) {
            float currentAmp = std::abs(loopBuffer[pos]);

            if (lastAmp < threshold && currentAmp >= threshold) {
                if (!slices.empty() && slices.back().active) {
                    int sliceLength = pos - slices.back().startSample;
                    if (sliceLength >= minSliceSamples) {
                        slices.back().endSample = pos - 1;
                    } else {
                        slices.pop_back();
                    }
                }

                if (slices.empty() || slices.back().endSample > 0) {
                    Slice newSlice;
                    newSlice.startSample = pos;
                    newSlice.active = true;
                    newSlice.peakAmplitude = 0.0f;
                    slices.push_back(newSlice);
                }
            }

            if (!slices.empty() && slices.back().active && slices.back().endSample == 0) {
                slices.back().peakAmplitude = std::max(slices.back().peakAmplitude, currentAmp);
            }

            lastAmp = currentAmp;
        }

        if (!slices.empty() && slices.back().active && slices.back().endSample == 0) {
            int sliceLength = recordedLength - slices.back().startSample;
            if (sliceLength >= minSliceSamples) {
                slices.back().endSample = recordedLength - 1;
            } else {
                slices.pop_back();
            }
        }

        if (currentSliceIndex >= (int)slices.size()) {
            currentSliceIndex = slices.empty() ? 0 : (int)slices.size() - 1;
        }
    }

    // Convert MIN_SLICE_TIME knob value (0-1) to actual time (0.001-5.0 seconds)
    // Left half (0-0.5): 0.001 to 1.0 seconds (exponential)
    // Right half (0.5-1.0): 1.0 to 5.0 seconds (linear)
    float getMinSliceTime() {
        float knobValue = params[MIN_SLICE_TIME_PARAM].getValue();
        if (knobValue <= 0.5f) {
            // Left half: exponential from 0.001 to 1.0
            float t = knobValue * 2.0f; // 0 to 1
            return 0.001f * std::pow(1000.0f, t); // 0.001 to 1.0
        } else {
            // Right half: linear from 1.0 to 5.0
            float t = (knobValue - 0.5f) * 2.0f; // 0 to 1
            return 1.0f + t * 4.0f; // 1.0 to 5.0
        }
    }

    void redistributeVoices() {
        if (slices.empty() || numVoices <= 1 || voices.empty()) return;

        std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
        std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

        for (int i = 1; i < numVoices; i++) {
            // Find a valid active slice
            int targetSliceIndex = sliceDist(randomEngine);
            int attempts = 0;
            while (attempts < 20 && (!slices[targetSliceIndex].active ||
                   slices[targetSliceIndex].startSample >= recordedLength)) {
                targetSliceIndex = sliceDist(randomEngine);
                attempts++;
            }

            // Safety check
            if (!slices[targetSliceIndex].active ||
                slices[targetSliceIndex].startSample >= recordedLength) {
                continue;
            }

            voices[i].sliceIndex = targetSliceIndex;
            voices[i].playbackPosition = slices[targetSliceIndex].startSample;
            voices[i].playbackPhase = 0.0f;
            voices[i].speedMultiplier = speedDist(randomEngine);
        }
    }

    void process(const ProcessArgs& args) override {
        // Handle REC button
        if (recTrigger.process(params[REC_PARAM].getValue())) {
            isRecording = !isRecording;
            if (isRecording) {
                // Start recording: clear temp buffer
                std::fill(tempBuffer.begin(), tempBuffer.end(), 0.0f);
                tempSlices.clear();
                tempRecordPosition = 0;
                tempRecordedLength = 0;
                tempLastAmplitude = 0.0f;
            } else {
                // Stop recording: finalize last slice and copy temp buffers to main buffers
                float minSliceTime = getMinSliceTime();
                int minSliceSamples = (int)(minSliceTime * args.sampleRate);

                // Close the last slice if it exists and is still open
                if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                    int sliceLength = tempRecordedLength - tempSlices.back().startSample;
                    if (sliceLength >= minSliceSamples) {
                        tempSlices.back().endSample = tempRecordedLength - 1;
                    } else {
                        tempSlices.pop_back();
                    }
                }

                std::copy(tempBuffer.begin(), tempBuffer.end(), loopBuffer.begin());
                slices = tempSlices;
                recordedLength = tempRecordedLength;
                playbackPosition = 0;
                playbackPhase = 0.0f;
                currentSliceIndex = 0;
                lastAmplitude = 0.0f;

                // Reset all voices to valid initial state
                for (int i = 0; i < (int)voices.size(); i++) {
                    voices[i].sliceIndex = 0;
                    voices[i].playbackPosition = 0;
                    voices[i].playbackPhase = 0.0f;
                    voices[i].speedMultiplier = 1.0f;
                }

                // Redistribute voices if in poly mode
                if (numVoices > 1) {
                    redistributeVoices();
                }
            }
        }

        lights[REC_LIGHT].setBrightness(isRecording ? 1.0f : 0.0f);

        // Get input
        float input = inputs[LEFT_INPUT].getVoltage();

        // Check if minSliceTime changed
        float threshold = 0.5f; // Fixed threshold
        float minSliceTime = getMinSliceTime();

        if (!isRecording && recordedLength > 0 && std::abs(minSliceTime - lastMinSliceTime) > 0.001f) {
            rescanSlices(threshold, minSliceTime, args.sampleRate);
            redistributeVoices();
            lastMinSliceTime = minSliceTime;
        }

        // Recording with slice detection (to temp buffer)
        if (isRecording && tempRecordPosition < LOOP_BUFFER_SIZE) {
            tempBuffer[tempRecordPosition] = input;
            tempRecordedLength = tempRecordPosition + 1;

            float currentAmp = std::abs(input);

            float minSliceTime = getMinSliceTime();
            int minSliceSamples = (int)(minSliceTime * args.sampleRate);

            if (tempLastAmplitude < threshold && currentAmp >= threshold) {
                if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                    int sliceLength = tempRecordPosition - tempSlices.back().startSample;
                    if (sliceLength >= minSliceSamples) {
                        tempSlices.back().endSample = tempRecordPosition - 1;
                    } else {
                        // Slice too short, remove it
                        tempSlices.pop_back();
                    }
                }

                // Start new slice (only if previous one was closed or removed)
                if (tempSlices.empty() || tempSlices.back().endSample > 0) {
                    Slice newSlice;
                    newSlice.startSample = tempRecordPosition;
                    newSlice.active = true;
                    newSlice.peakAmplitude = 0.0f;
                    tempSlices.push_back(newSlice);
                }
            }

            if (!tempSlices.empty() && tempSlices.back().active && tempSlices.back().endSample == 0) {
                tempSlices.back().peakAmplitude = std::max(tempSlices.back().peakAmplitude, currentAmp);
            }

            tempLastAmplitude = currentAmp;
            tempRecordPosition++;
        }

        // Handle polyphonic voices count
        int newNumVoices = (int)params[POLY_PARAM].getValue();
        newNumVoices = clamp(newNumVoices, 1, 8);

        if (newNumVoices != numVoices) {
            numVoices = newNumVoices;
            voices.resize(numVoices);

            if (!slices.empty() && numVoices > 1) {
                std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
                std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

                for (int i = 0; i < numVoices; i++) {
                    if (i == 0) {
                        voices[i].sliceIndex = currentSliceIndex;
                        voices[i].playbackPosition = playbackPosition;
                        voices[i].playbackPhase = playbackPhase;
                        voices[i].speedMultiplier = 1.0f;
                    } else {
                        // Find a valid active slice
                        int targetSliceIndex = sliceDist(randomEngine);
                        int attempts = 0;
                        while (attempts < 20 && (targetSliceIndex >= (int)slices.size() ||
                               !slices[targetSliceIndex].active ||
                               slices[targetSliceIndex].startSample >= recordedLength)) {
                            targetSliceIndex = sliceDist(randomEngine);
                            attempts++;
                        }

                        // Safety check - use voice 0's slice if no valid slice found
                        if (targetSliceIndex >= (int)slices.size() ||
                            !slices[targetSliceIndex].active ||
                            slices[targetSliceIndex].startSample >= recordedLength) {
                            targetSliceIndex = currentSliceIndex;
                        }

                        voices[i].sliceIndex = targetSliceIndex;
                        voices[i].playbackPosition = slices[targetSliceIndex].startSample;
                        voices[i].playbackPhase = 0.0f;
                        voices[i].speedMultiplier = speedDist(randomEngine);
                    }
                }
            } else {
                for (int i = 0; i < numVoices; i++) {
                    voices[i].sliceIndex = currentSliceIndex;
                    voices[i].playbackPosition = playbackPosition;
                    voices[i].playbackPhase = playbackPhase;
                    voices[i].speedMultiplier = 1.0f;
                }
            }
        }

        // SCAN functionality
        float scanValue = params[SCAN_PARAM].getValue();

        // Check if SCAN value changed
        if (std::abs(scanValue - lastScanValue) > 0.001f) {
            redistributeVoices();
            lastScanValue = scanValue;
        }

        if (slices.size() > 1) {
            bool useManualScan = scanValue > 0.01f;

            if (useManualScan) {
                int targetSliceIndex = (int)std::round(scanValue * (slices.size() - 1));
                targetSliceIndex = clamp(targetSliceIndex, 0, (int)slices.size() - 1);

                if (targetSliceIndex != lastScanTargetIndex && slices[targetSliceIndex].active) {
                    currentSliceIndex = targetSliceIndex;
                    playbackPosition = slices[targetSliceIndex].startSample;
                    playbackPhase = 0.0f;
                    lastScanTargetIndex = targetSliceIndex;

                    if (numVoices > 1 && !voices.empty()) {
                        voices[0].sliceIndex = targetSliceIndex;
                        voices[0].playbackPosition = slices[targetSliceIndex].startSample;
                        voices[0].playbackPhase = 0.0f;
                    }
                }
            } else {
                lastScanTargetIndex = -1;
            }
        }

        // Playback (loop current slice)
        float loopL = 0.0f;
        float loopR = 0.0f;

        if (recordedLength > 0) {
            float playbackSpeed = params[SPEED_PARAM].getValue();
            bool isReverse = playbackSpeed < 0.0f;

            if (numVoices == 1 || voices.empty()) {
                // Single voice mode
                playbackPhase += playbackSpeed;
                int positionDelta = (int)playbackPhase;
                playbackPhase -= (float)positionDelta;
                playbackPosition += positionDelta;

                // Loop current slice
                if (!slices.empty() && currentSliceIndex < (int)slices.size() && slices[currentSliceIndex].active) {
                    int sliceStart = slices[currentSliceIndex].startSample;
                    int sliceEnd = slices[currentSliceIndex].endSample;

                    if (isReverse) {
                        if (playbackPosition < sliceStart) {
                            playbackPosition = sliceEnd;
                        }
                    } else {
                        if (playbackPosition > sliceEnd) {
                            playbackPosition = sliceStart;
                        }
                    }
                } else {
                    // No slices: loop entire buffer
                    if (isReverse) {
                        if (playbackPosition < 0) {
                            playbackPosition = recordedLength - 1;
                        }
                    } else {
                        if (playbackPosition >= recordedLength) {
                            playbackPosition = 0;
                        }
                    }
                }

                // Read with interpolation (mono output to both channels)
                if (recordedLength > 0) {
                    playbackPosition = clamp(playbackPosition, 0, recordedLength - 1);
                    int pos0 = playbackPosition;
                    int pos1 = (recordedLength > 1) ? ((pos0 + 1) % recordedLength) : pos0;

                    // Ensure positions are within bounds
                    pos0 = clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
                    pos1 = clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

                    float frac = clamp(std::abs(playbackPhase), 0.0f, 1.0f);

                    float sample = loopBuffer[pos0] * (1.0f - frac) + loopBuffer[pos1] * frac;
                    loopL = sample;
                    loopR = sample;
                }
            } else {
                // Multiple voices mode
                for (int i = 0; i < numVoices; i++) {
                    float voiceSpeed = playbackSpeed * voices[i].speedMultiplier;
                    // Clamp total speed to safe range
                    voiceSpeed = clamp(voiceSpeed, -16.0f, 16.0f);
                    voices[i].playbackPhase += voiceSpeed;

                    int positionDelta = (int)voices[i].playbackPhase;
                    voices[i].playbackPhase -= (float)positionDelta;
                    voices[i].playbackPosition += positionDelta;

                    // Loop current slice for each voice
                    if (!slices.empty() && voices[i].sliceIndex < (int)slices.size() && slices[voices[i].sliceIndex].active) {
                        int sliceStart = slices[voices[i].sliceIndex].startSample;
                        int sliceEnd = slices[voices[i].sliceIndex].endSample;

                        bool voiceReverse = voiceSpeed < 0.0f;
                        if (voiceReverse) {
                            if (voices[i].playbackPosition < sliceStart) {
                                voices[i].playbackPosition = sliceEnd;
                            }
                        } else {
                            if (voices[i].playbackPosition > sliceEnd) {
                                voices[i].playbackPosition = sliceStart;
                            }
                        }
                    } else {
                        // No valid slice: loop entire buffer
                        bool voiceReverse = voiceSpeed < 0.0f;
                        if (voiceReverse) {
                            if (voices[i].playbackPosition < 0) {
                                voices[i].playbackPosition = recordedLength - 1;
                            }
                        } else {
                            if (voices[i].playbackPosition >= recordedLength) {
                                voices[i].playbackPosition = 0;
                            }
                        }
                    }

                    // Read with interpolation and distribute to L/R alternately
                    if (recordedLength > 0) {
                        voices[i].playbackPosition = clamp(voices[i].playbackPosition, 0, recordedLength - 1);
                        int pos0 = voices[i].playbackPosition;
                        int pos1 = (recordedLength > 1) ? ((pos0 + 1) % recordedLength) : pos0;

                        // Ensure positions are within bounds
                        pos0 = clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
                        pos1 = clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

                        float frac = clamp(std::abs(voices[i].playbackPhase), 0.0f, 1.0f);

                        float sample = loopBuffer[pos0] * (1.0f - frac) + loopBuffer[pos1] * frac;

                        // Check for invalid sample
                        if (std::isfinite(sample)) {
                            // Alternate voices between L and R
                            if (i % 2 == 0) {
                                loopL += sample;
                            } else {
                                loopR += sample;
                            }
                        }
                    }
                }

                // Normalize by sqrt of voices per channel
                int leftVoices = (numVoices + 1) / 2;  // Round up for left
                int rightVoices = numVoices / 2;       // Round down for right
                if (leftVoices > 0) loopL /= std::sqrt((float)leftVoices);
                if (rightVoices > 0) loopR /= std::sqrt((float)rightVoices);

                // Update layer position to voice 0
                if (!voices.empty()) {
                    playbackPosition = voices[0].playbackPosition;
                    playbackPhase = voices[0].playbackPhase;
                    currentSliceIndex = voices[0].sliceIndex;
                }
            }
        }

        // MIX control (input is mono, distributed to both L/R)
        float mix = params[MIX_PARAM].getValue();
        float mixedL = input * (1.0f - mix) + loopL * mix;
        float mixedR = input * (1.0f - mix) + loopR * mix;

        // FEEDBACK (send/return from EQ->Delay->Reverb output)
        float feedback = params[FDBK_PARAM].getValue();
        float fbL = std::tanh(lastOutputL * 0.3f) / 0.3f;
        float fbR = std::tanh(lastOutputR * 0.3f) / 0.3f;

        mixedL += fbL * feedback;
        mixedR += fbR * feedback;

        // 3-Band EQ
        float eqLowGain = params[EQ_LOW_PARAM].getValue();
        float eqMidGain = params[EQ_MID_PARAM].getValue();
        float eqHighGain = params[EQ_HIGH_PARAM].getValue();

        eqLowL.setParameters(dsp::TBiquadFilter<>::LOWSHELF, 80.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqLowGain / 20.0f));
        eqLowR.setParameters(dsp::TBiquadFilter<>::LOWSHELF, 80.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqLowGain / 20.0f));
        eqMidL.setParameters(dsp::TBiquadFilter<>::PEAK, 2500.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqMidGain / 20.0f));
        eqMidR.setParameters(dsp::TBiquadFilter<>::PEAK, 2500.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqMidGain / 20.0f));
        eqHighL.setParameters(dsp::TBiquadFilter<>::HIGHSHELF, 12000.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqHighGain / 20.0f));
        eqHighR.setParameters(dsp::TBiquadFilter<>::HIGHSHELF, 12000.0f / args.sampleRate, 0.707f, std::pow(10.0f, eqHighGain / 20.0f));

        float eqL = eqLowL.process(mixedL);
        eqL = eqMidL.process(eqL);
        eqL = eqHighL.process(eqL);

        float eqR = eqLowR.process(mixedR);
        eqR = eqMidR.process(eqR);
        eqR = eqHighR.process(eqR);

        // Delay processing
        float delayTimeL = params[DELAY_TIME_L_PARAM].getValue();
        float delayTimeR = params[DELAY_TIME_R_PARAM].getValue();
        float delayFeedback = params[DELAY_FEEDBACK_PARAM].getValue();
        float delayWet = params[DELAY_WET_PARAM].getValue();

        float delayedL = delayL.process(eqL, delayTimeL, delayFeedback, args.sampleRate);
        float delayedR = delayR.process(eqR, delayTimeR, delayFeedback, args.sampleRate);

        float delayMixL = eqL * (1.0f - delayWet) + delayedL * delayWet;
        float delayMixR = eqR * (1.0f - delayWet) + delayedR * delayWet;

        // Reverb processing
        float roomSize = 1.0f; // Fixed at maximum
        float damping = 1.0f; // Fixed at maximum
        float decay = params[REVERB_DECAY_PARAM].getValue();
        float reverbWet = params[REVERB_WET_PARAM].getValue();

        float reverbedL = reverbL.process(delayMixL, roomSize, damping, decay, args.sampleRate);
        float reverbedR = reverbR.process(delayMixR, roomSize, damping, decay, args.sampleRate);

        float outputL = delayMixL * (1.0f - reverbWet) + reverbedL * reverbWet;
        float outputR = delayMixR * (1.0f - reverbWet) + reverbedR * reverbWet;

        // Store for feedback
        lastOutputL = outputL;
        lastOutputR = outputR;

        // Output
        outputs[LEFT_OUTPUT].setVoltage(clamp(outputL, -10.0f, 10.0f));
        outputs[RIGHT_OUTPUT].setVoltage(clamp(outputR, -10.0f, 10.0f));
    }
};

struct Alien4Widget : ModuleWidget {
    PanelThemeHelper panelThemeHelper;

    Alien4Widget(Alien4* module) {
        setModule(module);
        panelThemeHelper.init(this, "12HP");

        box.size = Vec(12 * RACK_GRID_WIDTH, RACK_GRID_HEIGHT);

        addChild(new EnhancedTextLabel(Vec(0, 1), Vec(box.size.x, 20), "Alien4", 12.f, nvgRGB(255, 200, 0), true));
        addChild(new EnhancedTextLabel(Vec(0, 13), Vec(box.size.x, 20), "MADZINE", 10.f, nvgRGB(255, 200, 0), false));

        // LOOP section
        addChild(new EnhancedTextLabel(Vec(0, 30), Vec(box.size.x, 15), "LOOP", 10.f, nvgRGB(255, 255, 255), true));

        float loopY = 46;
        float x = 5;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "REC", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createLightParamCentered<VCVLightLatch<MediumSimpleLight<RedLight>>>(Vec(x + 12, loopY + 18), module, Alien4::REC_PARAM, Alien4::REC_LIGHT));
        x += 30;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "SCAN", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 12, loopY + 18), module, Alien4::SCAN_PARAM));
        x += 30;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "MIN", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 12, loopY + 18), module, Alien4::MIN_SLICE_TIME_PARAM));
        x += 30;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "MIX", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 12, loopY + 18), module, Alien4::MIX_PARAM));
        x += 30;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "FDBK", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 12, loopY + 18), module, Alien4::FDBK_PARAM));
        x += 30;

        addChild(new EnhancedTextLabel(Vec(x, loopY), Vec(25, 10), "POLY", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 12, loopY + 18), module, Alien4::POLY_PARAM));

        // EQ section
        addChild(new EnhancedTextLabel(Vec(0, 88), Vec(box.size.x, 15), "3-BAND EQ", 10.f, nvgRGB(255, 255, 255), true));

        float eqY = 104;
        x = 20;

        addChild(new EnhancedTextLabel(Vec(x, eqY), Vec(30, 10), "LOW", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, eqY + 18), module, Alien4::EQ_LOW_PARAM));
        x += 50;

        addChild(new EnhancedTextLabel(Vec(x, eqY), Vec(30, 10), "MID", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, eqY + 18), module, Alien4::EQ_MID_PARAM));
        x += 50;

        addChild(new EnhancedTextLabel(Vec(x, eqY), Vec(30, 10), "HIGH", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, eqY + 18), module, Alien4::EQ_HIGH_PARAM));

        // SPEED section
        float speedY = 150;
        addChild(new EnhancedTextLabel(Vec(0, speedY), Vec(box.size.x, 15), "SPEED", 10.f, nvgRGB(255, 255, 255), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(box.size.x / 2, speedY + 20), module, Alien4::SPEED_PARAM));

        // DELAY section
        addChild(new EnhancedTextLabel(Vec(0, 196), Vec(box.size.x, 15), "DELAY", 10.f, nvgRGB(255, 255, 255), true));

        float delayY = 212;
        x = 10;

        addChild(new EnhancedTextLabel(Vec(x, delayY), Vec(30, 10), "TIME L", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, delayY + 18), module, Alien4::DELAY_TIME_L_PARAM));
        x += 45;

        addChild(new EnhancedTextLabel(Vec(x, delayY), Vec(30, 10), "TIME R", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, delayY + 18), module, Alien4::DELAY_TIME_R_PARAM));
        x += 45;

        addChild(new EnhancedTextLabel(Vec(x, delayY), Vec(30, 10), "FDBK", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, delayY + 18), module, Alien4::DELAY_FEEDBACK_PARAM));
        x += 45;

        addChild(new EnhancedTextLabel(Vec(x, delayY), Vec(30, 10), "WET", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, delayY + 18), module, Alien4::DELAY_WET_PARAM));

        // REVERB section
        addChild(new EnhancedTextLabel(Vec(0, 258), Vec(box.size.x, 15), "REVERB", 10.f, nvgRGB(255, 255, 255), true));

        float reverbY = 274;
        x = 55;

        addChild(new EnhancedTextLabel(Vec(x, reverbY), Vec(30, 10), "DECAY", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, reverbY + 18), module, Alien4::REVERB_DECAY_PARAM));
        x += 45;

        addChild(new EnhancedTextLabel(Vec(x, reverbY), Vec(30, 10), "WET", 7.f, nvgRGB(200, 200, 200), true));
        addParam(createParamCentered<StandardBlackKnob26>(Vec(x + 15, reverbY + 18), module, Alien4::REVERB_WET_PARAM));

        // I/O section
        addInput(createInputCentered<PJ301MPort>(Vec(45, 350), module, Alien4::LEFT_INPUT));

        addOutput(createOutputCentered<PJ301MPort>(Vec(120, 350), module, Alien4::LEFT_OUTPUT));
        addOutput(createOutputCentered<PJ301MPort>(Vec(150, 350), module, Alien4::RIGHT_OUTPUT));
    }

    void step() override {
        Alien4* module = dynamic_cast<Alien4*>(this->module);
        if (module) {
            panelThemeHelper.step(module);
        }
        ModuleWidget::step();
    }

    void appendContextMenu(ui::Menu* menu) override {
        Alien4* module = dynamic_cast<Alien4*>(this->module);
        if (!module) return;

        addPanelThemeMenu(menu, module);
    }
};

Model* modelAlien4 = createModel<Alien4, Alien4Widget>("Alien4");
