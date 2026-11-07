#include <stdint.h>
#include "music.h"
#include "sound.h"
#include "apple2e.h"

/* Commander X16 music: music.zcm is a 8011 Hz, mono, signed 16-bit ZCM stream
 * built from media/music.ogg by tools/build_music_zcm.py.  It is streamed from
 * hostfs with the KERNAL's MACPTR block read, so the 2 MB track never has to
 * fit in banked RAM.  The five original 8-bit PCM effects are mixed into the
 * same FIFO (VERA has only one PCM channel); their levels and music gain leave
 * enough headroom that the 16-bit sum cannot overflow. */
#define MUSIC_FILE      9u
#define MUSIC_RATE      21u             /* VERA rate used by music.zcm */
#define MUSIC_HEADER    8u
#define MUSIC_BUF       ((uint8_t *)0x0C00u)   /* 512-byte disk staging page */
#define FEED_TARGET     26700u          /* 267 bytes per VSYNC, x100 */
#define EFFECT_BUDGET   512u
#define PREFILL_STEPS   8u

extern void pcm_copy(void);
extern void pcm_mix(void);
extern void pcm_mix16(void);
extern uint16_t pcm_count;
extern uint8_t *pcm_pointer;
uint8_t *pcm_effect;

static uint8_t clock_last;
static uint8_t pcm_on, drain;
static uint8_t stream_ready, stream_at_end;
static uint8_t stream_attempted;
static uint16_t feed_frac;
static uint8_t carry, carry_valid;
static uint8_t *pending;
static uint16_t pending_count;
static uint8_t music_last;

/* Start the 16-bit FIFO with the sample clock paused.  The FIFO is filled
 * before VERA starts consuming it; a full FIFO gives about 250 ms of slack
 * for a slow frame and avoids the underrun "motorboat" at 8 kHz. */
static void pcm_start16(void) {
    VERA.audio.control = 0x20;
    VERA.audio.rate = 0;
    VERA.audio.control = 0xA0;
    VERA.audio.control = 0x2A;      /* 16-bit mono, volume 10 */
    pcm_on = 1;
    drain = 0;
}

static void pcm_resume16(void) {
    VERA.audio.rate = MUSIC_RATE;
}

static void pcm_silence(void) {
    VERA.audio.control = 0x20;
    VERA.audio.rate = 0;
    pcm_on = 0;
    drain = 0;
}

static uint8_t stream_open(void) {
    static const char name[] = "music.zcm";
    uint8_t i;
    for (i = 0; i < MUSIC_FILE; ++i) x16_name[i] = (uint8_t)name[i];
    x16_namelen = MUSIC_FILE;
    if (x16_pcm_open() != 0u) return 0;

    /* Skip the eight-byte ZCM header. */
    x16_pcm_dest = MUSIC_BUF;
    x16_pcm_count = MUSIC_HEADER;
    x16_pcm_read();
    if (x16_pcm_got != MUSIC_HEADER) {
        x16_pcm_close();
        return 0;
    }
    stream_ready = 1;
    stream_at_end = 0;
    feed_frac = 0;
    carry_valid = 0;
    pending = 0;
    pending_count = 0;
    return 1;
}
static void stream_close(void) {
    if (stream_ready) x16_pcm_close();
    stream_ready = 0;
    stream_at_end = 0;
    carry_valid = 0;
    pending = 0;
    pending_count = 0;
}

/* Add staged 16-bit effect samples to the 16-bit music samples in RAM.  The
 * FIFO is only written later by pcm_copy, so a nearly-full FIFO can never
 * lose one byte of a sample pair. */
static void mix_effect16(uint16_t n, const uint8_t *effect) {
    uint16_t i;
    for (i = 0; i < n; ++i) {
        uint16_t m = (uint16_t)MUSIC_BUF[i * 2u] |
                     (uint16_t)((uint16_t)MUSIC_BUF[i * 2u + 1u] << 8);
        int16_t e = (int16_t)((uint16_t)effect[i * 2u] |
                              (uint16_t)((uint16_t)effect[i * 2u + 1u] << 8));
        int32_t s = (int16_t)m + (int32_t)e;
        if (s > 32767) s = 32767;
        else if (s < -32768) s = -32768;
        MUSIC_BUF[i * 2u] = (uint8_t)((uint16_t)s & 0xFFu);
        MUSIC_BUF[i * 2u + 1u] = (uint8_t)(((uint16_t)s >> 8) & 0xFFu);
    }
}

static void music_prefill(void);

static void music_frame(void) {
    uint16_t want, got, total, samples;
    uint16_t sent;
    uint8_t start_ctrl;

    if (!stream_ready) return;
    start_ctrl = VERA.audio.control;

    /* First retry bytes that the FIFO was too full to accept last frame.
       Keeping them here prevents a dropped byte from shifting every later
       16-bit sample. */
    if (pending_count) {
        if (VERA.audio.control & 0x80u) return;
        pcm_pointer = pending;
        pcm_count = pending_count;
        pcm_copy();
        sent = (uint16_t)(pending_count - pcm_count);
        pending += sent;
        pending_count = pcm_count;
        if (pending_count) return;
    }

    if (stream_at_end) {
        pcm_silence();
        stream_close();
        return;
    }

    if (VERA.audio.control & 0x80u) return;   /* FIFO full */

    feed_frac = (uint16_t)(feed_frac + FEED_TARGET);
    want = (uint16_t)(feed_frac / 100u);
    feed_frac = (uint16_t)(feed_frac % 100u);
    if (start_ctrl & 0x40u) want = 510u;   /* FIFO empty: catch up (carry-safe) */
    else if (want > 268u) want = 268u;

    if (carry_valid) MUSIC_BUF[0] = carry;
    x16_pcm_dest = MUSIC_BUF + (carry_valid ? 1u : 0u);
    x16_pcm_count = want;
    x16_pcm_read();
    got = x16_pcm_got;
    if (x16_pcm_status & 0x40u) stream_at_end = 1;

    total = (uint16_t)((carry_valid ? 1u : 0u) + got);
    carry_valid = 0;
    samples = (uint16_t)(total >> 1);
    if (total & 1u) {
        carry = MUSIC_BUF[total - 1u];
        carry_valid = 1;
    }
    if (!samples) return;

    if (MUSIC_SETTING == 0u) {
        uint16_t i;
        for (i = 0; i < (uint16_t)(samples * 2u); ++i) MUSIC_BUF[i] = 0;
    }

    if (sound_remaining()) {
        uint16_t n_effects;
        uint8_t *effect = sound_stage(samples, &n_effects);
        if (n_effects) {
            mix_effect16(n_effects, effect);
            sound_stage_commit(n_effects);
        }
    }
    pcm_pointer = MUSIC_BUF;
    pcm_count = (uint16_t)(samples * 2u);
    pcm_copy();
    if (pcm_count) {
        pending = MUSIC_BUF + (uint16_t)((samples * 2u) - pcm_count);
        pending_count = pcm_count;
    }
}

static void music_prefill(void) {
    uint8_t n;
    pcm_start16();
    for (n = 0; n < PREFILL_STEPS; ++n) {
        /* Always try one frame first: after a restart the FIFO-full flag can
           still be stale for a few cycles after the reset, and breaking on it
           here would start the clock with an empty FIFO. */
        music_frame();
        if (VERA.audio.control & 0x80u) break;
    }
    pcm_resume16();
}

void music_init(void) {
    clock_last = X16_FRAME;
    music_last = X16_FRAME;
    stream_ready = 0;
    stream_attempted = 0;
    stream_at_end = 0;
    pcm_silence();
}

void music_stop(void) {
    stream_close();
    pcm_silence();
}

void music_restart(void) {
    stream_close();
    stream_attempted = 1;
    if (MUSIC_SETTING == 1u) {
        if (stream_open()) {
            music_prefill();
            music_last = X16_FRAME;
        }
    }
}

void music_clock_reset(void) {
    clock_last = X16_FRAME;
}

__attribute__((noinline)) uint8_t music_frames_elapsed(void) {
    uint8_t now = X16_FRAME;
    uint8_t n = (uint8_t)(now - clock_last);
    clock_last = now;
    return n ? n : 1u;
}

__attribute__((noinline)) void music_tick(void) {
    uint8_t now, n;
    /* Open only after all startup MLI loads have finished: opening the KERNAL
       stream before upload_scene/upload_gems used to leave the channel in an
       invalid state.  The staging page at $0C00 is free by the first frame. */
    if (!stream_ready && !stream_attempted) {
        stream_attempted = 1;
        if (stream_open()) {
            music_prefill();
            music_last = X16_FRAME;
            return;
        }
    }
    if (stream_ready) {
        now = X16_FRAME;
        if (!pcm_on) {
            music_prefill();
            music_last = now;
            return;
        }
        /* Keep the FIFO shallow so effects do not arrive a quarter second
           late.  Feed at most one frame per VSYNC: a long board scan must not
           dump several frames into the 4KB FIFO at once, because a full FIFO
           can split a 16-bit sample pair. */
        n = (uint8_t)(now - music_last);
        if (!n) return;
        music_frame();
        music_last = now;
        return;
    }

    if (pcm_on) {
        /* Let a short effect tail leave the FIFO before shutting it down. */
        if (++drain > 32u) pcm_silence();
    }
}
