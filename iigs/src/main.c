#include <stdint.h>
#include "video.h"
#include "audio.h"
#include "input.h"
#include "board.h"

Board board;

int main(void) {
    uint8_t x, y;
    /* Disable interrupts to stop GS/OS from resetting our hardware registers in the background! */
    __asm__ volatile ("sei");
    

    
    /* Initialize IIGS hardware */
    video_init();
    
    audio_init();
    input_init();
    
    /* Generate a random board */
    board_seed(&board, 1234); /* Seed the RNG so it generates gems! */
    board_generate(&board);
    
    /* Draw the initial board */
    for (y = 0; y < 8; ++y) {
        for (x = 0; x < 8; ++x) {
            uint8_t gem = board.cells[y][x];
            if (gem >= 1 && gem <= 7) {
                video_draw_gem(x * 32, y * 32, gem);
            }
        }
    }
    
    /* Simple run loop */
    while (1) {
        input_update();
        if (input_get_key() == 27) { /* ESC key */
            break;
        }
    }
    
    audio_stop();
    __asm__ volatile ("cli"); /* Re-enable interrupts before returning to GS/OS / ProDOS */
    return 0;
}
