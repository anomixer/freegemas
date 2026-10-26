cmake_minimum_required(VERSION 3.10)
project(freegemas_wasm CXX C)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(ROOT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/..")

# Collect game source files
file(GLOB SOURCE_FILES
    "${ROOT_DIR}/src/*.cpp"
)

# Include directories
include_directories(
    "${ROOT_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/vendor"
)

# Emscripten flags
set(EMSCRIPTEN_FLAGS
    "-s USE_SDL=2"
    "-s USE_SDL_IMAGE=2"
    "-s SDL2_IMAGE_FORMATS=[\"png\"]"
    "-s USE_SDL_MIXER=2"
    "-s USE_SDL_TTF=2"
    "-s USE_OGG=1"
    "-s USE_VORBIS=1"
    "-s ALLOW_MEMORY_GROWTH=1"
    "-s INITIAL_MEMORY=67108864"
    "-s EXPORTED_RUNTIME_METHODS=[\"ccall\",\"cwrap\"]"
    "--preload-file ${ROOT_DIR}/media@media"
    "--shell-file ${CMAKE_CURRENT_SOURCE_DIR}/shell.html"
    "-O2"
)

string(JOIN " " EMSCRIPTEN_FLAGS_STR ${EMSCRIPTEN_FLAGS})
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${EMSCRIPTEN_FLAGS_STR}")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${EMSCRIPTEN_FLAGS_STR}")

add_executable(freegemas ${SOURCE_FILES} "${CMAKE_CURRENT_SOURCE_DIR}/vendor/jsoncpp.cpp")

set_target_properties(freegemas PROPERTIES OUTPUT_NAME "index")
set_target_properties(freegemas PROPERTIES SUFFIX ".html")
set_target_properties(freegemas PROPERTIES LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/shell.html")
