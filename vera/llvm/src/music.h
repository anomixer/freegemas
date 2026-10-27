#ifndef FREEGEMAS_MUSIC_H
#define FREEGEMAS_MUSIC_H
/* 1 = MUSIC.VZM (YM2151 + PSG percussion), 0 = MUSIC.PSG fallback. */
extern uint8_t music_fm;
void music_init(void);
void music_tick(void);
void music_stop(void);
void music_restart(void);
#endif
