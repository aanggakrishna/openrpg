# OpenRPG

Game kehidupan 2D berbasis Python: karakter beranimasi, kebun, peternakan, hutan dengan satwa, market NPC, dan **terminal shell sungguhan di monitor PC dalam kamar**.

## Jalankan

Di macOS, klik dua kali `run.command`, atau:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Pilih Nara, Bima, atau Ayu, lalu Enter. Posisi, kesehatan, kebutuhan, tas, uang, kebun, kuda, satwa, cuaca, dan waktu tersimpan otomatis setiap 15 detik serta saat keluar, di `.openrpg/save.json`. Penyimpanan versi lama tetap bisa dibuka.

## Aset RPG

Grafis dunia memakai tileset dan sprite PNG asli dari Kenney, diperbesar tanpa smoothing agar pixel tetap tajam:

- [Tiny Town](https://kenney.nl/assets/tiny-town): rumput, jalan, rumah, pohon, pagar.
- [Tiny Farm](https://kenney.nl/assets/tiny-farm): tanaman, hewan, peternakan, karakter petani.
- [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon): sprite Ayu.
- [Roguelike/RPG Pack](https://kenney.nl/assets/roguelike-rpg-pack): tepian air, lantai, dapur, tempat tidur, meja, kursi, dekorasi.

Paket Kenney berlisensi **CC0**. Karakter kini memakai animasi berjalan empat arah dari [Ninja Adventure](https://pixel-boy.itch.io/ninja-adventure-asset-pack), karya Pixel-Boy dan AAA, juga CC0. Paket tersebut menyediakan NPC, pohon lebih detail, singa, kuda, ayam, babi hutan, hyena, dan monyet. Gajah dan kelinci memakai sprite sheet orisinal yang dibuat dengan ImageGen, masing-masing empat arah dan empat pose berjalan. Satwa Ninja Adventure memakai pose arah dengan gerak bob. Gaya visual tetap pixel art. Kredit dan lisensi tersedia di `assets/CREDITS.md`.

## Kontrol dan aktivitas

| Kontrol | Fungsi |
| --- | --- |
| WASD / panah | Berjalan |
| E | Interaksi benda terdekat |
| I | Tas dan catatan aktivitas |
| Space | Serang dengan senjata; dekat Pokémon atau pelatih untuk mulai duel |
| 1 / 2 / 3 saat bermain | Pakai tombak / busur / simpan senjata |
| H | Gunakan obat dari tas |
| R | Naik kuda terdekat / turun |
| T / tombol +1 jam | Majukan waktu satu jam |
| C | Pilih cuaca atau kembali ke cuaca otomatis |
| B | Buka ponsel dan kirim prompt ke OpenCode |
| P | Buka Pokédex; ketik nama untuk mencari |
| N / E di center suaka | Periksa, pulihkan, dan evolusikan tim Pokémon |
| M | Langsung masuk ke suaka Pokémon |
| F1 | Bantuan |
| Esc | Menu; saat di PC, tinggalkan monitor |
| 1 / 2 / 3 | Pilih karakter di layar awal |

- **Rumah:** pintu depan. Dapur memasak 1 bahan menjadi 1 makanan, meja makan untuk makan. Air memulihkan minum, sofa memulihkan senang dan energi.
- **Kamar:** pintu kanan atas ruang keluarga. Tidur mengawali hari berikutnya dan mengisi energi. PC membuka terminal.
- **Kebun:** E tanam, E siram, tunggu 45 detik waktu bermain, E panen 2 sayur. Benih dan air tidak terbatas.
- **Peternakan:** beri ayam 1 sayur untuk menerima 2 telur. Jeda 40 detik sebelum pemberian berikutnya.
- **Kolam:** E melempar umpan, tunggu 2,5 detik hingga TARIK, E dalam 1,7 detik untuk menangkap ikan.
- **Taman:** bangku untuk bersantai.
- **Hutan:** ikuti jalan ke kiri halaman. Ada 30 satwa dari enam jenis; satwa berjalan, beristirahat, kabur, dan predator mengejar mangsa. E pada tumpukan kayu untuk mengumpulkan kayu.
- **Suaka Pokémon:** tekan M kapan saja saat bermain, atau gunakan portal bertanda Pokémon di halaman. Peta seluas 2.560 × 1.600 piksel mengikuti pemain, dengan jalan ke pantai dan gunung. Pokémon berkeliaran, lari menjauh, dan kadang bersembunyi di semak. Dekati lalu tekan Space untuk memulai duel. Spesies generasi awal banyak di dekat pintu; spesies yang lebih langka dan level lebih tinggi muncul makin jauh.
- **Pokédex:** tekan P untuk melihat daftar PokéAPI, cari berdasarkan nama atau nomor, dan periksa tipe, gambar, serta koleksi. Katalog, detail, evolusi, gambar resmi, dan GIF sprite battle yang telah diunduh disimpan lokal di `.openrpg/pokedex`.
- **Duel Pokémon real-time:** jelajahi suaka, pantai, atau gunung untuk bertemu Pokémon liar, lalu bertarung satu lawan satu melawan AI. A/D bergerak, W melompat, S menangkis, J / Space menyerang, Q memakai jurus sesuai tipe Pokémon, dan K memakai ultimate setelah meter terisi. Efek api, air, daun, listrik, dan tipe lain punya animasi visual bertema. O / 2 melempar Poké Ball, Tab mengganti Pokémon tim, dan Esc kembali ke peta. HP rendah memberi tanda untuk menangkap. Pertarungan pelatih di arena dan sepanjang jalan memberi uang serta XP.
- **Pokémon Center:** dekati bangunan putih-merah dekat pintu masuk suaka dan tekan E. N juga membukanya saat berdiri dekat. Periksa tipe, level, XP, dan HP; pulihkan tim; dan evolusikan Pokémon yang memenuhi syarat level-up. Menang duel memberi XP dan level yang tersimpan.
- **Market:** ikuti jalan ke kanan halaman. Buka 06:00–22:00. Dekati Sari untuk makanan/obat, Budi untuk senjata/panah, atau Danu untuk menjual sayur, telur, ikan, daging, kulit, dan kayu. E membuka perdagangan; pilih jual satu atau semua.
- **Kuda:** berada di peternakan. Dekati lalu R atau E untuk naik; bisa dibawa menyeberang ke hutan dan market. Masuk rumah otomatis menurunkan penunggang.

### Berburu dan kesehatan

Uang awal 150 koin dan lima Poké Ball. Poké Ball tambahan dijual seharga 12 koin dari Sari. Tombak berharga 80; busur 160 dan panah 3 per buah. Beli senjata di Budi, kemudian pakai dengan 1 atau 2. Tombak menyerang jarak dekat ke arah hadap; busur menghabiskan satu panah per tembakan. Hewan yang diburu menghasilkan daging dan kulit ke tas. Buruan predator tidak memberikan hasil ke pemain.

Singa berburu pukul **06–10 dan 16–20**; hyena **18–06**. Gajah dan babi hutan dapat membalas serangan. Hewan yang mati muncul kembali setelah 100 detik waktu bermain.

Kebutuhan turun selama bermain, memakai PC, membuka tas, atau berbelanja. Energi rendah memperlambat berjalan. Lapar atau haus yang kosong mengurangi kesehatan; serangan satwa juga melukai pemain. Obat memulihkan 45 HP, tidur memulihkan kesehatan. Saat HP habis, pemain bangun di tempat tidur dengan HP penuh; tas dan uang tetap tersimpan. **Sesi terminal dan proses AI tidak diulang atau dihentikan oleh kematian pemain.**

### Waktu dan cuaca

Jam dan hari tampil di atas layar. Satu detik nyata setara 1,3 menit di game. T memajukan tepat 60 menit, termasuk pergantian hari dan pertumbuhan kebun. Pencahayaan berubah saat pagi, sore, dan malam; cuaca otomatis dapat berubah setiap tiga jam game. C menyediakan cerah, berawan, hujan, salju, dan otomatis. Salju memperlambat gerakan di luar rumah.

Lompatan satu jam langsung mengganti jadwal satwa; gerakan satwa selama jam yang dilewati tidak disimulasikan satu per satu. Menu jeda, bantuan, dan layar pemilihan karakter menjeda dunia; terminal tetap berjalan.

## Terminal sungguhan

Ponsel dalam game: tekan B, ketik prompt, lalu Enter. Game menjalankan opencode run dengan prompt tersebut di sesi terminal latar belakang, pada folder proyek PC. Awali input dengan ! untuk menjalankan perintah shell biasa. Setelah perintah selesai, game menampilkan notifikasi ponsel. OpenCode memerlukan instalasi dan autentikasi provider yang sudah dikonfigurasi.

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

## Cakupan

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

Pemeriksaan retro memakai cache Pokémon 1, 4, 7, dan 15 yang sudah tersedia
lokal, tanpa permintaan jaringan. Save dan shell pemeriksaan terpisah dari
save pemain. Hasil render tersimpan di `artifacts/retro/`.
