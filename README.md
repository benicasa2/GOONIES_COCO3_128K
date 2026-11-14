# The Goonies — CoCo 3 com 128 KiB

- **GOON-128-DAC.DSK** usa o áudio interno do CoCo 3.
- **GOON-128-SSC.DSK** usa o Tandy Speech/Sound Cartridge e a trilha transcrita de GOONIES-3VOZES.mp3.

Monte o disco na unidade 0 de um CoCo 3 NTSC com controladora compatível com a Tandy RS-DOS e Disk BASIC. Digite `PCLEAR 1` e `RUN"START"`. No Windows, `Jogar-Goonies-128.cmd` abre a edição DAC no XRoar em 128 KiB e RGB. Para usar outro local de instalação do XRoar, defina a variável `XROAR_EXE`.

Pressione Espaço na apresentação. Use as setas para mover, Espaço para saltar e G para trocar de personagem. Mantenha o disco montado durante o jogo. As fases e a animação final são carregadas sob demanda. A imagem usa o mesmo formato de 320 × 192 e a mesma paleta da edição de 512 KiB. A edição de 128 KiB usa um único framebuffer e pode exibir atualizações durante a varredura.

## Compilação

Requer Python 3.10+, Py65, Pillow, LWASM e a imagem de disco original de Apple II.

```powershell
python -m pip install py65 Pillow
python tools/prepare.py "<disco original Apple II.dsk>" build/assets
python tools/sid_music.py evidence/c64-sid.json build/assets/music.inc
python tools/build.py build/assets build/base
python tools/build_128.py build/assets build/base/flat.asm build/128k
python tools/build_128.py build/assets build/base/flat.asm build/128k --ssc
```

O carregador está em `src/stream128.inc`. A versão de 128 KiB foi exercitada no XRoar 1.12. Os replays DAC saíram das oito fases e o da oitava chegou ao fim da animação de encerramento. A versão SSC teve o sequenciador verificado no emulador. A saída do cartucho e a leitura de discos físicos ainda precisam de teste em hardware.

