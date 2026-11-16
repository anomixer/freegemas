#ifndef AUDIO_H
#define AUDIO_H

#include <stdint.h>

void audio_init(void);
void audio_play_music(int music_id);
void audio_play_sfx(int sfx_id);
void audio_stop(void);

#endif
