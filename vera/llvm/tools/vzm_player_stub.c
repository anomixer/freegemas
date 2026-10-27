/* Test-only stubs: links music.c into a standalone 65C02 harness so the VZM
 * decoder and music_init() file selection can be stepped on the model.
 * The harness feeds files from a synthetic pattern, never from the disk.  The
 * volatile flag stops the mos-clang default LTO from folding music_init(). */
#include <stdint.h>
#include "music.h"
uint8_t mli_status;
volatile uint8_t vzm_stub_flag;      /* unused by the current tests */
volatile uint8_t vzm_stub_psg_size;  /* small, so no Aux LC mapping is needed */
volatile uint8_t vzm_stub_vzm_ok = 1;
volatile uint8_t vzm_stub_psg_ok = 1;
volatile uint8_t vzm_stub_name[16];
void loading_step(void) {}

static int named(const char *name, uint8_t length, const char *want) {
    for (uint8_t i = 0; i < length; ++i)
        if (name[i] != want[i]) return 0;
    return want[length] == 0;
}

uint8_t disk_file(const char *name, uint8_t length, uint16_t *key,
                  uint32_t *size) {
    for (uint8_t i = 0; i < 15; ++i)
        vzm_stub_name[i] = i < length ? (uint8_t)name[i] : 0;
    if (named(name, length, "MUSIC.VZM") && vzm_stub_vzm_ok) {
        *size = 22974;            /* the shipped MUSIC.VZM length */
    } else if (named(name, length, "MUSIC.PSG") && vzm_stub_psg_ok) {
        *size = vzm_stub_psg_size ? vzm_stub_psg_size : 1;
    } else {
        return 0;
    }
    *key = 0;
    return 1;
}

void disk_read(uint16_t block, uint8_t *dest) {
    for (uint16_t i = 0; i < 512; ++i) dest[i] = (uint8_t)(block * 7 + i);
}

/* Force the linker to keep the player entry points as callable symbols. */
static void (*volatile keep)(void);
int main(void) {
    keep = music_init; keep();
    keep = music_tick; keep();
    keep = music_restart; keep();
    keep = music_stop; keep();
    return 0;
}
