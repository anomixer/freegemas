#ifndef INPUT_H
#define INPUT_H

#include <stdint.h>

void input_init(void);
void input_update(void);
uint8_t input_is_mouse_down(void);
uint16_t input_get_mouse_x(void);
uint8_t input_get_mouse_y(void);
uint8_t input_get_key(void);

#endif
