cmake_minimum_required(VERSION 3.15)
project(breakbeat CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Python
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find pybind11
execute_process(
    COMMAND ${Python_EXECUTABLE} -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(pybind11 REQUIRED)

# Find libsndfile
find_package(PkgConfig REQUIRED)
pkg_check_modules(SNDFILE REQUIRED sndfile)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SNDFILE_INCLUDE_DIRS}
)

# Source files
set(SOURCES
    src/breakbeat_engine.cpp
    src/breakbeat_pattern.cpp
    src/compressor.cpp
)

# Create Python module
pybind11_add_module(breakbeat
    ${SOURCES}
    python/bindings.cpp
)

# Link libraries
target_link_directories(breakbeat PRIVATE ${SNDFILE_LIBRARY_DIRS})
target_link_libraries(breakbeat PRIVATE ${SNDFILE_LIBRARIES})

# Compiler flags
if(APPLE)
    target_compile_options(breakbeat PRIVATE -O3 -march=native -ffast-math)
endif()

# Install
install(TARGETS breakbeat
    LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}
)
