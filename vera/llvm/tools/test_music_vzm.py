"""Reference decoder + model run for MUSIC.VZM (YM2151 + PSG percussion).

Instrumented 65C02 model only: not a listening test and not real hardware.

    python -u vera/llvm/tools/test_music_vzm.py [ticks]

With an optional tick count the stream is only compared that far (quick
iteration while editing the player); the default compares the whole song.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_mos as m

VERA = m.VERA
BUILD = m.LLVM / 'build'
BASELINE = bytearray(64)
BASELINE[3::4] = bytes([128]) * 16


def fm_silence_writes():
    return [(0x08, ch) for ch in range(8)] + [(reg, 0) for reg in range(0x20, 0x100)]


def decode(data, ticks):
    """Mirror of music_tick()'s VZM state machine, independent of the C code."""
    psg = bytearray(BASELINE)
    out = []
    loop_ticks = []
    i = 0
    pending = 0
    for tick in range(ticks):
        # The player clears both chips before the first group and on every loop.
        fm = list(fm_silence_writes()) if tick == 0 else []
        if pending:
            pending -= 1
            out.append((bytes(psg), fm))
            continue
        while True:
            assert i < len(data), 'stream ended without $FF'
            command = data[i]
            i += 1
            if command < 0x80:
                pending = command
                break
            if command < 0xC0:
                psg[command & 0x3F] = data[i]
                i += 1
            elif command < 0xE0:
                count = (command & 0x1F) + 1
                for _ in range(count):
                    fm.append((data[i], data[i + 1]))
                    i += 2
            elif command == 0xFF:
                loop_ticks.append(tick)
                psg = bytearray(BASELINE)
                fm.extend(fm_silence_writes())
                i = 0
            # $E0-$FE: padding, no tick consumed
        out.append((bytes(psg), fm))
    return out, loop_ticks


def probe_bytes():
    text = (m.LLVM / 'src/fm_probe.h').read_text()
    blocks = re.findall(r'fm_probe\[\]\s*=\s*\{(.*?)\};', text, re.S)
    assert len(blocks) == 2, 'expected slot 2 and slot 4 probes'
    return [bytes(int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{2})', b)) for b in blocks]


def call(machine, name, arg=0):
    pc, sp = machine.cpu.pc, machine.cpu.sp
    machine.cpu.a = arg
    machine.cpu.stPushWord(0x02FE)
    machine.cpu.pc = machine.sym[name]
    machine.until(lambda: machine.cpu.pc == 0x02FF)
    assert machine.cpu.sp == sp and not machine.mem.aux_read and not machine.mem.aux_write
    machine.cpu.pc = pc


def get(machine, name, size=1):
    base = machine.sym[name]
    return int.from_bytes(machine.mem.ram[base:base + size], 'little')


def put(machine, name, value, size=1):
    base = machine.sym[name]
    machine.mem.ram[base:base + size] = int(value).to_bytes(size, 'little')


def check_probes():
    probes = probe_bytes()
    for slot in (2, 4):
        for present, want in ((True, 1), (False, 0)):
            mem = m.Memory(slot)
            mem.fm_present = present
            mem.ram[0x0300:0x0300 + len(probes[0])] = probes[0 if slot == 2 else 1]
            cpu = m.MPU(memory=mem, pc=0x0300)
            cpu.stPushWord(0x02FE)
            while cpu.pc != 0x02FF:
                cpu.step()
            assert mem.ram[0x02FF] == want, (slot, present, mem.ram[0x02FF])
        print(f'PASS slot {slot}: YM2151 BUSY probe detects chip / rejects open bus', flush=True)


def load_player(slot, data, code, sym):
    machine = m.Machine(slot)
    machine.mem.ram[0x3000:0x3000 + len(code)] = code
    machine.sym = sym
    machine.mem.fm_present = True
    machine.mem.ram[0x3F2] = 1     # Music ON
    call(machine, 'music_aux_init')
    # 256-byte logical pages start at page 8; the player reads them from Aux RAM.
    pages = (len(data) + 255) >> 8
    for page in range(8, 8 + pages):
        chunk = data[(page - 8) * 256:(page - 7) * 256]
        machine.mem.aux[page * 256:page * 256 + len(chunk)] = chunk
    put(machine, 'music_size', len(data), 4)
    put(machine, 'music_position', 0, 2)
    put(machine, 'music_ready', 1)
    put(machine, 'music_fm', 1)
    put(machine, 'music_on', 0)
    put(machine, 'music_delay', 0)
    put(machine, 'cache_page', 255)
    assert machine.mem.ram[0x300:0x312] == machine.mem.aux[0x300:0x312]
    return machine


def check_init_selection(slot):
    """music_init() must prefer MUSIC.VZM when the chip answers, else PSG."""
    name = 'vzm_player4' if slot == 4 else 'vzm_player'
    code = (BUILD / f'{name}.bin').read_bytes()
    if int.from_bytes(code[:2], 'little') == 0x3000:
        code = code[4:]
    sym = m.symbols(BUILD / f'{name}.bin.elf')
    pattern = lambda length: bytes((i // 512) * 7 + (i % 512) & 0xFF for i in range(length))
    for fm, vzm_ok, want_fm, want_file in ((True, True, 1, b'MUSIC.VZM'),
                                           (True, False, 0, b'MUSIC.PSG'),
                                           (False, True, 0, b'MUSIC.PSG')):
        machine = m.Machine(slot)
        machine.mem.ram[0x3000:0x3000 + len(code)] = code
        machine.sym = sym
        machine.mem.fm_present = fm
        machine.mem.ram[sym['vzm_stub_vzm_ok']] = 1 if vzm_ok else 0
        machine.mem.ram[sym['vzm_stub_psg_size']] = 8       # 1 sector, aux RAM only
        call(machine, 'music_init')
        assert get(machine, 'music_fm') == want_fm, (slot, fm, vzm_ok)
        assert bytes(machine.mem.ram[sym['vzm_stub_name']:sym['vzm_stub_name'] + 9]) == want_file
        assert get(machine, 'music_ready') == 1
        want_size = 22974 if want_fm else 8
        assert get(machine, 'music_size', 4) == want_size
        assert machine.mem.aux[0x800:0x800 + want_size] == pattern(want_size), 'preload must match the stream'
    print(f'PASS slot {slot}: music_init prefers MUSIC.VZM with FM, falls back to MUSIC.PSG', flush=True)


def check_intro_fm_line():
    """The boot intro must report the same detection result the player uses."""
    for slot in (2, 4):
        name = 'intro4' if slot == 4 else 'intro'
        code = (BUILD / f'{name}.bin').read_bytes()
        if int.from_bytes(code[:2], 'little') == 0x3000:
            code = code[4:]
        for present, want in ((True, 'FM: YM2151 DETECTED (OPM)'),
                              (False, 'FM: NONE, PSG MUSIC ONLY')):
            machine = m.Machine(slot)
            machine.mem.ram[0x3000:0x3000 + len(code)] = code
            machine.mem.ram[0x3EC] = slot
            machine.mem.ram[0x3F0] = 0xFF
            machine.mem.fm_present = present
            machine.cpu.pc = 0x3000
            for _ in range(200000):
                if machine.mem.ram[0x600] == 0xC6:      # 'F' of the FM row
                    for _ in range(4000):               # let the row finish
                        machine.step()
                    break
                machine.step()
            text = bytes(machine.mem.ram[0x600:0x628])
            want_bytes = bytes(ord(c) | 0x80 for c in want)
            assert text[:len(want_bytes)] == want_bytes, (slot, present, text[:32], want)
        print(f'PASS slot {slot}: intro reports FM detection result', flush=True)


def main():
    report = json.loads((BUILD / 'music_vzm_report.json').read_text())
    data = (VERA / 'generated/music.vzm').read_bytes()
    assert len(data) == report['vzmBytes']
    frames = report['ticks']
    expected, loops = decode(data, frames + 1)
    assert len(expected) == frames + 1 and loops == [frames], (loops, frames)
    assert expected[frames][1][-1][0] == 0xFF, 'loop must re-silence the FM chip'

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    subset = expected if limit is None else expected[:limit]

    check_probes()
    check_intro_fm_line()
    for slot in (2, 4):
        check_init_selection(slot)
        name = 'vzm_player4' if slot == 4 else 'vzm_player'
        code = (BUILD / f'{name}.bin').read_bytes()
        if int.from_bytes(code[:2], 'little') == 0x3000:
            code = code[4:]
        sym = m.symbols(BUILD / f'{name}.bin.elf')
        machine = load_player(slot, data, code, sym)
        machine.mem.addr[:] = [0x12345, 0x18010]
        machine.mem.inc[:] = [320, 40]
        machine.mem.ctrl = 3
        saved = (machine.mem.addr[:], machine.mem.inc[:], machine.mem.ctrl)
        machine.mem.writes.clear()
        cycles = []
        for tick, (psg, fm) in enumerate(subset):
            machine.mem.fm_writes.clear()
            before = machine.cpu.processorCycles
            call(machine, 'music_tick')
            cycles.append(machine.cpu.processorCycles - before)
            assert machine.mem.vram[0x1F9C0:0x1FA00] == psg, (slot, tick, 'psg image')
            assert [(r, v) for _, r, v in machine.mem.fm_writes] == fm, (slot, tick, 'fm stream')
            assert (machine.mem.addr, machine.mem.inc, machine.mem.ctrl) == saved, (slot, tick, 'graphics port')
        assert all(0x1F9C0 <= a < 0x1FA00 for a in machine.mem.writes), 'music touched graphics'
        if limit is None:
            assert not any(machine.mem.vram[0x1F9C2:0x1FA00:4]), 'final image must be silent'

            # Stop and OFF must silence both chips without restarting the stream.
            machine.mem.fm_writes.clear()
            call(machine, 'music_stop')
            assert machine.mem.vram[0x1F9C0:0x1FA00] == bytes(BASELINE)
            assert [(r, v) for _, r, v in machine.mem.fm_writes] == fm_silence_writes(), 'stop must key-off and zero YM2151'
            machine.mem.ram[0x3F2] = 0
            machine.mem.fm_writes.clear()
            machine.mem.writes.clear()
            call(machine, 'music_tick')
            assert not machine.mem.fm_writes and not machine.mem.writes
        print(f'PASS slot {slot}: {len(subset)} ticks byte-exact (PSG image and FM write order)'
              + (f', loop at tick {frames}, stop/OFF silence' if limit is None else '')
              + f'; cycles mean={np.mean(cycles):.0f} max={max(cycles)}', flush=True)


if __name__ == '__main__':
    main()
