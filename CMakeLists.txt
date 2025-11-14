cmake_minimum_required(VERSION 3.15)
project(alien4_extension)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Python
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

# Add pybind11
# Try to find pybind11 via pip install location
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE PYBIND11_SEARCH_RESULT
)

if(PYBIND11_SEARCH_RESULT EQUAL 0)
    list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
    find_package(pybind11 CONFIG REQUIRED)
else()
    # Fallback: try to find it via standard cmake
    find_package(pybind11 CONFIG REQUIRED)
endif()

# Create the Python module
pybind11_add_module(alien4 alien4_extension.cpp)

# Set compiler flags for optimization
target_compile_options(alien4 PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/O2 /fp:fast>
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-O3 -ffast-math -march=native>
)

# Set the output directory
set_target_properties(alien4 PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/vav/audio"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_SOURCE_DIR}/vav/audio"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_SOURCE_DIR}/vav/audio"
)

# Installation rules
install(TARGETS alien4
    LIBRARY DESTINATION "${CMAKE_SOURCE_DIR}/vav/audio"
)
