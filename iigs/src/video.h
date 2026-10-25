#ifndef VIDEO_H
#define VIDEO_H

#include <stdint.h>

void video_init(void);
void video_update(void);
void video_draw_gem(int x, int y, int gem_type);
void video_draw_text(int x, int y, const char* str);
void video_hide_sprite(int slot);

#endif
