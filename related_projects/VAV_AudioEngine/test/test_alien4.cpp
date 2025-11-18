#include "../src/alien4_engine.hpp"
#include <iostream>
#include <cmath>
#include <vector>

/**
 * Simple test for Alien4AudioEngine
 *
 * Generates a test tone, processes it through the engine, and prints output
 */

void generateTestTone(float* buffer, int numSamples, float frequency, float sampleRate) {
    for (int i = 0; i < numSamples; i++) {
        buffer[i] = 0.5f * std::sin(2.0f * M_PI * frequency * i / sampleRate);
    }
}

int main() {
    std::cout << "=== Alien4 Audio Engine Test ===" << std::endl;

    const float SAMPLE_RATE = 48000.0f;
    const int BUFFER_SIZE = 512;
    const int NUM_BUFFERS = 10;

    // Create engine
    Alien4AudioEngine engine(SAMPLE_RATE);

    std::cout << "Engine initialized at " << SAMPLE_RATE << " Hz" << std::endl;

    // Configure parameters
    engine.setRecording(true);
    engine.setLooping(true);
    engine.setMix(0.5f);
    engine.setFeedback(0.3f);
    engine.setSpeed(1.0f);

    // EQ
    engine.setEQLow(3.0f);    // +3dB low
    engine.setEQMid(0.0f);    // 0dB mid
    engine.setEQHigh(-3.0f);  // -3dB high

    // Ellen Ripley
    engine.setDelayTime(0.25f, 0.3f);
    engine.setDelayFeedback(0.4f);
    engine.setDelayWet(0.3f);
    engine.setReverbRoom(0.7f);
    engine.setReverbDamping(0.5f);
    engine.setReverbDecay(0.6f);
    engine.setReverbWet(0.3f);

    std::cout << "Parameters configured" << std::endl;

    // Allocate buffers
    std::vector<float> inputL(BUFFER_SIZE);
    std::vector<float> inputR(BUFFER_SIZE);
    std::vector<float> outputL(BUFFER_SIZE);
    std::vector<float> outputR(BUFFER_SIZE);

    // Generate test tone (440 Hz)
    generateTestTone(inputL.data(), BUFFER_SIZE, 440.0f, SAMPLE_RATE);
    generateTestTone(inputR.data(), BUFFER_SIZE, 440.0f, SAMPLE_RATE);

    std::cout << "Processing " << NUM_BUFFERS << " buffers..." << std::endl;

    // Process multiple buffers
    for (int buf = 0; buf < NUM_BUFFERS; buf++) {
        engine.process(inputL.data(), inputR.data(),
                      outputL.data(), outputR.data(),
                      BUFFER_SIZE);

        // Print first sample of each buffer
        std::cout << "Buffer " << buf << ": "
                  << "Input L=" << inputL[0] << " "
                  << "Output L=" << outputL[0] << " R=" << outputR[0]
                  << std::endl;
    }

    std::cout << "Test completed successfully!" << std::endl;

    // Test clear
    engine.clear();
    std::cout << "Engine cleared" << std::endl;

    return 0;
}
