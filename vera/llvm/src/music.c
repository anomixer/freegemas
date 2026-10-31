/* Background music: streamed signed 8-bit PCM (MUSIC.PCM).
 *
 * VERA has a single PCM FIFO and the sound effects share it, so the game
 * feeds one 8-bit stream: music bytes read from disk plus the active effect,
 * added sample by sample.  The two sources are limited to 0.70 and 0.29 of
 * full scale at build time, so the sum always fits signed 8-bit without a
 * clamp.
 *
 * The FIFO is kept about two VSYNC frames deep: enough slack for a slow match
 * cascade, but small enough that an effect is not audibly late.  A small RAM
 * ring is topped up from MUSIC.PCM every few frames; the disk is never read to
 * fill the FIFO directly.
 *
 * waitvsync returns without waiting when a frame overruns its VSYNC (a match
 * cascade, the music disk read), so the 133/134 samples fed per iteration lag
 * the samples the VERA drains in real time and the queue creeps downward until
 * the player runs dry: a periodic "bo~bo~" pop.  The VERA audio-low flag
 * (ISR bit 3, FIFO below 1024) reports that depth directly, so a small
 * catch-up payment is added whenever the queue is shallower than the target,
 * instead of waiting for the EMPTY flag to find out too late.
 */
#include <stdint.h>
#include "apple2e.h"
#include "music.h"
#include "sound.h"

#define MUSIC_SETTING (*(volatile uint8_t *)0x03F2)
#define MUSIC_RING   1024u       /* staging ring, one block plus slack */
#define MUSIC_BUFFER 1024u       /* samples queued (~128 ms at rate 21) */
#define MUSIC_RATE   21u         /* 21 * 25e6 / 512 / 128 = 8010.86 Hz */
#define MUSIC_VOLUME 0x0Fu       /* mono 8-bit, volume 15 */
#define MUSIC_CATCHUP 64u        /* samples repaid while the queue is low */

extern uint8_t mli_status;
extern void disk_read(uint16_t block, uint8_t *dest);
extern uint16_t disk_read_seq(uint16_t count, uint8_t *dest);
extern uint8_t disk_file(const char *name, uint8_t length, uint16_t *key, uint32_t *size);
extern void disk_close(void);
extern uint8_t disk_epoch(void);
extern void pcm_copy(void), pcm_mix(void);
extern uint16_t pcm_count;
extern uint8_t *pcm_pointer;
extern uint8_t *pcm_effect;

static uint8_t ring[MUSIC_RING];
static const uint8_t silence[256];
static uint16_t ring_read, ring_count;
static uint32_t music_size, music_file_pos, music_mark;
static uint8_t music_ready, music_on, music_mark_ok;
static uint8_t music_epoch, music_fd;
static uint8_t budget_phase;

/* ProDOS closes the previous file whenever another one is opened, so the
 * epoch reported by main.c tells us that our refnum is gone. */
static uint8_t open_file(void) {
    uint16_t key;
    uint32_t size;
    if (music_fd && disk_epoch() == music_epoch) return 1;
    mli_status = 0;
    if (!disk_file("MUSIC.PCM", 9, &key, &size)) { music_fd = 0; return 0; }
    music_size = size;
    music_fd = 1;
    music_epoch = disk_epoch();
    music_file_pos = 0;
    music_mark = 0;
    music_mark_ok = 0;
    return 1;
}

static uint8_t read_block(void) {
    uint32_t offset;
    uint16_t want, got;
    if (!music_fd) return 0;
    if (music_file_pos >= music_size) music_file_pos = 0;   /* seamless loop */
    offset = music_file_pos;
    want = music_size - offset > MUSIC_RING ? MUSIC_RING : (uint16_t)(music_size - offset);
    if (music_mark_ok && offset == music_mark) {
        mli_status = 0;
        got = disk_read_seq(want, ring);
        if (!got) {             /* the mark may be unusable; restart from here */
            disk_read((uint16_t)(offset >> 9), ring);
            if (mli_status) return 0;
            got = music_size - offset > 512u ? 512u : (uint16_t)(music_size - offset);
        }
    } else {
        disk_read((uint16_t)(offset >> 9), ring);
        if (mli_status) return 0;
        got = music_size - offset > 512u ? 512u : (uint16_t)(music_size - offset);
    }
    if (!got) return 0;
    ring_read = 0;
    ring_count = got;
    music_file_pos = offset + got;
    music_mark = offset + got;
    music_mark_ok = 1;
    return 1;
}

static void engine_silence(void) {
    VERA.audio.control = 0x00;
    VERA.audio.rate = 0;
    VERA.audio.control = 0xA0;      /* reset the FIFO, stay muted */
}

/* Feed at most `budget` samples, mixing the active effect when one is playing.
 * The VERA port 0 address is saved and restored because reading the effect
 * stage uses the same port. */
__attribute__((noinline)) static void feed(uint8_t use_music, uint16_t budget) {
    uint8_t ctrl = VERA.control, hi = VERA.address_hi;
    uint16_t address = VERA.address;
    while (budget) {
        uint16_t chunk, sent, room, ecount = 0;
        uint8_t *mptr, *eptr = 0;
        if (use_music) {
            if (!ring_count && !read_block()) break;
            if (!ring_count) break;
            chunk = ring_count > 255u ? 255u : ring_count;
            if (MUSIC_RING - ring_read < chunk) chunk = MUSIC_RING - ring_read;
            mptr = &ring[ring_read];
        } else {
            chunk = 255u;
            mptr = (uint8_t *)silence;
        }
        if (chunk > budget) chunk = budget;
        if (sound_remaining()) {
            eptr = sound_stage(chunk, &ecount);
            if (eptr) {
                /* The effect stage is 256 bytes, so its run must not wrap. */
                room = (uint16_t)(256u - ((uint16_t)(uintptr_t)eptr & 0xFFu));
                if (ecount > room) ecount = room;
                if (ecount < chunk) chunk = ecount;
            }
            if (!ecount) eptr = 0;
        }
        if (!chunk) break;
        pcm_count = chunk;
        pcm_pointer = mptr;
        if (eptr) { pcm_effect = eptr; pcm_mix(); }
        else pcm_copy();
        sent = (uint16_t)(chunk - pcm_count);
        if (use_music) {
            ring_read += sent;
            if (ring_read >= MUSIC_RING) ring_read = 0;
            ring_count -= sent;
        }
        if (eptr) sound_stage_commit(sent);
        budget -= sent;
        if (sent < chunk) break;    /* FIFO full */
    }
    /* Restore control first: the address registers belong to whichever port
     * control selects, and the effect staging left it on port 0. */
    VERA.control = ctrl;
    VERA.address = address;
    VERA.address_hi = hi;
}

__attribute__((noinline)) static void engine_start(uint8_t use_music) {
    VERA.audio.control = 0x20;
    VERA.audio.rate = 0;
    VERA.audio.control = 0xA0;      /* discard any stale samples */
    VERA.audio.control = MUSIC_VOLUME;
    feed(use_music, MUSIC_BUFFER);
    VERA.audio.rate = MUSIC_RATE;
}

void music_init(void) {
    uint16_t key;
    uint32_t size;
    music_ready = 0;
    music_on = 0;
    music_fd = 0;
    ring_read = ring_count = 0;
    music_file_pos = 0;
    music_mark_ok = 0;
    budget_phase = 0;
    /* Validate only: sound_init opens the effect files right after this and
     * would close ours anyway. */
    if (!disk_file("MUSIC.PCM", 9, &key, &size)) return;
    if (size < 512u || size > 0x180000u) { disk_close(); return; }
    music_size = size;
    music_ready = 1;
    disk_close();
}

__attribute__((noinline)) void music_stop(void) {
    engine_silence();
    music_on = 0;
    disk_close();
    music_fd = 0;
    ring_read = ring_count = 0;
    music_file_pos = 0;
    music_mark_ok = 0;
}

__attribute__((noinline)) void music_restart(void) {
    music_file_pos = 0;
    music_mark_ok = 0;
    ring_read = ring_count = 0;
}

__attribute__((noinline)) void music_tick(void) {
    uint8_t music = MUSIC_SETTING != 0;
    uint8_t irq;
    uint16_t budget;
    if (!music_ready) return;
    if (!music && !sound_remaining()) {
        if (music_on) music_stop();
        return;
    }
    if (music) {
        if (!open_file()) { music_ready = 0; music_stop(); return; }
        if (!music_on) { engine_start(1); music_on = 1; return; }
    } else if (!music_on) {
        engine_start(0);
        music_on = 1;
        return;
    }
    /* An empty FIFO means a frame overran the buffer; refill it rather than
     * trickling a frame's worth back and leaving the stream starved. */
    if (VERA.audio.control & 0x40u) {
        feed(music, MUSIC_BUFFER);
        return;
    }
    /* 133/134 alternately averages the 133.51 samples one VSYNC drains, so
     * the queue depth (and effect latency) stays put instead of creeping. */
    budget_phase ^= 1u;
    budget = (uint16_t)(133u + budget_phase);
    irq = VERA.irq_flags;
    if (irq & VERA_IRQ_AUDIO_LOW) {
        /* A late frame skipped its VSYNC, so one feed is not one VSYNC worth
         * of audio any more.  Pay the shortfall back rather than letting the
         * queue slide until the player underruns. */
        budget += MUSIC_CATCHUP;
        VERA.irq_flags = VERA_IRQ_AUDIO_LOW;    /* clear a latched flag */
    }
    feed(music, budget);
}
