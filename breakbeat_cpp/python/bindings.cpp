#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "breakbeat_engine.h"

namespace py = pybind11;
using namespace breakbeat;

PYBIND11_MODULE(breakbeat, m) {
    m.doc() = "Breakbeat Engine - High Performance C++ Rhythm Generator";

    // Enums
    py::enum_<PatternType>(m, "PatternType")
        .value("AMEN", PatternType::AMEN)
        .value("JUNGLE", PatternType::JUNGLE)
        .value("BOOM_BAP", PatternType::BOOM_BAP)
        .value("TECHNO", PatternType::TECHNO);

    py::enum_<LatinPatternType>(m, "LatinPatternType")
        .value("SAMBA", LatinPatternType::SAMBA)
        .value("BOSSA", LatinPatternType::BOSSA)
        .value("SALSA", LatinPatternType::SALSA);

    // VoiceSegment
    py::class_<VoiceSegment>(m, "VoiceSegment")
        .def(py::init<int, const std::vector<float>&>(),
             py::arg("step"), py::arg("audio"))
        .def_readwrite("step", &VoiceSegment::step)
        .def_readwrite("audio", &VoiceSegment::audio);

    // BreakbeatEngine
    py::class_<BreakbeatEngine>(m, "BreakbeatEngine")
        .def(py::init<const std::string&, int>(),
             py::arg("sample_dir"), py::arg("sample_rate") = 44100,
             "Initialize Breakbeat Engine")

        // Parameter setters
        .def("set_bpm", &BreakbeatEngine::set_bpm,
             py::arg("bpm"),
             "Set BPM (beats per minute)")

        .def("set_pattern_type", &BreakbeatEngine::set_pattern_type,
             py::arg("pattern_type"),
             "Set pattern type (AMEN, JUNGLE, BOOM_BAP, TECHNO)")

        .def("set_pattern_variation", &BreakbeatEngine::set_pattern_variation,
             py::arg("variation"),
             "Set pattern variation (0-9)")

        .def("set_latin_pattern_type", &BreakbeatEngine::set_latin_pattern_type,
             py::arg("latin_pattern_type"),
             "Set latin pattern type (SAMBA, BOSSA, SALSA)")

        .def("set_latin_enabled", &BreakbeatEngine::set_latin_enabled,
             py::arg("enabled"),
             "Enable/disable latin rhythm layer")

        .def("set_latin_fill_amount", &BreakbeatEngine::set_latin_fill_amount,
             py::arg("amount"),
             "Set latin fill amount (0.0-1.0)")

        .def("set_rest_probability", &BreakbeatEngine::set_rest_probability,
             py::arg("probability"),
             "Set rest probability (0.0-1.0)")

        .def("set_swing_amount", &BreakbeatEngine::set_swing_amount,
             py::arg("amount"),
             "Set swing amount (0.0-0.33)")

        .def("set_ghost_notes", &BreakbeatEngine::set_ghost_notes,
             py::arg("amount"),
             "Set ghost notes probability (0.0-1.0)")

        .def("set_voice_enabled", &BreakbeatEngine::set_voice_enabled,
             py::arg("enabled"),
             "Enable/disable voice layer")

        // Voice segments
        .def("set_voice_segments", &BreakbeatEngine::set_voice_segments,
             py::arg("segments"),
             "Set voice segments")

        .def("clear_voice_segments", &BreakbeatEngine::clear_voice_segments,
             "Clear all voice segments")

        // Compressor parameters (LA-2A style)
        .def("set_comp_enabled", &BreakbeatEngine::set_comp_enabled,
             py::arg("enabled"),
             "Enable/disable LA-2A compressor")

        .def("set_comp_peak_reduction", &BreakbeatEngine::set_comp_peak_reduction,
             py::arg("amount"),
             "Set peak reduction amount (0.0 to 1.0)")

        .def("set_comp_gain", &BreakbeatEngine::set_comp_gain,
             py::arg("db"),
             "Set makeup gain (-20 to 20 dB)")

        .def("set_comp_mix", &BreakbeatEngine::set_comp_mix,
             py::arg("mix"),
             "Set compressor dry/wet mix (0.0-1.0)")

        // Audio generation
        .def("get_audio_chunk",
             [](BreakbeatEngine& engine, int num_frames) -> py::array_t<float> {
                 auto result = py::array_t<float>(num_frames);
                 auto buf = result.request();
                 float* ptr = static_cast<float*>(buf.ptr);

                 engine.get_audio_chunk(ptr, num_frames);

                 return result;
             },
             py::arg("num_frames"),
             "Get audio chunk (returns numpy array)")

        // Getters
        .def("get_sample_rate", &BreakbeatEngine::get_sample_rate,
             "Get sample rate")

        .def("get_bar_count", &BreakbeatEngine::get_bar_count,
             "Get bar count");
}
