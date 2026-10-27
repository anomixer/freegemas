#!/usr/bin/env python3
"""Transcribe media/music.ogg into a VERA stream: YM2151 FM voices + VERA PSG percussion.

    ogg -> 16 kHz mono analysis WAV -> FFT note/drum analysis
        -> 60 Hz event list -> ZSM byte stream -> VERA "VZM" re-pack

The note/drum analysis is shared with ``wav2psg.py`` (same detectors), the PSG
part is reduced to the four percussion voices (12-15) and every detected note
becomes a YM2151 note.  The intermediate ZSM keeps the standard Commander X16
ZSM layout (16-byte header, PSG/FM/delay commands); the VZM file is that same
ZSM stream re-packed for the Apple II player:

  $00-$7F  delay       consume the current 60 Hz tick, wait N more
  $80-$BF  PSG write   register = byte & $3F, next byte value
  $C0-$DF  FM batch    count = (byte & $1F) + 1, then count x (reg, value)
  $FF      end of song loop back to offset 0

Register writes are de-duplicated against a shadow table that starts at zero
(the player zeroes PSG + YM2151 at start/loop).  ``$08`` (YM2151 key mask) is
always forwarded verbatim: a zero mask releases, a non-zero mask keys on, and
two key-ons in a row are a legitimate retrigger.

Unlike ``cx16-othello-vera``'s converter this one does not pad records to 512
byte blocks: the Apple II player preloads the whole stream, so no record can be
split by a block read.  Dropping the padding keeps the stream inside the
63,488-byte Aux RAM budget.

Outputs:
  vera/generated/music.vzm                 packed stream (shipped as MUSIC.VZM)
  vera/generated/music.zsm                 intermediate ZSM (reference/preview)
  vera/generated/music_vzm.h               size / tick constants for C
  vera/llvm/build/music_vzm_report.json    conversion statistics
  vera/llvm/build/music_vzm_preview.wav    optional offline render (melodius)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
VERA = HERE.parent
sys.path.insert(0, str(HERE))

from wav2psg import CLOCK, analyze, decode, percussion, route_short_transients  # noqa: E402

TICK_RATE = 60
MAX_STREAM = 63488          # music_init() hard gate (248 x 256-byte pages)
FM_CHANNELS = 8
FM_TL_BASE = 0x00       # total level of a full-velocity carrier (0 = loudest)
FM_TL_SPAN = 28         # attenuation headroom for quiet notes
PSG_VOICES = 16
PERCUSSION_FIRST = 12

# ---------------------------------------------------------------------------
# YM2151 key code
# ---------------------------------------------------------------------------
# KC = octave << 4 | note.  The 4-bit note field is "gappy": the chip subtracts
# (note >> 2), so 12 semitones map onto 16 codes with values 3/4, 7/8, 11/12
# shared.  Measured with melodius.exe on the YM2151 core: $4A plays A4 and
# $3E plays C4, i.e. semitone s uses INVERSE[s-1] inside a block and C sits on
# note code 14 of the block below.  See llvm/build/fm_kc_table.py.
KC_INVERSE = (0, 1, 2, 3, 5, 6, 7, 9, 10, 11, 13)  # adjusted semitone -> note code


def kc_for_midi(midi: int) -> int:
    midi = int(midi)
    semitone = midi % 12
    if semitone == 0:
        octave = midi // 12 - 2
        note = 14
    else:
        octave = midi // 12 - 1
        note = KC_INVERSE[semitone - 1]
    if not 0 <= octave <= 7:
        raise ValueError(f"note {midi} is outside the YM2151 KC range")
    return (octave << 4) | note


# ---------------------------------------------------------------------------
# YM2151 patches (CON=4: O1->O2 and O3->O4, two parallel two-operator pairs)
# ---------------------------------------------------------------------------
def _op(mul, tl, ar, dr, sr, sl, rr, dt1=0, ams=0, dt2=0, ks=0):
    return {
        'dtmul': (dt1 << 4) | mul,
        'tl': tl,
        'ksar': (ks << 6) | ar,
        'amsdr': (ams << 7) | dr,
        'dt2sr': (dt2 << 6) | sr,
        'slrr': (sl << 4) | rr,
    }


OPERATOR_BASES = (0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0)
OPERATOR_KEYS = ('dtmul', 'tl', 'ksar', 'amsdr', 'dt2sr', 'slrr')

PATCHES = {
    # Operator register slots are M1, M2, C1, C2 (ymfm natural order M1, C1,
    # M2, C2).  CON=4 wires M1->C1 and M2->C2, so C1/C2 are the audible
    # carriers and the per-note total level belongs to C1 (slot 2).
    # Soft round bass: the M2/C2 pair is muted so the tone stays clean.
    'bass': {
        'alg': 4,
        'carrier': 2,           # C1 carries the per-note level
        'ops': (
            _op(mul=1, tl=0x20, ar=31, dr=10, sr=0, sl=4, rr=10),   # M1
            _op(mul=1, tl=0x7F, ar=31, dr=10, sr=0, sl=15, rr=12),  # M2 (off)
            _op(mul=1, tl=0x00, ar=31, dr=10, sr=0, sl=4, rr=10),   # C1
            _op(mul=1, tl=0x7F, ar=31, dr=10, sr=0, sl=15, rr=12),  # C2 (off)
        ),
    },
    # Bright struck tone: one 2:1 FM pair plus a quieter 4:1 pair.
    'tine': {
        'alg': 4,
        'carrier': 2,
        'ops': (
            _op(mul=2, tl=0x1A, ar=31, dr=9, sr=0, sl=5, rr=12),    # M1
            _op(mul=4, tl=0x2A, ar=31, dr=11, sr=0, sl=7, rr=13),   # M2
            _op(mul=1, tl=0x00, ar=31, dr=9, sr=0, sl=5, rr=12),    # C1
            _op(mul=1, tl=0x26, ar=31, dr=10, sr=0, sl=7, rr=13),   # C2
        ),
    },
}

ROLE = ('bass', 'bass', 'tine', 'tine', 'tine', 'tine', 'tine', 'tine')
BASS_SPLIT = 52             # MIDI notes below this prefer the bass channels


def patch_writes(prefix):
    """Yield (reg, value) programming one channel's patch (reg without channel)."""
    writes = [(0x20, 0xC0 | prefix['alg'])]
    for index, values in enumerate(prefix['ops']):
        for base, key in zip(OPERATOR_BASES, OPERATOR_KEYS):
            writes.append((base + index * 8, values[key]))
    return writes


def tl_for_level(level, peak, base):
    """Map a normalised amplitude onto a YM2151 total-level byte."""
    if level <= 0:
        return 0x7F
    amp = min(1.0, (level / peak) ** 0.6)
    return int(round(base + (1.0 - amp) * FM_TL_SPAN))


# ---------------------------------------------------------------------------
# 60 Hz event list
# ---------------------------------------------------------------------------
def build_events(notes, amplitudes, drums):
    """Return (fm_writes, psg_writes, frames, stats)."""
    levels, hits = route_short_transients(notes, amplitudes, drums)
    percussion_regs = percussion(hits)
    frames = len(levels)
    fm = [[] for _ in range(frames)]
    psg = [[] for _ in range(frames)]

    peak = float(np.percentile(levels[levels > 0], 99)) if np.any(levels) else 1.0

    # Frame 0: program both patches on every FM channel (player starts zeroed).
    for channel in range(FM_CHANNELS):
        for reg, value in patch_writes(PATCHES[ROLE[channel]]):
            fm[0].append((reg + channel, value))

    slots = [None] * FM_CHANNELS      # note index owned by each channel
    played = [0] * FM_CHANNELS        # MIDI note currently keyed on (-1 none)
    release = [0] * FM_CHANNELS
    note_starts = note_stops = 0

    previous_psg = [None] * 64
    for frame in range(frames):
        frame_levels = levels[frame]

        chosen = [int(n) for n in np.flatnonzero(frame_levels > peak * 0.045)]
        chosen.sort(key=lambda n: frame_levels[n], reverse=True)
        chosen = chosen[:FM_CHANNELS]

        # Stable ownership: keep a note on its channel while it lasts, release
        # the channel after three silent frames.
        for channel in range(FM_CHANNELS):
            note = slots[channel]
            if note is not None and note not in chosen:
                release[channel] += 1
                if release[channel] >= 3:
                    slots[channel] = None
                    if played[channel] >= 0:
                        fm[frame].append((0x08, channel))
                        played[channel] = -1
                        note_stops += 1
            elif note is not None:
                release[channel] = 0

        for note in chosen:
            if note in slots:
                continue
            role = 'bass' if notes[note] < BASS_SPLIT else 'tine'
            free = [c for c in range(FM_CHANNELS) if slots[c] is None]
            preferred = [c for c in free if ROLE[c] == role] or free
            if not preferred:
                continue
            channel = preferred[0]
            slots[channel] = note
            release[channel] = 0
            midi = int(notes[note])
            carrier = PATCHES[ROLE[channel]]['carrier']
            if played[channel] >= 0:
                fm[frame].append((0x08, channel))       # release before retrigger
            fm[frame].append((0x28 + channel, kc_for_midi(midi)))
            fm[frame].append((0x60 + carrier * 8 + channel,
                              tl_for_level(frame_levels[note], peak, FM_TL_BASE)))
            fm[frame].append((0x08, 0x78 | channel))    # key on all four operators
            played[channel] = midi
            note_starts += 1

        # Percussion: only rewrite registers whose value actually changed.
        voices = percussion_regs[frame].reshape(16)
        for index in range(16):
            value = int(voices[index])
            if previous_psg[PERCUSSION_FIRST * 4 + index] != value:
                previous_psg[PERCUSSION_FIRST * 4 + index] = value
                psg[frame].append((PERCUSSION_FIRST * 4 + index, value))

    stats = {'frames': frames, 'noteStarts': note_starts, 'noteStops': note_stops}
    return fm, psg, frames, stats


# ---------------------------------------------------------------------------
# ZSM byte stream
# ---------------------------------------------------------------------------
ZSM_END = 0x80


def delay_chunks(ticks):
    while ticks > 0:
        chunk = min(ticks, 127)
        yield chunk
        ticks -= chunk


def encode_zsm(fm, psg, frames):
    """Interleave the per-frame writes into a ZSM stream that loops at offset 0."""
    events = [frame for frame in range(frames) if fm[frame] or psg[frame]]
    last_event = events[-1] if events else 0
    out = bytearray()
    previous = 0
    for frame in events:
        for chunk in delay_chunks(frame - previous):
            out.append(0x80 | chunk)
        previous = frame
        for reg, value in psg[frame]:
            out.extend((reg, value))
        pairs = fm[frame]
        for start in range(0, len(pairs), 63):
            batch = pairs[start:start + 63]
            out.append(0x40 | len(batch))
            for reg, value in batch:
                out.extend((reg, value))
    # Hold the final tick for its full 60 Hz slot, then loop to offset 0.
    for chunk in delay_chunks(max(1, frames - last_event)):
        out.append(0x80 | chunk)
    out.append(ZSM_END)
    header = bytearray(b'zm\x00')
    header += (16).to_bytes(3, 'little')      # loop offset: first stream byte
    header += bytes(3)                        # no PCM
    header += bytes((0xFF, 0xFF, 0x0F))       # fm mask 8 bits, psg mask 16 bits
    header += TICK_RATE.to_bytes(2, 'little')
    header += bytes(2)
    return bytes(header + out), events[-1] if events else 0


# ---------------------------------------------------------------------------
# VZM re-pack (dedupe + batched FM writes)
# ---------------------------------------------------------------------------
VZM_NOP = 0xE0
VZM_END = 0xFF
MAX_FM_BATCH = 32


def zsm_to_vzm(zsm):
    if len(zsm) < 16 or zsm[:2] != b'zm':
        raise ValueError('not a ZSM stream (missing "zm" magic)')
    tick_rate = int.from_bytes(zsm[12:14], 'little')
    if tick_rate != TICK_RATE:
        raise ValueError(f'unsupported tick rate {tick_rate}')
    out = bytearray()
    fm_last = bytearray(256)
    psg_last = bytearray(64)
    tick_psg = []
    tick_fm = []
    stats = {'psgWrites': 0, 'psgKept': 0, 'fmWrites': 0, 'fmKept': 0, 'ticks': 0}
    ptr = 16

    def flush():
        nonlocal tick_psg, tick_fm
        for reg, value in tick_psg:
            out.extend((0x80 | reg, value))
        for start in range(0, len(tick_fm), MAX_FM_BATCH):
            batch = tick_fm[start:start + MAX_FM_BATCH]
            out.append(0xC0 | (len(batch) - 1))
            for reg, value in batch:
                out.extend((reg, value))
        tick_psg = []
        tick_fm = []

    while ptr < len(zsm):
        command = zsm[ptr]
        ptr += 1
        if command < 0x40:
            value = zsm[ptr]
            ptr += 1
            stats['psgWrites'] += 1
            if value != psg_last[command]:
                psg_last[command] = value
                tick_psg.append((command, value))
                stats['psgKept'] += 1
            continue
        if command == 0x40:
            ext = zsm[ptr]
            ptr += 1 + (ext & 0x3F)
            continue
        if command < 0x80:
            count = command & 0x3F
            for _ in range(count):
                reg = zsm[ptr]
                value = zsm[ptr + 1]
                ptr += 2
                stats['fmWrites'] += 1
                if reg == 0x08 or value != fm_last[reg]:
                    fm_last[reg] = value
                    tick_fm.append((reg, value))
                    stats['fmKept'] += 1
            continue
        if command == ZSM_END:
            break
        flush()
        delay = command & 0x7F
        stats['ticks'] += delay
        while delay > 0:
            chunk = min(delay, 127)
            out.append(chunk - 1)
            delay -= chunk
    flush()
    out.append(VZM_END)
    return bytes(out), stats


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def check_stream(vzm, frames):
    """Fail loudly on a malformed stream instead of shipping a bad asset."""
    ptr = 0
    ticks = 0
    fm = 0
    psg = 0
    while ptr < len(vzm):
        command = vzm[ptr]
        ptr += 1
        if command < 0x80:
            ticks += (command & 0x7F) + 1
        elif command < 0xC0:
            reg = command & 0x3F
            if reg >= 64:
                raise ValueError('PSG register out of range')
            psg += 1
            ptr += 1
        elif command < 0xE0:
            count = (command & 0x1F) + 1
            fm += count
            ptr += 2 * count
        elif command < 0xFF:
            pass
        else:
            return ticks, fm, psg
        if ptr > len(vzm):
            raise ValueError('stream ran past the end')
    raise ValueError('stream has no end marker')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path,
                        default=VERA.parent / 'media/music.ogg')
    parser.add_argument('--vzm', type=Path, default=VERA / 'generated/music.vzm')
    parser.add_argument('--zsm', type=Path, default=VERA / 'generated/music.zsm')
    parser.add_argument('--header', type=Path,
                        default=VERA / 'generated/music_vzm.h')
    parser.add_argument('--preview', type=Path,
                        default=VERA / 'llvm/build/music_vzm_preview.wav')
    parser.add_argument('--no-preview', action='store_true')
    parser.add_argument('--melodius',
                        default=r'C:\dev\veramusic\tools\melodius.exe')
    args = parser.parse_args()

    audio = decode(args.input)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(args.input),
                    '-c:a', 'pcm_s16le',
                    str(VERA / 'llvm/build/music_original.wav')], check=True)
    notes, amplitudes, drums = analyze(audio)
    fm, psg, frames, event_stats = build_events(notes, amplitudes, drums)
    zsm, last_event = encode_zsm(fm, psg, frames)
    args.zsm.parent.mkdir(parents=True, exist_ok=True)
    args.zsm.write_bytes(zsm)
    vzm, vzm_stats = zsm_to_vzm(zsm)
    ticks, fm_writes, psg_writes = check_stream(vzm, frames)
    if len(vzm) > MAX_STREAM:
        raise SystemExit(f'music.vzm is {len(vzm)} bytes, over the {MAX_STREAM} byte budget')
    if ticks != frames:
        print(f'warning: stream covers {ticks} ticks, analysis has {frames}',
              file=sys.stderr)

    args.vzm.parent.mkdir(parents=True, exist_ok=True)
    args.vzm.write_bytes(vzm)
    header = (
        '/* Generated by vera/tools/build_music_vzm.py - do not hand-edit. */\n'
        f'#define MUSIC_VZM_SIZE {len(vzm)}u\n'
        f'#define MUSIC_VZM_TICKS {ticks}u\n'
        f'#define MUSIC_VZM_FM_WRITES {fm_writes}u\n'
        f'#define MUSIC_VZM_PSG_WRITES {psg_writes}u\n'
    )
    args.header.write_text(header)

    report = {
        'source': str(args.input),
        'durationSeconds': round(frames / TICK_RATE, 3),
        'analysisFrames': frames,
        'lastEventFrame': last_event,
        'zsmBytes': len(zsm),
        'vzmBytes': len(vzm),
        'budgetBytes': MAX_STREAM,
        'ticks': ticks,
        'fmWrites': fm_writes,
        'psgWrites': psg_writes,
        'fmKept': vzm_stats['fmKept'],
        'psgKept': vzm_stats['psgKept'],
        **event_stats,
    }
    report_path = VERA / 'llvm/build/music_vzm_report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')

    if not args.no_preview and Path(args.melodius).is_file():
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([args.melodius, str(args.zsm), '--no-loop',
                        '--wav', str(args.preview)], check=True,
                       stdout=subprocess.DEVNULL)

    print(f'music.vzm {len(vzm)} bytes ({ticks} ticks, {fm_writes} FM writes, '
          f'{psg_writes} PSG writes)')


if __name__ == '__main__':
    main()
