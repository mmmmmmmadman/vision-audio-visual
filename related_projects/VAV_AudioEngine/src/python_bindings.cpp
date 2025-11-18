#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "alien4_engine.hpp"

namespace py = pybind11;

/**
 * Python bindings for Alien4AudioEngine
 *
 * Complete VCV Rack Alien4 port with dynamic slice detection and polyphonic playback
 */

class Alien4Wrapper {
private:
    Alien4AudioEngine engine;

public:
    Alien4Wrapper(float sampleRate = 48000.0f) : engine(sampleRate) {}

    // === Documenta parameters ===
    void set_recording(bool rec) { engine.setRecording(rec); }
    void set_looping(bool loop) { engine.setLooping(loop); }

    void set_min_slice_time(float time) {
        // time is 0.0-1.0 knob value, will be converted internally to 0.001-5.0 seconds
        engine.setMinSliceTime(time);
    }

    void set_scan(float scan) {
        // scan is 0.0-1.0, scans through all detected slices
        engine.setScan(scan);
    }

    void set_feedback(float amount) { engine.setFeedback(amount); }
    void set_mix(float mix) { engine.setMix(mix); }

    void set_speed(float speed) {
        // speed is -8.0 to +8.0 (negative = reverse)
        engine.setSpeed(speed);
    }

    void set_poly(int voices) {
        // voices is 1-8
        engine.setPolyVoices(voices);
    }

    // === EQ parameters ===
    void set_eq_low(float gain) { engine.setEQLow(gain); }
    void set_eq_mid(float gain) { engine.setEQMid(gain); }
    void set_eq_high(float gain) { engine.setEQHigh(gain); }

    // === Effects parameters ===
    void set_delay_time(float timeL, float timeR) { engine.setDelayTime(timeL, timeR); }
    void set_delay_feedback(float fb) { engine.setDelayFeedback(fb); }
    void set_delay_wet(float wet) { engine.setDelayWet(wet); }
    void set_reverb_room(float room) { engine.setReverbRoom(room); }
    void set_reverb_damping(float damp) { engine.setReverbDamping(damp); }
    void set_reverb_decay(float decay) { engine.setReverbDecay(decay); }
    void set_reverb_wet(float wet) { engine.setReverbWet(wet); }

    // === Query functions ===
    int get_num_slices() const { return engine.getNumSlices(); }
    int get_current_slice() const { return engine.getCurrentSlice(); }
    int get_num_voices() const { return engine.getNumVoices(); }
    bool get_is_recording() const { return engine.getIsRecording(); }

    // Process audio with NumPy arrays
    py::tuple process(py::array_t<float> input_l, py::array_t<float> input_r) {
        // Get buffer info
        py::buffer_info buf_l = input_l.request();
        py::buffer_info buf_r = input_r.request();

        if (buf_l.ndim != 1 || buf_r.ndim != 1) {
            throw std::runtime_error("Input arrays must be 1-dimensional");
        }

        if (buf_l.size != buf_r.size) {
            throw std::runtime_error("Input arrays must have the same size");
        }

        int num_samples = buf_l.size;

        // Get input pointers
        float* in_l = static_cast<float*>(buf_l.ptr);
        float* in_r = static_cast<float*>(buf_r.ptr);

        // Allocate output arrays
        py::array_t<float> output_l(num_samples);
        py::array_t<float> output_r(num_samples);

        py::buffer_info out_buf_l = output_l.request();
        py::buffer_info out_buf_r = output_r.request();

        float* out_l = static_cast<float*>(out_buf_l.ptr);
        float* out_r = static_cast<float*>(out_buf_r.ptr);

        // Process
        engine.process(in_l, in_r, out_l, out_r, num_samples);

        return py::make_tuple(output_l, output_r);
    }

    void clear() { engine.clear(); }
};

PYBIND11_MODULE(alien4, m) {
    m.doc() = "Alien4 Audio Engine - Complete VCV Rack Alien4 port with dynamic slicing and polyphonic playback";

    py::class_<Alien4Wrapper>(m, "AudioEngine")
        .def(py::init<float>(), py::arg("sample_rate") = 48000.0f,
             "Create Alien4 audio engine\n\n"
             "Args:\n"
             "    sample_rate: Sample rate in Hz (default 48000)")

        // === Documenta parameters ===
        .def("set_recording", &Alien4Wrapper::set_recording, py::arg("enabled"),
             "Start/stop recording")

        .def("set_looping", &Alien4Wrapper::set_looping, py::arg("enabled"),
             "Enable/disable looping")

        .def("set_min_slice_time", &Alien4Wrapper::set_min_slice_time, py::arg("time"),
             "Set minimum slice time (0.0-1.0 knob value)\n"
             "0.0-0.5: exponential 0.001-1.0 seconds\n"
             "0.5-1.0: linear 1.0-5.0 seconds")

        .def("set_scan", &Alien4Wrapper::set_scan, py::arg("scan"),
             "Scan through slices (0.0-1.0)\n"
             "0.0 = first slice, 1.0 = last slice")

        .def("set_feedback", &Alien4Wrapper::set_feedback, py::arg("amount"),
             "Set feedback amount (0.0-0.95)")

        .def("set_mix", &Alien4Wrapper::set_mix, py::arg("mix"),
             "Set input/loop mix (0=input, 1=loop)")

        .def("set_speed", &Alien4Wrapper::set_speed, py::arg("speed"),
             "Set playback speed (-8.0 to +8.0)\n"
             "Negative values = reverse playback")

        .def("set_poly", &Alien4Wrapper::set_poly, py::arg("voices"),
             "Set number of polyphonic voices (1-8)")

        // === EQ parameters ===
        .def("set_eq_low", &Alien4Wrapper::set_eq_low, py::arg("gain"),
             "Set low shelf gain in dB (-20 to +20)")

        .def("set_eq_mid", &Alien4Wrapper::set_eq_mid, py::arg("gain"),
             "Set mid peak gain in dB (-20 to +20)")

        .def("set_eq_high", &Alien4Wrapper::set_eq_high, py::arg("gain"),
             "Set high shelf gain in dB (-20 to +20)")

        // === Effects parameters ===
        .def("set_delay_time", &Alien4Wrapper::set_delay_time,
             py::arg("time_l"), py::arg("time_r"),
             "Set delay times in seconds (0.001-2.0)")

        .def("set_delay_feedback", &Alien4Wrapper::set_delay_feedback,
             py::arg("feedback"),
             "Set delay feedback (0.0-0.95)")

        .def("set_delay_wet", &Alien4Wrapper::set_delay_wet, py::arg("wet"),
             "Set delay wet/dry mix (0=dry, 1=wet)")

        .def("set_reverb_room", &Alien4Wrapper::set_reverb_room, py::arg("room"),
             "Set reverb room size (0.0-1.0)")

        .def("set_reverb_damping", &Alien4Wrapper::set_reverb_damping,
             py::arg("damping"),
             "Set reverb damping (0.0-1.0)")

        .def("set_reverb_decay", &Alien4Wrapper::set_reverb_decay,
             py::arg("decay"),
             "Set reverb decay time (0.0-1.0)")

        .def("set_reverb_wet", &Alien4Wrapper::set_reverb_wet, py::arg("wet"),
             "Set reverb wet/dry mix (0=dry, 1=wet)")

        // === Query functions ===
        .def("get_num_slices", &Alien4Wrapper::get_num_slices,
             "Get number of detected slices")

        .def("get_current_slice", &Alien4Wrapper::get_current_slice,
             "Get current slice index")

        .def("get_num_voices", &Alien4Wrapper::get_num_voices,
             "Get number of polyphonic voices")

        .def("get_is_recording", &Alien4Wrapper::get_is_recording,
             "Check if currently recording")

        // === Processing ===
        .def("process", &Alien4Wrapper::process,
             py::arg("input_l"), py::arg("input_r"),
             "Process stereo audio\n\n"
             "Args:\n"
             "    input_l: Left channel input (NumPy array)\n"
             "    input_r: Right channel input (NumPy array)\n\n"
             "Returns:\n"
             "    (output_l, output_r): Tuple of output arrays")

        .def("clear", &Alien4Wrapper::clear,
             "Clear all internal buffers and reset state");
}
