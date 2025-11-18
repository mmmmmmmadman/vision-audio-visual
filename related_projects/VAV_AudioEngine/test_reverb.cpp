#include "src/ripley/reverb_processor.hpp"
#include <iostream>
#include <vector>
#include <cmath>

int main() {
    std::cout << "=== Reverb Processor Test ===" << std::endl;

    const float SAMPLE_RATE = 48000.0f;
    const int BUFFER_SIZE = 4800;  // 0.1 second

    // Create reverb
    ReverbProcessor reverb(SAMPLE_RATE);
    reverb.setParameters(0.9f, 0.5f, 0.8f);  // room, damping, decay

    std::cout << "Reverb configured: room=0.9, damping=0.5, decay=0.8" << std::endl;

    // Create impulse
    std::vector<float> inputL(BUFFER_SIZE, 0.0f);
    std::vector<float> inputR(BUFFER_SIZE, 0.0f);
    inputL[10] = 1.0f;
    inputR[10] = 1.0f;

    std::vector<float> outputL(BUFFER_SIZE);
    std::vector<float> outputR(BUFFER_SIZE);

    // Process
    reverb.process(inputL.data(), inputR.data(), outputL.data(), outputR.data(), BUFFER_SIZE);

    // Check output
    float maxOut = 0.0f;
    int maxIdx = 0;
    float energy = 0.0f;

    for (int i = 0; i < BUFFER_SIZE; i++) {
        float absVal = std::abs(outputL[i]);
        if (absVal > maxOut) {
            maxOut = absVal;
            maxIdx = i;
        }
        energy += outputL[i] * outputL[i];
    }

    std::cout << "Input peak: 1.0 at index 10" << std::endl;
    std::cout << "Output peak: " << maxOut << " at index " << maxIdx << std::endl;
    std::cout << "Output energy: " << energy << std::endl;

    // Check tail
    float tailEnergy = 0.0f;
    for (int i = 100; i < 1000; i++) {
        tailEnergy += outputL[i] * outputL[i];
    }
    std::cout << "Tail energy (100-1000): " << tailEnergy << std::endl;

    if (tailEnergy > 0.001f) {
        std::cout << "✓ Reverb is working!" << std::endl;
    } else {
        std::cout << "✗ Reverb is NOT working!" << std::endl;
    }

    return 0;
}
