"""Arrange the Easy Lemon MIDI for the YM2151 FM daughterboard.

`media/music.ogg` is transcribed to `vera/assets/music.mid`; this script reads
that note list and lays it out on the eight YM2151 channels:

  * channel 7  - melody (top note of the sounding set)
  * channel 0  - bass (lowest note)
  * channel 1  - second bass voice, only for genuinely low notes
  * channels 2-6 - accompaniment, highest remaining notes first

Driving the FM part from the MIDI note list (instead of the earlier FFT
transcription of the OGG) keeps every pitch, note boundary and velocity exact,
so the arrangement no longer contains the over-detected harmonics and octave
jumps that made the first FM stream sound wrong.  The MIDI has no drum track,
so there is no invented percussion: the FM chip is the only sound source and
the PSG-only `MUSIC.PSG` fallback keeps its own separate arrangement.

Outputs:
  generated/music.vzm        the stream shipped as MUSIC.VZM
  generated/music.zsm        the same stream with a ZSM header (for melodius)
  generated/music_vzm.h      size / tick count macros
  llvm/build/music_vzm_report.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERA = HERE.parent

TICK_RATE = 60
MAX_STREAM = 63488          # music_init() hard gate (248 x 256-byte pages)
FM_CHANNELS = 8
BASS_SPLIT = 52             # below this the second bass voice may take a note
BASS_CHANNELS = (0, 1)
ACCOMP_CHANNELS = (2, 3, 4, 5, 6)
MELODY_CHANNEL = 7
CARRIER_SLOT = 2            # CON=4: the audible carriers live in slot 2 and 3

# ---------------------------------------------------------------------------
# YM2151 key code
# ---------------------------------------------------------------------------
# The OPM key code is octave << 4 | note and the note field is "gappy": the
# chip subtracts (note >> 2), so 12 semitones map onto 16 codes with 3/4,
# 7/8 and 11/12 shared.  Measured with melodius on the YM2151 core: $3E plays
# C4 and $4A plays A4 (llvm/build/fm_kc_table.py), i.e. semitone s uses
# INVERSE[s-1] and C sits on code 14 of the block below.
KC_INVERSE = (0, 1, 2, 3, 5, 6, 7, 9, 10, 11, 13)


def kc_for_midi(midi):
    midi = int(midi)
    semitone = midi % 12
    if semitone == 0:
        octave = midi // 12 - 2
        note = 14
    else:
        octave = midi // 12 - 1
        note = KC_INVERSE[semitone - 1]
    if not 0 <= octave <= 7:
        raise ValueError(f'note {midi} is outside the YM2151 KC range')
    return (octave << 4) | note


# ---------------------------------------------------------------------------
# YM2151 patches
# ---------------------------------------------------------------------------
# Operator register groups are 0x40 (DT1/MULT), 0x60 (TL), 0x80 (KSR/AR),
# 0xA0 (AM/DR), 0xC0 (DT2/SR), 0xE0 (SL/RR); the group index is the operator
# slot, the low three bits of every register are the channel.  Channel
# register 0x20 holds feedback << 3 | algorithm.  With CON=4 the wiring is
# slot 0 -> slot 2 and slot 1 -> slot 3, and slots 2/3 are the carriers that
# reach the output, so the per-note total level goes to slot 2 (TL 0x70+ch).
def _op(mult, tl, ar, dr, sr, sl, rr, dt1=0, dt2=0, ks=0, ams=0):
    return {
        'dtmul': (dt1 << 4) | mult,
        'tl': tl,
        'ksar': (ks << 6) | ar,
        'amsdr': (ams << 7) | dr,
        'dt2sr': (dt2 << 6) | sr,
        'slrr': (sl << 4) | rr,
    }


PATCHES = {
    # Rounded bass: one 1:1 FM pair, the second pair muted at the carrier.
    'bass': {
        'alg': 4,
        'ops': (
            _op(mult=1, tl=0x18, ar=31, dr=12, sr=0, sl=7, rr=9),    # M1
            _op(mult=1, tl=0x7F, ar=31, dr=12, sr=0, sl=7, rr=9),    # M2 (off)
            _op(mult=1, tl=0x00, ar=31, dr=5, sr=0, sl=4, rr=8),     # C1 carrier
            _op(mult=1, tl=0x7F, ar=31, dr=12, sr=0, sl=7, rr=9),    # C2 (off)
        ),
    },
    # Struck tine: 1:1 pair with a fast-decaying modulation index, plus a
    # quiet 3:1 pair for the attack sparkle.
    'tine': {
        'alg': 4,
        'ops': (
            _op(mult=1, tl=0x10, ar=31, dr=16, sr=0, sl=9, rr=10),   # M1
            _op(mult=3, tl=0x20, ar=31, dr=20, sr=0, sl=12, rr=10),  # M2
            _op(mult=1, tl=0x00, ar=31, dr=12, sr=0, sl=7, rr=12),   # C1 carrier
            _op(mult=1, tl=0x20, ar=31, dr=14, sr=0, sl=10, rr=12),  # C2 (quiet)
        ),
    },
    # Melody lead: brighter and a little slower to decay than the tine.
    'lead': {
        'alg': 4,
        'ops': (
            _op(mult=1, tl=0x0A, ar=31, dr=18, sr=0, sl=10, rr=12),  # M1
            _op(mult=2, tl=0x1C, ar=31, dr=22, sr=0, sl=12, rr=12),  # M2
            _op(mult=1, tl=0x00, ar=31, dr=13, sr=0, sl=8, rr=12),   # C1 carrier
            _op(mult=1, tl=0x1C, ar=31, dr=15, sr=0, sl=10, rr=12),  # C2 (quiet)
        ),
    },
}

ROLE = ('bass', 'bass', 'tine', 'tine', 'tine', 'tine', 'tine', 'lead')


def patch_writes(prefix):
    """Yield (register without channel, value) programming one channel."""
    yield 0x20, 0xC0 | prefix['alg']       # output enable bits | algorithm
    for slot, op in enumerate(prefix['ops']):
        yield 0x40 + slot * 8, op['dtmul']
        yield 0x60 + slot * 8, op['tl']
        yield 0x80 + slot * 8, op['ksar']
        yield 0xA0 + slot * 8, op['amsdr']
        yield 0xC0 + slot * 8, op['dt2sr']
        yield 0xE0 + slot * 8, op['slrr']


def tl_for_velocity(velocity, role):
    """Map a MIDI velocity onto a carrier total level (0 = loudest).

    The bass keeps a much smaller attenuation span: the transcription puts a
    third of its notes an octave or two below the melody, and those low notes
    have to stay audible against the tine arpeggios.
    """
    velocity = max(0, min(127, int(velocity)))
    base, span = {
        'bass': (0x00, 0x0A),
        'tine': (0x02, 0x14),
        'lead': (0x00, 0x14),
    }[role]
    return max(0, min(0x30, base + round((127 - velocity) / 127 * span)))


# ---------------------------------------------------------------------------
# Standard MIDI file reader
# ---------------------------------------------------------------------------
def _varint(data, pos):
    value = 0
    while True:
        if pos >= len(data):
            raise ValueError('truncated variable-length value')
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, pos


def read_smf(path):
    """Return (notes, duration) with notes as absolute seconds."""
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b'MThd':
        raise ValueError(f'{path}: not a standard MIDI file')
    header_len = int.from_bytes(data[4:8], 'big')
    division = int.from_bytes(data[12:14], 'big')
    if division & 0x8000:
        raise ValueError(f'{path}: SMPTE timing is not supported')
    track_count = int.from_bytes(data[10:12], 'big')

    tempos = []          # (tick, microseconds per quarter note)
    events = []          # (tick, track, order, status, d1, d2)
    pos = 8 + header_len
    for track in range(track_count):
        if data[pos:pos + 4] != b'MTrk':
            raise ValueError(f'{path}: track {track} is not an MTrk chunk')
        size = int.from_bytes(data[pos + 4:pos + 8], 'big')
        ptr = pos + 8
        end = ptr + size
        tick = 0
        order = 0
        running = None
        while ptr < end:
            delta, ptr = _varint(data, ptr)
            tick += delta
            first = data[ptr]
            if first & 0x80:
                status = first
                ptr += 1
                if status < 0xF0:
                    running = status
            elif running is not None:
                status = running
            else:
                raise ValueError(f'{path}: data byte without running status')
            if status == 0xFF:
                meta = data[ptr]
                ptr += 1
                length, ptr = _varint(data, ptr)
                payload = data[ptr:ptr + length]
                ptr += length
                if meta == 0x51 and len(payload) == 3:
                    tempos.append((tick, int.from_bytes(payload, 'big')))
            elif status in (0xF0, 0xF7):
                length, ptr = _varint(data, ptr)
                ptr += length
            elif status >= 0xF0:
                raise ValueError(f'{path}: unsupported system event {status:02X}')
            else:
                kind = status & 0xF0
                if kind in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    d1 = data[ptr]
                    d2 = data[ptr + 1]
                    ptr += 2
                elif kind in (0xC0, 0xD0):
                    d1 = data[ptr]
                    d2 = 0
                    ptr += 1
                else:
                    raise ValueError(f'{path}: unsupported status {status:02X}')
                events.append((tick, track, order, status, d1, d2))
                order += 1
        pos = end

    tempos.sort()
    if not tempos:
        tempos = [(0, 500000)]

    def seconds(tick):
        total = 0.0
        last = 0
        tempo = tempos[0][1]
        for change_tick, change_tempo in tempos:
            if change_tick >= tick:
                break
            total += (change_tick - last) * tempo / 1e6 / division
            last = change_tick
            tempo = change_tempo
        total += (tick - last) * tempo / 1e6 / division
        return total

    notes = []
    started = {}
    for tick, _track, _order, status, d1, d2 in sorted(events):
        kind = status & 0xF0
        if kind == 0x90 and d2 > 0:
            started.setdefault((status & 0x0F, d1), []).append((tick, d2))
        elif kind == 0x80 or kind == 0x90:
            queue = started.get((status & 0x0F, d1))
            if queue:
                start, velocity = queue.pop(0)
                notes.append({
                    'start': seconds(start),
                    'end': seconds(tick),
                    'pitch': d1,
                    'velocity': velocity,
                })
    duration = seconds(max((e[0] for e in events), default=0))
    return notes, duration


# ---------------------------------------------------------------------------
# 60 Hz arrangement
# ---------------------------------------------------------------------------
def quantise_notes(notes, frames):
    out = []
    for note in notes:
        start = int(round(note['start'] * TICK_RATE))
        end = int(round(note['end'] * TICK_RATE))
        if start < 0 or start >= frames:
            continue
        end = min(frames, max(start + 2, end))
        out.append({
            'start': start,
            'end': end,
            'pitch': note['pitch'],
            'velocity': note['velocity'],
        })
    out.sort(key=lambda note: (note['start'], note['pitch']))
    return out


def _steal_channel(slots, candidates):
    """Pick the channel whose note ends soonest (ties: started earliest)."""
    best = candidates[0]
    for channel in candidates[1:]:
        note = slots[channel]
        other = slots[best]
        if other is None:
            break
        if note is None:
            best = channel
        elif (note['end'], -note['start']) < (other['end'], -other['start']):
            best = channel
    return best


def build_events(notes, frames):
    """Lay the note list out on the FM channels; return (fm, psg, stats).

    A note keeps its channel from key-on to key-off, so a sustained note is never
    re-articulated when the melody or bass line changes.  A new note takes the
    first free channel of its register group (bass below BASS_SPLIT, everything
    else among the tine/lead channels); when the group is full the channel whose
    note ends soonest is stolen.
    """
    fm = [[] for _ in range(frames)]
    psg = [[] for _ in range(frames)]

    for channel in range(FM_CHANNELS):
        patch = PATCHES[ROLE[channel]]
        for reg, value in patch_writes(patch):
            fm[0].append((reg + channel, value))

    starts = [[] for _ in range(frames + 1)]
    for note in notes:
        starts[note['start']].append(note)

    slots = [None] * FM_CHANNELS
    note_starts = note_stops = steals = 0

    for frame in range(frames):
        for channel in range(FM_CHANNELS):
            note = slots[channel]
            if note is not None and note['end'] <= frame:
                fm[frame].append((0x08, channel))
                slots[channel] = None
                note_stops += 1

        for note in sorted(starts[frame], key=lambda item: -item['velocity']):
            if note['pitch'] < BASS_SPLIT:
                candidates = list(BASS_CHANNELS)
            else:
                sounding = [slots[channel]['pitch'] for channel in ACCOMP_CHANNELS + (MELODY_CHANNEL,)
                            if slots[channel] is not None]
                if not sounding or note['pitch'] >= max(sounding):
                    candidates = [MELODY_CHANNEL] + list(ACCOMP_CHANNELS)
                else:
                    candidates = list(ACCOMP_CHANNELS) + [MELODY_CHANNEL]
            free = [channel for channel in candidates if slots[channel] is None]
            if free:
                channel = free[0]
            else:
                channel = _steal_channel(slots, candidates)
                fm[frame].append((0x08, channel))
                slots[channel] = None
                note_stops += 1
                steals += 1
            role = ROLE[channel]
            fm[frame].append((0x28 + channel, kc_for_midi(note['pitch'])))
            fm[frame].append((0x70 + channel, tl_for_velocity(note['velocity'], role)))
            fm[frame].append((0x08, 0x78 | channel))
            slots[channel] = note
            note_starts += 1

    stats = {
        'frames': frames,
        'noteStarts': note_starts,
        'noteStops': note_stops,
        'voiceSteals': steals,
    }
    return fm, psg, stats


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
                        default=VERA / 'assets/music.mid')
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

    notes, duration = read_smf(args.input)
    frames = max(int(round(duration * TICK_RATE)), 2)
    notes = quantise_notes(notes, frames)
    if not notes:
        raise SystemExit(f'{args.input}: no playable notes')
    frames = max(frames, max(note['end'] for note in notes) + 1)

    fm, psg, event_stats = build_events(notes, frames)
    zsm, last_event = encode_zsm(fm, psg, frames)
    args.zsm.parent.mkdir(parents=True, exist_ok=True)
    args.zsm.write_bytes(zsm)
    vzm, vzm_stats = zsm_to_vzm(zsm)
    ticks, fm_writes, psg_writes = check_stream(vzm, frames)
    if len(vzm) > MAX_STREAM:
        raise SystemExit(f'music.vzm is {len(vzm)} bytes, over the {MAX_STREAM} byte budget')
    if ticks != frames:
        print(f'warning: stream covers {ticks} ticks, arrangement has {frames}',
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
        'notes': len(notes),
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
        subprocess.run([str(args.melodius), str(args.zsm), '--no-loop',
                        '--wav', str(args.preview)], check=True,
                       stdout=subprocess.DEVNULL)

    print(f'music.vzm {len(vzm)} bytes ({ticks} ticks, {fm_writes} FM writes, '
          f'{psg_writes} PSG writes, {len(notes)} notes) from {args.input.name}')


if __name__ == '__main__':
    main()
