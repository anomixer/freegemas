/* Diagnostic wrapper around veramusic's player; does not alter that repo.
 * Build with /I C:\dev\veramusic\tools. Default: linear, 16-voice headroom.
 * --original restores its original tanh mix. --render file.wav renders offline.
 * This is not an exact hardware emulator or a de-click filter.
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int original_mix = 0;
static float peak_mix = 0;
static float diagnostic_mix(float value) {
    float absolute = fabsf(value * 3.0f);
    if (absolute > peak_mix) peak_mix = absolute;
    return original_mix ? tanhf(value) : value * (3.0f / 16.0f);
}
#define tanhf diagnostic_mix
#define main original_player_main
#include <psgplay.c>
#undef main
#undef tanhf

static void write_u32(FILE *file, uint32_t value) {
    for (int i = 0; i < 4; i++) fputc((value >> (8 * i)) & 255, file);
}
static int render_wav(const char *input, const char *output) {
    if (!load_psg_file(input)) return 1;
    if (totalFrames > 600 * FPS) return 1;
    FILE *file = fopen(output, "wb");
    if (!file) { perror(output); return 1; }
    uint32_t bytes = (uint32_t)totalFrames * SAMPLES_PER_FRAME * 4;
    fwrite("RIFF", 1, 4, file); write_u32(file, bytes + 36);
    fwrite("WAVEfmt ", 1, 8, file); write_u32(file, 16);
    write_u32(file, 0x00020001); write_u32(file, SAMPLE_RATE);
    write_u32(file, SAMPLE_RATE * 4); write_u32(file, 0x00100004);
    fwrite("data", 1, 4, file); write_u32(file, bytes);
    int16_t buffer[SAMPLES_PER_FRAME * 2];
    psg_reset(); currentFrame = 0; loopEnabled = false;
    for (int frame = 0; frame < totalFrames; frame++) {
        render_frame(buffer);
        if (fwrite(buffer, sizeof(buffer), 1, file) != 1) {
            fclose(file); return 1;
        }
    }
    if (fclose(file)) return 1;
    printf("Rendered %d frames; peak summed voice amplitude %.6f; mix=%s\n",
           totalFrames, peak_mix, original_mix ? "original tanh" : "linear /16");
    return 0;
}
int main(int argc, char **argv) {
    const char *output = NULL, *input = NULL;
    char **filtered = calloc((size_t)argc + 1, sizeof(char *));
    if (!filtered) return 1;
    int count = 1; filtered[0] = argv[0];
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--original")) original_mix = 1;
        else if (!strcmp(argv[i], "--render") && i + 1 < argc) output = argv[++i];
        else {
            filtered[count++] = argv[i];
            if (argv[i][0] != '-' && !input) input = argv[i];
        }
    }
    printf("Diagnostic mix: %s (no PSG changes)\n",
           original_mix ? "original tanh" : "linear, safe 16-voice headroom");
    int status = output ? (input ? render_wav(input, output) : 1)
                        : original_player_main(count, filtered);
    free(filtered); return status;
}
