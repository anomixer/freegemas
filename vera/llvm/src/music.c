/* Exact approved PSG curves in main RAM, timed notes in aux RAM.
 * Frees aux RAM for raw PCM SFX; no audio disk I/O during gameplay.
 */
#include <stdint.h>
#include "apple2e.h"
#include "music.h"
#include "loading.h"
#include "music_data.h"
#define MUSIC_SETTING (*(volatile uint8_t *)0x03F2)
extern uint8_t mli_status;
extern void disk_read(uint16_t block,uint8_t *dest);
extern uint8_t disk_file(const char *name,uint8_t length,uint16_t *key,uint32_t *size);
extern void music_aux_init(void),music_aux_store(void),music_aux_page(void);
extern uint8_t music_aux_available(void);
uint8_t music_cache[256],music_page,music_aux_top;
uint8_t *music_source,*music_target;
uint8_t music_destination_page;
/* Asset loads are sequential. Share the reserved MLI staging page, which is
 * deliberately excluded from curve_address(), instead of another 512B BSS. */
static uint8_t *const disk_buffer=(uint8_t *)0x0C00;
static uint8_t curve_tail[MUSIC_CURVE_TAIL_SIZE];
static uint16_t disk_blocks[24];
static uint16_t music_position,music_frames,music_frame,music_size,music_notes,note_index,next_note;
static uint8_t music_ready,music_on,cache_page;
typedef struct {uint16_t curve;uint8_t remaining,byte,bits,volume,active;} Voice;
static Voice voices[16];
uint8_t music_bit_byte,music_bit_left;
static uint16_t music_curve_position;
extern uint8_t music_read_bits(uint8_t count);
static void psg_write(uint8_t reg,uint8_t value) {
    VERA.address=(uint16_t)(0xF9C0u+reg);VERA.address_hi=1;VERA.data0=value;
}
static void silence(void) {
    uint8_t channel;VERA.address=0xF9C2;VERA.address_hi=VERA_INC_4|1;
    for(channel=0;channel<16;channel++)VERA.data0=0;
}
static uint8_t *curve_address(uint16_t offset) {
    if(offset<1024u)return (uint8_t *)(0x0800u+offset);
    if(offset<5632u)return (uint8_t *)(0x0A00u+offset); /* skip $0C00-$0DFF MLI buffer */
    return curve_tail+offset-5632u;
}
__attribute__((noinline)) uint8_t music_read_byte(void) {
    if(music_curve_position>=MUSIC_CURVE_SIZE){music_ready=0;return 0;}
    return *curve_address(music_curve_position++);
}
static uint8_t event_byte(void) {
    uint8_t page=(uint8_t)(8u+(music_position>>8)),value;
    if(music_position>=music_size){music_ready=0;return 0;}
    if(page!=cache_page) {music_page=page;music_target=music_cache;music_aux_page();cache_page=page;}
    value=music_cache[(uint8_t)music_position];++music_position;return value;
}
static uint16_t event_word(void) {
    uint16_t value=event_byte();return value|((uint16_t)event_byte()<<8);
}
__attribute__((noinline)) void music_restart(void) {
    uint8_t i;music_frame=0;music_position=12;note_index=0;next_note=65535;cache_page=255;
    for(i=0;i<16;i++)voices[i].active=voices[i].remaining=0;
}
static uint8_t index_file(uint16_t key) {
    uint8_t i;disk_read(key,disk_buffer);if(mli_status)return 0;
    for(i=0;i<24;i++)disk_blocks[i]=(uint16_t)disk_buffer[i]|((uint16_t)disk_buffer[256u+i]<<8);
    return 1;
}
void music_init(void) {
    uint16_t key,at=0;uint32_t size;uint8_t n,pages;
    music_ready=music_on=music_aux_top=0;
    if(!music_aux_available())return;
    if(!disk_file("MUSIC.CRV",9,&key,&size)||size!=MUSIC_CURVE_SIZE||!index_file(key))return;
    pages=(uint8_t)((MUSIC_CURVE_SIZE+511u)>>9);
    for(n=0;n<pages;n++) {
        uint16_t i,count=MUSIC_CURVE_SIZE-at;if(count>512u)count=512;
        disk_read(disk_blocks[n],disk_buffer);if(mli_status)return;
        for(i=0;i<count;i++)*curve_address(at++)=disk_buffer[i];
        loading_step();
    }
    if(!disk_file("MUSIC.FGM",9,&key,&size)||size<12||size>9216u||!index_file(key))return;
    music_size=(uint16_t)size;
    music_aux_init();music_destination_page=8;pages=(uint8_t)((music_size+511u)>>9);
    for(n=0;n<pages;n++) {
        disk_read(disk_blocks[n],disk_buffer);if(mli_status)return;
        if(!n) {
            if(disk_buffer[0]!='F'||disk_buffer[1]!='G'||disk_buffer[2]!='M'||disk_buffer[3]!='2')return;
            music_frames=(uint16_t)disk_buffer[4]|((uint16_t)disk_buffer[5]<<8);
            music_notes=(uint16_t)disk_buffer[8]|((uint16_t)disk_buffer[9]<<8);
            if(!music_frames||music_frames>36000u||
               ((uint16_t)disk_buffer[6]|((uint16_t)disk_buffer[7]<<8))!=music_size||
               ((uint16_t)disk_buffer[10]|((uint16_t)disk_buffer[11]<<8))!=MUSIC_CURVE_SIZE)return;
        }
        music_source=disk_buffer;music_aux_store();
        music_source=disk_buffer+256;music_aux_store();
        loading_step();
    }
    music_aux_top=music_destination_page;music_ready=1;music_restart();
}
__attribute__((noinline)) void music_stop(void) {
    uint8_t ctrl=VERA.control,hi;uint16_t address;
    VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    silence();music_on=0;
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}
__attribute__((noinline)) void music_tick(void) {
    uint8_t ctrl,hi,channel;uint16_t address;
    if(!music_ready||!MUSIC_SETTING) {if(music_on)music_stop();return;}
    ctrl=VERA.control;VERA.control=0;address=VERA.address;hi=VERA.address_hi;
    if(!music_on||music_frame==music_frames) {
        VERA.address=0xF9C0;VERA.address_hi=VERA_INC_1|1;
        for(channel=0;channel<16;channel++){VERA.data0=0;VERA.data0=0;VERA.data0=0;VERA.data0=128;}
        music_restart();music_on=1;
    }
    for(channel=0;channel<16;channel++)if(voices[channel].active&&!voices[channel].remaining) {
        voices[channel].active=0;psg_write(channel*4u,0);psg_write(channel*4u+1u,0);psg_write(channel*4u+2u,0);
    }
    if(next_note==65535u&&note_index<music_notes)next_note=event_word();
    while(next_note==music_frame && music_ready) {
        uint8_t frequency;uint16_t hz;Voice *v;
        channel=event_byte();frequency=event_byte();
        if(channel>=16||frequency>=MUSIC_FREQUENCIES){music_ready=0;break;}
        v=voices+channel;v->curve=event_word();v->remaining=event_byte();
        if(v->curve>=MUSIC_CURVE_SIZE||!v->remaining){music_ready=0;break;}
        v->active=1;v->byte=v->bits=v->volume=0;
        hz=music_frequencies[frequency];psg_write(channel*4u,(uint8_t)hz);psg_write(channel*4u+1u,(uint8_t)(hz>>8));
        ++note_index;next_note=note_index<music_notes?event_word():65535;
    }
    for(channel=0;channel<16 && music_ready;channel++)if(voices[channel].active) {
        Voice *v=voices+channel;uint8_t node=0,value;
        music_curve_position=v->curve;music_bit_byte=v->byte;music_bit_left=v->bits;
        while(node<128)node=music_curve_tree[(uint16_t)node*2u+music_read_bits(1)];
        node-=128;value=node==64?music_read_bits(6):(uint8_t)(v->volume-node);
        if(value>63){music_ready=0;break;}
        /* A new note can reuse a channel whose previous volume was nonzero. */
        psg_write(channel*4u+2u,value?(uint8_t)(value|192u):0);
        v->volume=value;v->curve=music_curve_position;v->byte=music_bit_byte;v->bits=music_bit_left;
        --v->remaining;
    }
    if(!music_ready){silence();music_on=0;}++music_frame;
    VERA.address=address;VERA.address_hi=hi;VERA.control=ctrl;
}
