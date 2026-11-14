"""Build the 128 KiB disk-streaming port from the same extracted Apple II assets."""
import argparse
from pathlib import Path
import subprocess

from build import (GRANULE, SECTOR, encode_bank, make_disk,
                   room6_segment, room8_segment, runtime_segment, split_room5_code)
from prepare import asm_bytes


def streaming_source(source, runtime):
    source = source.replace('FB0     equ     $08', 'FB0     equ     $30')
    source = source.replace('FB1     equ     $0C', 'FB1     equ     FB0')
    source = source.replace('        jsr     require_512\n        ifne PRELOAD_ALL\n        jsr     install_room5\n        jsr     install_room6\n        endc\n', '')
    source = source.replace('        clra\n        tfr     a,dp\n        ldx     #ticks',
                            '        clra\n        tfr     a,dp\n        jsr     stream_boot\n        ldx     #ticks')
    source = source.replace('        jmp     require_512', '        jmp     start')
    first = source.index('\nrequire_512\n')
    last = source.index('; Load consecutive LZ', first)
    source = source[:first] + '\n' + source[last:]
    source = source.replace('copy_background\n        ldb     <room_bank', 'copy_background\n        ldb     #$34')
    source = source.replace('        lda     <room_bank\n        adda    #4\n        pshs    a', '        lda     #$38\n        pshs    a')
    source = source.replace('map_terrain\n        lda     <room_bank\n        adda    #4', 'map_terrain\n        lda     #$3A')
    source = source.replace('adda    <room_bank', 'adda    #$34').replace('adda #ROOM7\n', 'adda #$34\n')
    source = source.replace('sta     <room_bank\n        jsr     reset_room', 'sta     <room_bank\n        jsr     stream_room\n        jsr     reset_room')
    source = source.replace('lda     #ROOM+4\n', 'lda     #$3B\n')
    source = source.replace('lda     #ROOM+19\n', 'lda     #$3C\n')
    source = source.replace('lda     #ROOM+24\n', 'lda     #$3D\n')
    source = source.replace('lda     #ROOM+14\n', 'lda     #$3E\n')
    source = source.replace('ROOM4_GRAPH equ ROOM+39', 'ROOM4_GRAPH equ $3E')
    source = source.replace('lda     #ROOM+29\n', 'lda     #$3C\n').replace(
        '        adda    #5\nroom4_state_bank', '        inca\nroom4_state_bank')
    source = source.replace('ROOM5_ART equ $3A', 'ROOM5_ART equ $3C')
    source = source.replace('ROOM7_ART equ $3F', 'ROOM7_ART equ $3E')
    source = source.replace('ROOM8_ART equ $3D', 'ROOM8_ART equ $3E')
    source = source.replace('NATIVE_BANK equ $3E', 'NATIVE_BANK equ $3D')
    source = source.replace('MOTION2 equ $3B', 'MOTION2 equ $3C')
    source = source.replace('        lda     ,x\n        ldb     #5\n        mul\n        addb    #ROOM+23\n        stb     MMU3\n        clra',
                            '        lda     #$3D\n        sta     MMU3\n        clra')
    source = source.replace('        addd    #$7800\n        tfr     d,u\n', '''        addd    #$6000
        pshs    b
        ldb     ,x
        lslb
        lslb
        lslb
        pshs    b
        adda    ,s+
        puls    b
        tfr     d,u
''')
    # Move the game-over patch to reserved RAM accessible using aperture 3.
    source = source.replace('lda     #$3E\n        sta     MMU3\nlife_game_over equ $7F02',
                            'lda     #$3F\n        sta     MMU3\nlife_game_over equ $7900')
    first = source.index('\nrestore_title\n')
    last = source.index('        endc', first)
    source = source[:first] + '\nrestore_title\n        lda #9\n        jmp stream_group\n' + source[last:]
    source = source.replace('exit_win\n        inc', 'exit_win\n        lda #8\n        jsr stream_group\n        inc')
    source = source.replace('        lda     #4\n        sta     <ending_bank', '        lda     #$34\n        sta     <ending_bank')
    first = source.index('\nending_step\n')
    last = source.index('\nending_play\n', first)
    source = source[:first] + '\nending_step' + source[last:]
    source = source.replace('        cmpa    #8\n        bne     ending_next_bank\n        lda     #$3C', '        cmpa    #$38\n        bne     ending_next_bank\n        lda     #$3A')
    source = source.replace('        suba    #2\n        sta     <ending_hold', '        deca\n        sta     <ending_hold')
    first = source.index('\nending_patched\n')
    last = source.index('        stu     <ending_ptr', first)
    source = source[:first] + '\nending_patched\n' + source[last:]
    # No disk staging or 512 KiB initialization routines are used here.
    first = source.index('\ninstall_room5\n')
    last = source.index('\ninstall_room5_byte\n', first)
    source = source[:first] + source[last:]
    first = source.index('        org $1D00\ninstall_room6')
    last = source.index('        endc', first)
    source = source[:first] + runtime + '\n' + source[last:]
    # Single-buffer redraws happen once per room transition.
    source = source.replace('lda     #2\n        sta     <redraw', 'lda     #1\n        sta     <redraw')
    first = source.index('        ldx     #$7800', source.index('ssc_music_restart\n'))
    last = source.index('ssc_music_event\n', source.index('ssc_music_next\n', first))
    source = source[:first] + """        ldx     #$6000
        clr     <music_note
        clr     <music_note+1
        clr     <music_note+2
ssc_music_map
        lda     #$3F
        sta     MMU3
        lda     ,x+
        beq     ssc_music_restart
""" + source[last:]
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('assets', type=Path)
    parser.add_argument('flat', type=Path, help='flat.asm generated by build.py')
    parser.add_argument('output', type=Path)
    parser.add_argument('--ssc', action='store_true', help='Use the Tandy Speech and Sound Cartridge')
    parser.add_argument('--replay', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--test-room', type=int, choices=range(1, 9), default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    assets = args.assets

    def asset(name):
        return (assets / name).read_bytes()

    def bank(data):
        if len(data) > 8192:
            raise ValueError('Asset exceeds one bank')
        return bytes(data).ljust(8192, b'\0')

    def banks(name, base):
        pixels = asset(name)
        if len(pixels) != 320 * 192 // 2:
            raise ValueError(f'Incorrect bitmap size for {name}')
        data = pixels.ljust(32768, b'\0')
        return [(base + i, data[i * 8192:(i + 1) * 8192]) for i in range(4)]

    runtime = (Path(__file__).resolve().parent.parent / 'src/stream128.inc').read_text()
    source = streaming_source(args.flat.read_text(encoding='ascii'), runtime)
    variant = 'GOON-128-SSC' if args.ssc else 'GOON-128-DAC'
    if args.replay:
        replay = bytes.fromhex(args.replay.read_text())
        source = source.replace('        andcc   #$AF\n', '        andcc   #$AF\n        bra title_start\n', 1)
        first, last = source.split('\nmain_loop\n', 1)
        source = first + '\nmain_loop\n' + last.replace('jsr     read_keys', 'jsr     replay_input', 1)
        source = source.replace('        lda     #ROOM\n        sta     <room_bank', f'        lda     #ROOM+{5*(args.test_room-1)}\n        sta     <room_bank', 1)
        source = source.replace('        lda #0\n        jmp stream_group', f'        lda #{args.test_room-1}\n        jmp stream_group', 1)
        if len(replay) > 0x4F0:
            parser.error('Replay exceeds its reserved space')
        source = source.replace('        lda #9\n        jsr stream_group\n', """        ldx #$5A00
        ldu #$7200
        lda #$3A
        sta MMU3
replay_copy
        ldd ,u++
        std ,x++
        cmpx #$5EF0
        blo replay_copy
        lda #9
        jsr stream_group
""", 1)
        replay_code = """        org $1CA0
replay_input
        tst replay_remaining
        bne replay_hold
        lda MMU2
        pshs a
        lda #$3F
        sta MMU2
        ldx replay_pos
        lda ,x+
        beq replay_done
        sta replay_remaining
        lda ,x+
        sta <keys
        stx replay_pos
        puls a
        sta MMU2
replay_hold
        dec replay_remaining
        rts
replay_done
        puls a
        sta MMU2
        clr <keys
        rts
replay_remaining fcb 0
replay_pos fdb $5A00
"""
        source = source.replace('        end entry', replay_code + '        end entry')
    table = asm_bytes('stream_sector_table', bytes(22))
    for _ in range(2):
        (out / 'flat128.asm').write_text(source.replace('        include "stream_sectors.inc"', table), encoding='ascii')
        subprocess.run(['lwasm', '--6809', '--decb', '-D', 'PRELOAD_ALL=1',
                        '-D', f'AUDIO_DRIVER_TYPE={int(args.ssc)}', f'--map={variant}.map',
                        '-o', 'stream.bin', 'flat128.asm'], cwd=out, check=True)
        engine = (out / 'stream.bin').read_bytes()
        native = bytearray(bank(asset('native8.bin')))
        native_code = runtime_segment(engine, 0x7500, 0x700)[2:]
        native[0x1500:0x1500 + len(native_code)] = native_code
        overlays = room6_segment(engine) + room8_segment(engine)
        engine, code5 = split_room5_code(engine)
        game_over = asset('scene3-collision.bin')[0x1F02:]
        if len(game_over) != 0xFE:
            raise ValueError('Game-over patch layout changed')
        overlays = code5 + overlays + game_over
        if len(overlays) > 0x1200:
            raise ValueError('Boot assets exceed one bank')
        if args.replay:
            overlays = overlays.ljust(0x1200, b'\0') + replay
        common = asset('scene1-collision.bin')
        particles = asset('room4-particles.bin')
        rng = bytes(0x1600) + particles
        room4_graphics = asset('scene8-collision.bin').ljust(0x1600, b'\0') + particles
        eggs = b''.join(asset(f'room5-eggs-{i}.bin').ljust(2048, b'\0') for i in range(5, 9))
        extra = [
            [],
            [(0x3C, asset('room2-motion.bin'))],
            [(0x3C, asset('scene4-collision.bin')), (0x3D, asset('scene5-collision.bin'))],
            [(0x3C, asset('scene6-collision.bin')), (0x3D, asset('scene7-collision.bin')), (0x3E, room4_graphics)],
            [(0x3C, asset('room5.bin')), (0x3D, eggs), (0x3E, rng)],
            [(0x3C, asset('room6.bin')), (0x3E, rng)],
            [(0x3D, native), (0x3E, asset('room7.bin'))],
            [(0x3C, asset('room6.bin')), (0x3D, native), (0x3E, asset('room8.bin'))],
        ]
        ending = banks('ending.4bpp', 0x30)
        ending += [(0x34 + i, asset(f'ending-{i}.bin')) for i in range(4)]
        ending.append((0x3A, asset('scene4-collision.bin')))
        groups = [banks(f'scene{i}.4bpp', 0x34) +
                  [(0x3A, asset(f'scene{i}-collision.bin'))] + extra[i-1]
                  for i in range(1, 9)]
        groups += [ending, banks('title.4bpp', 0x30), [(0x3A, overlays), (0x3B, common)]]
        if args.ssc:
            theme = (Path(__file__).resolve().parents[1] / 'assets/ssc-theme.bin').read_bytes()
            if not theme or len(theme) > 0x1800 or theme[-1] != 0:
                raise ValueError('SSC theme exceeds the reserved bank space or lacks a terminator')
            groups[10].append((0x3C, theme))
        files = [('START', 'BAS', 0, 255, b'10 CLEAR 200,&H16FF:LOADM"ENGINE":EXEC&H2000\r'),
                 ('ENGINE', 'BIN', 2, 0, engine)]
        first_sector = sum((len(data) + GRANULE-1) // GRANULE for _, _, _, _, data in files) * 9
        packed = bytearray()
        positions = bytearray(22)
        for index in (10, 9, *range(9)):
            group = groups[index]
            track, sector = divmod(first_sector + len(packed) // SECTOR, 18)
            positions[2*index:2*index+2] = bytes((track + (track >= 17), sector + 1))
            for address, data in group:
                raw = bank(data)
                encoded = encode_bank(raw)
                use_lz = len(encoded) < len(raw)
                packed.extend((address, use_lz))
                packed.extend(encoded if use_lz else raw)
            packed.append(0)
            packed.extend(bytes(-len(packed) % SECTOR))
        table = asm_bytes('stream_sector_table', positions)
    files.append(('ROOMDATA', 'BIN', 2, 0, packed))
    (out / f'{variant}.DSK').write_bytes(make_disk(files))


if __name__ == '__main__':
    main()



