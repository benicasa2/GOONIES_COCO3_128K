; Bank $3F hosts the sector buffer and game-over patch.
; Poll the WD17xx with the CPU at normal speed and IRQs masked.
        org $1B00
stream_boot
        lda #$6C
        sta INIT0
        lda #$3B               ; RTI for the controller INTRQ
        sta $FEFD
        lda #$3F
        sta MMU2
        lda #$29
        sta $FF40
        lda #$03
        sta $FF48
        jsr stream_wait
        lda #10
        jsr stream_group
        lda #$3A
        sta MMU3
        ldu #BG
        ldd ,u++
        ldx #$0D00
        jsr install_room5_byte
        ldd ,u++
        ldx #$1400
        jsr install_room5_byte
        ldd ,u++
        ldx #$0400
        jsr install_room5_byte
        ldx #$5900
stream_copy_game_over
        lda ,u+
        sta ,x+
        cmpx #$59FE
        blo stream_copy_game_over
        ifne AUDIO_DRIVER_TYPE
        lda #$3C
        sta MMU3
        ldx #$4000
        ldu #$6000
stream_copy_music
        ldd ,u++
        std ,x++
        cmpx #$5800
        blo stream_copy_music
        endc
        lda #9
        jsr stream_group
        lda #0
        jmp stream_group

stream_room
        ldb <room_bank
        subb #ROOM
        clra
stream_room_index
        subb #5
        blo stream_group
        inca
        bra stream_room_index

; A indexes the title/ending/initialization/room sector pairs.
stream_group
        pshs cc,a,b,x,y,u
        orcc #$50
        ldx #stream_sectors
        lsla
        ldd a,x
        sta stream_track
        stb stream_sector
        ldd #$5900
        std stream_cursor
        sta $FFD8
        lda #$29
        sta $FF40
        lda #$3F
        sta MMU2
stream_bank
        jsr stream_byte
        beq stream_complete
        sta MMU3
        jsr stream_byte
        ldy #BG
        tsta
        beq stream_raw
stream_token
        jsr stream_byte
        beq stream_bank
        tsta
        bmi stream_match
        tfr a,b
stream_literal
        jsr stream_byte
        sta ,y+
        decb
        bne stream_literal
        bra stream_token
stream_match
        anda #$7F
        adda #3
        pshs a
        jsr stream_byte
        pshs a
        jsr stream_byte
        tfr a,b
        puls a
        leau d,y
        puls b
stream_copy
        lda ,u+
        sta ,y+
        decb
        bne stream_copy
        bra stream_token
stream_raw
        jsr stream_byte
        sta ,y+
        cmpy #$8000
        blo stream_raw
        bra stream_bank
stream_complete
        clr $FF40
        sta $FFD9
        puls cc,a,b,x,y,u,pc

; Return the next byte in A. Preserve the decompressor registers.
stream_byte
        pshs x
        ldx stream_cursor
        cmpx #$5900
        bne stream_byte_ready
        pshs b,y,u
        lda stream_track
        cmpa $FF49
        beq stream_read
        sta $FF4B
        lda #$13
        sta $FF48
        jsr stream_wait
stream_read
        ldx #$5800
        lda stream_sector
        sta $FF4A
        lda #$80
        sta $FF48
        bsr stream_delay
stream_poll
        lda $FF48
        bita #2
        bne stream_drq
        bita #1
        bne stream_poll
        bita #$7C
        bne stream_error
        cmpx #$5900
        bne stream_error
        bra stream_read_ok
stream_drq
        ldb $FF4B
        stb ,x+
        bra stream_poll
stream_read_ok
        inc stream_sector
        lda stream_sector
        cmpa #19
        blo stream_sector_ready
        lda #1
        sta stream_sector
        inc stream_track
        lda stream_track
        cmpa #17
        bne stream_sector_ready
        inc stream_track
stream_sector_ready
        puls b,y,u
        ldx #$5800
stream_byte_ready
        lda ,x+
        stx stream_cursor
        tsta
        puls x,pc

stream_wait
        bsr stream_delay
stream_busy
        lda $FF48
        bita #1
        bne stream_busy
        rts
stream_delay
        ldb #16
stream_delay_loop
        decb
        bne stream_delay_loop
        rts

stream_error
        lda #$24
        sta $FF9A
        bra stream_error

stream_track rmb 1
stream_sector rmb 1
stream_cursor rmb 2
stream_sectors
        include "stream_sectors.inc"

