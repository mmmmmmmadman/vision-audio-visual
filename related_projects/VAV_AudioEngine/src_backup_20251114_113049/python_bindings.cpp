#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "alien4_engine.hpp"

namespace py = pybind11;

/**
 * Python bindings for Alien4AudioEngine
 *
 * Usage in Python:
 *   import alien4
 *   engine = alien4.AudioEngine(48000.0)
 *   engine.set_mix(0.5)
 *   output_l, output_r = engine.process(input_l, input_r)
 */

class Alien4Wrapper {
private:
    Alien4AudioEngine engine;

public:
    Alien4Wrapper(float sampleRate = 48000.0f) : engine(sampleRate) {}

    // Documenta parameters
    void set_recording(bool rec) { engine.setRecording(rec); }
    void set_looping(bool loop) { engine.setLooping(loop); }
    void set_min_slice_time(float time) { engine.setMinSliceTime(time); }
    void set_scan(int index) { engine.setScan(index); }
    void set_feedback(float amount) { engine.setFeedback(amount); }
    void set_mix(float mix) { engine.setMix(mix); }
    void set_speed(float speed) { engine.setSpeed(speed); }

    // EQ parameters
    void set_eq_low(float gain) { engine.setEQLow(gain); }
    void set_eq_mid(float gain) { engine.setEQMid(gain); }
    void set_eq_high(float gain) { engine.setEQHigh(gain); }

    // Ellen Ripley parameters
    void set_delay_time(float timeL, float timeR) { engine.setDelayTime(timeL, timeR); }
    void set_delay_feedback(float fb) { engine.setDelayFeedback(fb); }
    void set_delay_wet(float wet) { engine.setDelayWet(wet); }
    void set_reverb_room(float room) { engine.setReverbRoom(room); }
    void set_reverb_damping(float damp) { engine.setReverbDamping(damp); }
    void set_reverb_decay(float decay) { engine.setReverbDecay(decay); }
    void set_reverb_wet(float wet) { engine.setReverbWet(wet); }

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
    m.doc() = "Alien4 Audio Engine - Documenta + Ellen Ripley";

    py::class_<Alien4Wrapper>(m, "AudioEngine")
        .def(py::init<float>(), py::arg("sample_rate") = 48000.0f,
             "Create Alien4 audio engine\n\n"
             "Args:\n"
             "    sample_rate: Sample rate in Hz (default 48000)")

        // Documenta parameters
        .def("set_recording", &Alien4Wrapper::set_recording, py::arg("enabled"))
        .def("set_looping", &Alien4Wrapper::set_looping, py::arg("enabled"))
        .def("set_min_slice_time", &Alien4Wrapper::set_min_slice_time, py::arg("time"))
        .def("set_scan", &Alien4Wrapper::set_scan, py::arg("index"))
        .def("set_feedback", &Alien4Wrapper::set_feedback, py::arg("amount"))
        .def("set_mix", &Alien4Wrapper::set_mix, py::arg("mix"),
             "Set input/loop mix (0=input, 1=loop)")
        .def("set_speed", &Alien4Wrapper::set_speed, py::arg("speed"),
             "Set playback speed (0.25 - 4.0)")

        // EQ parameters
        .def("set_eq_low", &Alien4Wrapper::set_eq_low, py::arg("gain"),
             "Set low shelf gain in dB (-20 to +20)")
        .def("set_eq_mid", &Alien4Wrapper::set_eq_mid, py::arg("gain"))
        .def("set_eq_high", &Alien4Wrapper::set_eq_high, py::arg("gain"))

        // Ellen Ripley parameters
        .def("set_delay_time", &Alien4Wrapper::set_delay_time,
             py::arg("time_l"), py::arg("time_r"),
             "Set delay times in seconds")
        .def("set_delay_feedback", &Alien4Wrapper::set_delay_feedback, py::arg("feedback"))
        .def("set_delay_wet", &Alien4Wrapper::set_delay_wet, py::arg("wet"),
             "Set delay wet/dry mix (0=dry, 1=wet)")
        .def("set_reverb_room", &Alien4Wrapper::set_reverb_room, py::arg("room"))
        .def("set_reverb_damping", &Alien4Wrapper::set_reverb_damping, py::arg("damping"))
        .def("set_reverb_decay", &Alien4Wrapper::set_reverb_decay, py::arg("decay"))
        .def("set_reverb_wet", &Alien4Wrapper::set_reverb_wet, py::arg("wet"),
             "Set reverb wet/dry mix (0=dry, 1=wet)")

        // Processing
        .def("process", &Alien4Wrapper::process,
             py::arg("input_l"), py::arg("input_r"),
             "Process stereo audio\n\n"
             "Args:\n"
             "    input_l: Left channel input (NumPy array)\n"
             "    input_r: Right channel input (NumPy array)\n\n"
             "Returns:\n"
             "    (output_l, output_r): Tuple of output arrays")

        .def("clear", &Alien4Wrapper::clear,
             "Clear all internal buffers");
}
