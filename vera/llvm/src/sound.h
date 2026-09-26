#ifndef FREEGEMAS_SOUND_H
#define FREEGEMAS_SOUND_H
#include <stdint.h>
enum { SFX_SELECT, SFX_INVALID, SFX_MATCH1, SFX_MATCH2, SFX_MATCH3,
       SFX_FALL, SFX_HINT, SFX_RESET, SFX_GAME_OVER };
void sound_init(void);
void sound_play(uint8_t effect);
void sound_tick(void);
void sound_stop(void);
#endif
