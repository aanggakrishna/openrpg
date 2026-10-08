# OpenRPG

**Game RPG kehidupan 2D berbasis Python dan Pygame.** Jelajahi rumah, kebun, peternakan, hutan, market, serta suaka Pokémon dalam dunia pixel art 8-bit. Rawat kebutuhan karakter, kumpulkan Pokémon, bertarung dalam duel real-time, dan buka terminal shell sungguhan di dalam game.

[Instalasi](#jalankan) · [Kontrol](#kontrol) · [Fitur](#aktivitas) · [Terminal](#terminal-sungguhan) · [Kredit aset](assets/CREDITS.md) · [Lisensi](#lisensi)

## Jalankan

**Persyaratan:** Python 3.10+ dan macOS atau Linux. Katalog dan gambar Pokémon diunduh dari PokéAPI saat pertama kali dibutuhkan; setelah itu data tersimpan dalam cache lokal.

Di macOS, klik dua kali `run.command`. Atau jalankan dari Terminal:

```sh
git clone https://github.com/aanggakrishna/openrpg.git
cd openrpg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Pilih Nara, Bima, atau Ayu, lalu tekan Enter. Progres tersimpan otomatis pada `.openrpg/save.json`; save lama tetap didukung.

## Sekilas fitur

- **Simulasi kehidupan:** makan, minum, istirahat, memasak, berkebun, beternak, memancing, dan merawat kesehatan.
- **Dunia untuk dijelajahi:** rumah, peternakan, hutan, market, pantai, gunung, serta suaka berukuran **5.120 × 4.800 piksel** dengan 12 habitat.
- **Satwa dan berkuda:** hewan bergerak dan berinteraksi dengan lingkungannya; beli perlengkapan, berburu, dan tunggangi kuda.
- **Pokémon:** katalog Pokédex PokéAPI, Pokémon yang berkeliaran, tim hingga tiga Pokémon aktif, Pokémon Center, evolusi, serta pertarungan melawan AI dan pelatih.
- **Duel arcade real-time:** arena berpanggung, lompatan, tangkisan, serangan, jurus, ultimate, item pemulih, dan Poké Ball dengan peluang tangkap.
- **Terminal asli:** jalankan shell dan OpenCode dari PC di kamar. Sesi terminal yang sama bisa dibuka di Terminal.app dan terus bekerja saat kamu kembali menjelajahi game.
- **Retro 8-bit:** dunia pixel art, font piksel, HUD arcade, animasi, dan efek jurus.

## Aset RPG

Grafis dunia memakai tileset dan sprite PNG asli dari Kenney, diperbesar tanpa smoothing agar pixel tetap tajam:

- [Tiny Town](https://kenney.nl/assets/tiny-town): rumput, jalan, rumah, pohon, pagar.
- [Tiny Farm](https://kenney.nl/assets/tiny-farm): tanaman, hewan, peternakan, karakter petani.
- [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon): sprite Ayu.
- [Roguelike/RPG Pack](https://kenney.nl/assets/roguelike-rpg-pack): tepian air, lantai, dapur, tempat tidur, meja, kursi, dekorasi.

Paket Kenney berlisensi **CC0**. Karakter kini memakai animasi berjalan empat arah dari [Ninja Adventure](https://pixel-boy.itch.io/ninja-adventure-asset-pack), karya Pixel-Boy dan AAA, juga CC0. Paket tersebut menyediakan NPC, pohon lebih detail, singa, kuda, ayam, babi hutan, hyena, dan monyet. Gajah dan kelinci memakai sprite sheet orisinal yang dibuat dengan ImageGen, masing-masing empat arah dan empat pose berjalan. Satwa Ninja Adventure memakai pose arah dengan gerak bob. Gaya visual tetap pixel art. Kredit dan lisensi tersedia di `assets/CREDITS.md`.

## Kontrol

| Tombol | Fungsi |
| --- | --- |
| WASD / panah | Berjalan |
| E | Berinteraksi; memilih duel atau informasi saat bertemu Pokémon |
| I | Inventory |
| H | Memakai obat |
| R | Naik atau turun dari kuda |
| T | Memajukan waktu satu jam |
| C | Membuka pilihan cuaca |
| B | Membuka tampilan terminal bersama |
| P | Membuka Pokédex |
| M | Membuka peta suaka Pokémon; gunakan roda atau +/- untuk zoom |
| N | Membuka Pokémon Center |
| Space | Menyerang dengan senjata atau memulai duel jika dekat Pokémon |
| F1 / Esc | Bantuan / menu |

### Aktivitas

- **Rumah dan kamar:** masak dan makan di dapur; isi kebutuhan di ruang keluarga; tidur untuk memulihkan kesehatan dan energi; gunakan PC untuk membuka terminal.
- **Kebun dan peternakan:** tanam, siram, dan panen sayur; beri makan ayam untuk mengumpulkan telur. Jual hasil panen di market.
- **Memancing:** lempar umpan di kolam, tunggu ikan menggigit, lalu tarik dengan E.
- **Hutan:** jelajahi habitat satwa. Predator berburu sesuai waktu; hewan dapat lari, melawan, dan muncul kembali.
- **Suaka Pokémon:** tekan M atau gunakan portal di halaman. Peta 5.120 × 4.800 terbagi dalam 12 habitat yang terhubung. Pokémon liar berpindah, bersembunyi, dan spesies langka muncul lebih jauh dari pintu masuk.
- **Pertemuan Pokémon:** dekati Pokémon lalu tekan E untuk memilih duel atau informasi Pokédex. Katalog, sprite, dan data yang sudah diambil disimpan di `.openrpg/pokedex`.
- **Pokémon Center:** periksa dan pulihkan Pokémon, atur hingga tiga anggota tim aktif, dan evolusikan Pokémon yang memenuhi syarat.
- **Duel:** bergerak dengan panah; panah atas untuk melompat atau memanjat; Shift untuk menangkis; A untuk pukulan jarak dekat; S dan D untuk jurus; F untuk ultimate; tombol 1–3 untuk mengganti Pokémon; O untuk melempar Poké Ball. Setiap duel dibatasi 60 detik. Pelatih juga menantang pemain di jalan dan arena.
- **Market:** Sari menjual makanan dan obat, Budi menjual senjata, dan Danu membeli hasil kebun, ternak, ikan, serta buruan. Market buka pukul 06:00–22:00.

### Berburu dan kesehatan

Uang awal 150 koin dan lima Poké Ball. Poké Ball tambahan dijual seharga 12 koin dari Sari. Tombak berharga 80; busur 160 dan panah 3 per buah. Beli senjata di Budi, kemudian pakai dengan 1 atau 2. Tombak menyerang jarak dekat ke arah hadap; busur menghabiskan satu panah per tembakan. Hewan yang diburu menghasilkan daging dan kulit ke tas. Buruan predator tidak memberikan hasil ke pemain.

Singa berburu pukul **06–10 dan 16–20**; hyena **18–06**. Gajah dan babi hutan dapat membalas serangan. Hewan yang mati muncul kembali setelah 100 detik waktu bermain.

Kebutuhan turun selama bermain, memakai PC, membuka tas, atau berbelanja. Energi rendah memperlambat berjalan. Lapar atau haus yang kosong mengurangi kesehatan; serangan satwa juga melukai pemain. Obat memulihkan 45 HP, tidur memulihkan kesehatan. Saat HP habis, pemain bangun di tempat tidur dengan HP penuh; tas dan uang tetap tersimpan. **Sesi terminal dan proses AI tidak diulang atau dihentikan oleh kematian pemain.**

### Waktu dan cuaca

Jam dan hari tampil di atas layar. Satu detik nyata setara 1,3 menit di game. T memajukan tepat 60 menit, termasuk pergantian hari dan pertumbuhan kebun. Pencahayaan berubah saat pagi, sore, dan malam; cuaca otomatis dapat berubah setiap tiga jam game. C menyediakan cerah, berawan, hujan, salju, dan otomatis. Salju memperlambat gerakan di luar rumah.

Lompatan satu jam langsung mengganti jadwal satwa; gerakan satwa selama jam yang dilewati tidak disimulasikan satu per satu. Menu jeda, bantuan, dan layar pemilihan karakter menjeda dunia; terminal tetap berjalan.

## Terminal sungguhan

Buka terminal dengan menekan B di mana saja atau gunakan PC di kamar. Terminal menjalankan shell lokal; ketik `opencode` untuk membuka OpenCode, atau gunakan perintah `opencode run` seperti biasa. OpenCode memerlukan instalasi dan autentikasi provider di komputer.

PC membuka **shell login interaktif lokal** menggunakan `$SHELL`, biasanya zsh di macOS atau bash di Linux. Shell memiliki controlling pseudo-terminal untuk mendukung job control dan Ctrl+C. Input keyboard, paste, perintah, file, dan proses adalah nyata.

Contoh perintah yang bisa Anda ketik di PC:

```sh
pwd
ls
python3 --version
git status
opencode
```

OpenCode tidak dijalankan otomatis. Ketik `opencode` seperti di aplikasi Terminal biasa jika ingin memakai AI. Ia memakai konfigurasi/login lokal Anda. Jika binary belum ditemukan melalui PATH, coba `~/.opencode/bin/opencode`.

Folder awal adalah `computer-workspace/` di direktori game; folder dibuat ketika PC pertama kali digunakan. Pilih folder atau shell lain:

```sh
.venv/bin/python main.py --project /path/ke/proyek
.venv/bin/python main.py --shell /bin/bash
```

Shell memakai akun pengguna Anda dan dapat melakukan operasi komputer yang sama seperti terminal biasa. Folder awal bukan sandbox; `cd` dapat berpindah ke direktori lain.

| Kontrol di PC | Fungsi |
| --- | --- |
| Ketik + Enter | Jalankan perintah |
| Tab / panah | Completion / navigasi shell dan CLI |
| Ctrl+C | Hentikan perintah foreground |
| Ctrl/Cmd+V | Paste clipboard |
| Roda mouse / Shift+PageUp / Shift+PageDown | Scroll riwayat terminal |
| F10 | Kirim Escape ke shell/CLI |
| Esc / tombol Tinggalkan PC | Kembali bermain tanpa menutup shell |
| R setelah shell selesai | Buka shell baru |

Anda dapat meninggalkan monitor untuk berkebun atau memancing sementara perintah masih berjalan, kemudian kembali ke sesi yang sama. Ini berlaku **selama aplikasi game masih terbuka**. Saat keluar aplikasi, game menyimpan progres dan menutup shell beserta pekerjaan yang mengikuti sesi terminal tersebut. Perintah yang sengaja dilepaskan dengan `nohup`/`disown` mengikuti perilaku shell biasa.

Riwayat scroll berisi hingga 2.000 baris. Output baru atau input mengembalikan tampilan ke bagian bawah. Aplikasi CLI yang memakai alternate screen dapat kembali ke layar shell setelah selesai.

## Platform dan catatan

Lokasi mencakup halaman, hutan, suaka Pokémon, pantai, gunung, market, rumah, dan kamar. Data katalog PokéAPI memerlukan internet saat pertama dimuat; katalog, detail Pokémon, serta setiap gambar yang sudah diambil dicache lokal. Terminal tertanam mendukung macOS/Linux. Mouse di aplikasi TUI, emoji kompleks, dan protokol gambar terminal belum didukung; gunakan keyboard untuk aplikasi CLI.

## Tema retro 8-bit

Tampilan memakai font piksel VT323, panel bersudut, palet navy/mint/emas,
bar HP bersegmen, ikon item berukuran tetap, dan latar arena piksel.
`retro.py` menyimpan komponen visual bersama. Isi terminal tetap memakai
font monospace Unicode agar output shell tetap terbaca. Kontrol dan format
save tidak berubah. Tutup lalu buka ulang game untuk memuat tema baru.

Font VT323 oleh Peter Hull dibundel dari repositori Google Fonts
(`ofl/vt323`) dengan lisensi SIL Open Font License di `assets/fonts/OFL.txt`.

### Pemeriksaan regresi

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python tests/check_game.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python tests/check_retro.py
```

Pemeriksaan retro menggunakan data Pokémon contoh dan tidak memerlukan jaringan. Save dan shell pemeriksaan terpisah dari
save pemain. Hasil render tersimpan di `artifacts/retro/`.

## Lisensi

Kode asli OpenRPG dirilis di bawah [MIT License](LICENSE). Aset pihak ketiga mengikuti lisensinya masing-masing; lihat [daftar kredit dan lisensi aset](assets/CREDITS.md) serta file lisensi yang disertakan pada setiap paket. Lisensi MIT untuk kode OpenRPG tidak mencakup merek dagang atau data dan artwork Pokémon.
