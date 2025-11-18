cmake_minimum_required(VERSION 3.15)
project(Alien4AudioEngine)

# C++17 standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization flags
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native")
endif()

# Include directories
include_directories(${PROJECT_SOURCE_DIR}/src)

# ===== C++ Test Executable =====
add_executable(test_alien4
    test/test_alien4.cpp
)

# macOS specific settings
if(APPLE)
    target_compile_options(test_alien4 PRIVATE -Wall -Wextra)
endif()

# ===== Python Module =====
# Find Python
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# Get pybind11 include directory
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import pybind11; print(pybind11.get_include())"
    OUTPUT_VARIABLE PYBIND11_INCLUDE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Get Python include directory
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -c "import sysconfig; print(sysconfig.get_path('include'))"
    OUTPUT_VARIABLE PYTHON_INCLUDE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Python module
add_library(alien4 MODULE src/python_bindings.cpp)
target_include_directories(alien4 PRIVATE ${PYBIND11_INCLUDE_DIR} ${PYTHON_INCLUDE_DIR})
set_target_properties(alien4 PROPERTIES PREFIX "" SUFFIX ".so")

# macOS: Use undefined dynamic lookup for Python symbols
if(APPLE)
    target_link_options(alien4 PRIVATE "-undefined" "dynamic_lookup")
endif()

# macOS specific settings for Python module
if(APPLE)
    target_compile_options(alien4 PRIVATE -Wall -Wextra)
endif()

# Print build info
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID}")
message(STATUS "Python: ${Python3_EXECUTABLE}")
message(STATUS "Python version: ${Python3_VERSION}")
message(STATUS "Pybind11: Found")
