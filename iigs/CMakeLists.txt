cmake_minimum_required(VERSION 3.20)
project(FreegemasIIgs LANGUAGES NONE)

set(LLVM_MOS_SDK "C:/dev/llvm-mos-sdk/install" CACHE PATH "llvm-mos SDK")
find_program(MOS_CLANG NAMES mos-apple2e-clang.bat mos-apple2e-clang HINTS "${LLVM_MOS_SDK}/bin" NO_DEFAULT_PATH REQUIRED)
find_program(CADIUS NAMES cadius.exe cadius HINTS "${CMAKE_CURRENT_SOURCE_DIR}" NO_DEFAULT_PATH REQUIRED)

set(SRC "${CMAKE_CURRENT_SOURCE_DIR}/src")
set(OUT "${CMAKE_BINARY_DIR}/freegemas.bin")

add_custom_command(OUTPUT "${OUT}"
  COMMAND "${MOS_CLANG}" -Oz -mcpu=mos65c02 -o "${OUT}" 
    "${SRC}/main.c" "${SRC}/video.c" "${SRC}/audio.c" "${SRC}/input.c" "${SRC}/board.c" "${SRC}/assets.c" "${SRC}/shim.S"
  DEPENDS "${SRC}/main.c" "${SRC}/video.c" "${SRC}/audio.c" "${SRC}/input.c" "${SRC}/board.c" "${SRC}/assets.c" "${SRC}/shim.S"
  VERBATIM
)

add_custom_target(freegemas ALL DEPENDS "${OUT}")

add_custom_command(TARGET freegemas POST_BUILD
    COMMAND "${CADIUS}" CREATEVOLUME freegemas.2mg FREEGEMAS 800KB
    COMMAND "${CMAKE_COMMAND}" -E env python -c "import sys; open('FG.SYSTEM#FF0000', 'wb').write(open('${OUT}', 'rb').read()[4:])"
    COMMAND "${CADIUS}" ADDFILE freegemas.2mg /FREEGEMAS/ "FG.SYSTEM#FF0000"
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
