# DESIGN.md — Audio Quick Toolkit (Analog Console Edition)

> Dokumen spesifikasi aturan visual, UX, arsitektur komponen, layout, dan interaksi untuk Audio Quick Toolkit. Dokumen ini mengikat implementasi desktop Python (PySide6 / Qt 6.6+) berbasis arsitektur *Analog Studio Mixer & Hardware Console*.

---

## 0. Cara Pakai Dokumen

1. **Sumber Kebenaran:** File `tokens.json` adalah sumber kebenaran tunggal untuk seluruh nilai numerik (hex warna, dimensi piksel, margin, radius, ketebalan border, dan kurva fisika). Jika terdapat kontradiksi antara teks naratif di `DESIGN.md` dan nilai di `tokens.json`, implementor **MUST** memenangkan nilai di `tokens.json`.
2. **Hierarki Prioritas Aturan:**
   * Prioritas 1: `tokens.json` (Nilai token absolut).
   * Prioritas 2: Bagian 1 — Non-Negotiables (Aturan kelulusan mutlak).
   * Prioritas 3: Bagian 6 & 7 — Komponen dan Layar (Spesifikasi geometri instrumen hardware dan tata letak modul).
   * Prioritas 4: Bagian 2 s/d 5, 8 s/d 13 — Panduan visual, microcopy, dan aksesibilitas.
3. **Batasan Improvisasi AI / Developer:**
   * **Boleh Diimprovisasi:** Optimasi kalkulasi matematika paint call `QPainter`, pemisahan modul file python internal, caching `QPixmap`, dan threading pemrosesan audio background via `QThread`.
   * **DILARANG Diimprovisasi (NEVER):** Mengubah warna hex sasis/lampu, menghilangkan ornamen kayu samping (*wood cheeks*), mengganti tombol kotak *backlit* menjadi tombol datar web, menggunakan rotasi kursor 360 derajat untuk knob, atau memotong layout kartu hingga memicu scrollbar pada resolusi standar.

---

## 1. Non-Negotiables (Maksimal 20 Baris)

1. GUI **MUST** menggunakan **Python 3.10+** dengan **PySide6 (Qt 6.6+)**; framework berbasis webview/browser dilarang keras.
2. Gaya visual **MUST** merefleksikan **Analog Hardware Console**: sasis pelat perunggu (*anodized bronze*), lis kayu samping (*walnut cheeks*), dan ceruk kontrol hitam (*recessed wells*).
3. Sembilan modul utama disusun dalam **Grid Konsol 3x3** seragam berdimensi tetap $346 \times 216\text{ px}$ per modul.
4. Window default berukuran $1152 \times 768\text{ px}$; Minimum window adalah $1024 \times 680\text{ px}$.
5. Menu utama pada resolusi standar $1152 \times 768\text{ px}$ **NEVER** menampilkan scrollbar horizontal maupun vertikal.
6. Aksi utama tiap modul **MUST** menggunakan **Square Backlit Push-Button** berukuran $40 \times 40\text{ px}$ atau $36 \times 36\text{ px}$ dengan pendaran lampu pijar hangat (*amber halo*).
7. Warna teks sablon sasis (*silkscreen*) **MUST** krem gading `#EDE6DC` untuk heading dan khaki abu `#9E9182` untuk subteks; teks putih murni (`#FFFFFF`) dilarang.
8. Tombol pelat modul **MUST** memiliki 4 baut mesin heksagonal/slotted (`ChassisScrew`) di keempat sudutnya berdiameter $8\text{ px}$.
9. Seluruh rotary knob **MUST** merespons gestur **drag vertikal** mouse (tarik ke atas menaikkan nilai, tarik ke bawah menurunkan); rotasi melingkar dilarang.
10. Jarum VU Meter pada modul Key Detect dan Loudness Normalizer **MUST** digerakkan oleh kalkulasi buffer RMS audio riil via NumPy; timer animasi acak dilarang.
11. Tombol keyboard `Esc` di seluruh tampilan sekunder/workspace **MUST** mengembalikan tampilan ke konsol utama.
12. Font antarmuka **MUST** `Inter`; Font data numerik, BPM, LUFS, dan label tag modul **MUST** `JetBrains Mono`.
13. Frame rate canvas instrumen aktif (VU meter, waveform, LED ladder) **MUST** terkunci pada $60\text{ FPS}$ ($16.6\text{ ms}$).
14. **3 Hal yang MUST terlihat di screenshot mana pun:** Tekstur sasis *brushed bronze*, lis kayu *walnut* samping, dan lampu tombol *amber backlit*.
15. **Hal yang NEVER muncul sama sekali:** Tombol datar berwarna-warni pelangi (cyan/pink/neon), card UI mengambang (*floating white cards*), drop shadow blur CSS modern, dan icon emoji.

---

## 2. Arah Visual

### Mood Desain
* **3 Kata Representasi:** *Industrial*, *Tactile*, *Boutique-Studio*.
* **3 Kata Dilarang:** *Toy-like*, *SaaS-flat*, *Cyberpunk-neon*.

### Referensi Konkret
1. **Union Audio two.valve DJ Mixer (Referensi Utama):**
   * *Diambil:* Panel sasis perunggu gelap (*anodized dark bronze*), lis kayu kenari (*walnut end-cheeks*) di kedua sisi luar sasis, kenop aluminium silindris bertutup konsentris dengan indikator titik/garis putih, baut sasis hitam, dan tombol intip *Cue* berlingkar lampu pijar hangat.
   * *Ditinggalkan:* Teks tulisan tangan dekoratif dan layout 2-channel audio mixer fisik murni.
2. **Neve / SSL 4000 Console Channel Strips:**
   * *Diambil:* Organisasi strip modular fungsional, pembagian section berbasis pelat logam modular, dan sistem penomoran instrumen `[MOD-XX] [TAG]`.
   * *Ditinggalkan:* Fader plastik panjang 100mm yang memakan ruang vertikal layar launcher.
3. **Universal Audio (Apollo / UAD) Software Plugins:**
   * *Diambil:* Eksekusi visual hardware analog presisi tinggi yang menyatu secara fungsional dengan workflow desktop modern.
   * *Ditinggalkan:* Komposisi jendela popup terpisah-pisah.

---

## 3. Batasan Teknis

* **Core Platform:** Python 3.10+ (64-bit).
* **GUI Engine:** PySide6 (Qt 6.6+) menggunakan `QtWidgets`, `QtGui`, `QtCore`, dan `QtSvg`.
* **DSP & Compute Stack:** `numpy`, `scipy.signal`, `soundfile`, `librosa`, `sounddevice`.
* **Renderer Utama:** Custom `QPainter` dengan antialiasing aktif (`QPainter.RenderHint.Antialiasing`).
* **Icon Library:** Lucide Icons (SVG path monokrom dengan masker warna `QColor`).
* **Font UI:** `Inter` (Regular 400, Medium 500, SemiBold 600, Bold 700).
* **Font Teknis/Monospace:** `JetBrains Mono` (Medium 500, Bold 700).
* **Performance Budget:**
  * UI Frame Rate: Terkunci $60\text{ FPS}$ saat scrubbing/audio playback, $0\text{ FPS}$ saat idle.
  * Idle Memory: $< 140\text{ MB}$.
  * Startup Time: $< 750\text{ ms}$ hingga tampilan interaktif.
* **Ukuran Window:**
  * Default: Lebar $1152\text{ px}$, Tinggi $768\text{ px}$.
  * Minimum: Lebar $1024\text{ px}$, Tinggi $680\text{ px}$.
  * Maksimum: Bebas (layout konsol berpusat di tengah jika layar $> 1440\text{ px}$).

---

## 4. Design Tokens

### 4.1 Token Warna Sasis & Permukaan

| Nama Token | Nilai Hex / RGBA | Peruntukan Fungsional |
| :--- | :--- | :--- |
| `wood-walnut-base` | `#2A1A10` | Lis kayu samping kiri & kanan (dasar) |
| `wood-walnut-grain` | `#3D2617` | Tekstur serat kayu walnut highlight |
| `wood-walnut-shadow` | `#1A100A` | Bayangan ceruk pertemuan kayu dan sasis |
| `chassis-bronze-base` | `#3B2C1E` | Pelat logam perunggu sasis utama |
| `chassis-bronze-light`| `#483625` | Gradasi highlight atas pelat perunggu |
| `chassis-bronze-dark` | `#2D2116` | Gradasi bayangan bawah pelat perunggu |
| `plate-modular` | `#33251A` | Permukaan pelat masing-masing modul kartu 3x3 |
| `plate-groove` | `#17100B` | Parit alur batas antar pelat modul (1px inset) |
| `surface-well-dark` | `#120E0B` | Ceruk recessed display, VU meter, dan waveform |
| `surface-display-glass`| `#18130E` | Kaca proteksi display CRT / status inspect |

### 4.2 Token Pencahayaan & Indikator (Lamps & LEDs)

| Nama Token | Nilai Hex / RGBA | Peruntukan Fungsional |
| :--- | :--- | :--- |
| `amber-lamp-glow` | `rgba(245, 158, 11, 0.45)` | Pendaran halo tombol backlit aktif |
| `amber-lamp-lens` | `#F59E0B` | Lensa kaca tombol backlit saat menyala |
| `amber-lamp-core` | `#FFF1D6` | Inti filamen tombol menyala (pusat) |
| `amber-lamp-dim` | `#523617` | Lensa tombol saat standby/off |
| `led-green-lit` | `#22C55E` | LED status normal, CoreAudio aktif, VU aman |
| `led-amber-lit` | `#F59E0B` | LED warning, clip caution, status deteksi |
| `led-red-lit` | `#EF4444` | LED clipping overload, error state |
| `led-dark-unlit` | `#241C15` | LED dalam kondisi mati / tidak ada sinyal |

### 4.3 Token Tipografi & Teks Sablon (Silkscreen)

| Token | Nilai Hex | Font Family | Size / Weight | Line Height |
| :--- | :--- | :--- | :--- | :--- |
| `text-silkscreen-title` | `#EDE6DC` | `Inter` | $15\text{ px}$ / Bold 700 | $20\text{ px}$ |
| `text-silkscreen-sub` | `#9E9182` | `Inter` | $11\text{ px}$ / Regular 400 | $15\text{ px}$ |
| `text-silkscreen-tag` | `#B5A899` | `JetBrains Mono` | $10\text{ px}$ / Medium 500 | $14\text{ px}$ |
| `text-display-readout` | `#FCD34D` | `JetBrains Mono` | $13\text{ px}$ / Bold 700 | $16\text{ px}$ |
| `text-display-terminal`| `#EDE6DC` | `JetBrains Mono` | $10\text{ px}$ / Medium 500 | $13\text{ px}$ |
| `text-knob-label` | `#A39281` | `Inter` | $9\text{ px}$ / Bold 700 | $12\text{ px}$ |

### 4.4 Dimensi, Bevel, dan Radius

* **Radius:** `radius-screw: 9999px`, `radius-knob: 9999px`, `radius-well: 4px`, `radius-button: 6px`, `radius-card: 4px`.
* **Bevel:**
  * `bevel-raised-top`: `1px solid rgba(255, 255, 255, 0.12)`
  * `bevel-raised-bottom`: `1px solid rgba(0, 0, 0, 0.65)`
  * `bevel-recessed-top`: `1px solid rgba(0, 0, 0, 0.85)`
  * `bevel-recessed-bottom`: `1px solid rgba(255, 255, 255, 0.08)`
* **Dimensi Hardware:**
  * Lis Kayu Samping: Lebar $16\text{ px}$ (sisi kiri) dan $16\text{ px}$ (sisi kanan).
  * Diameter Baut Sasis: $8\text{ px}$ (offset $6\text{ px}$ dari sudut pelat kartu).
  * Diameter Rotary Knob Standar: $36\text{ px}$ (cap $28\text{ px}$).
  * Tombol Backlit Kotak: $36 \times 36\text{ px}$ (inset $3\text{ px}$).

---

## 5. Layout dan Grid

### 5.1 Shell Konsol Audio

```
[NATIVE macOS TITLE BAR ~24px, di luar klien: Traffic Lights + judul "Audio Quick Toolkit"]
+--[16px Wood]--+-------------------------------------------------------+--[16px Wood]--+
|               | TITLEBAR: Height 44px (Dark Anodized Strip)           |               |
|               | ◆ Audio Quick Toolkit  v2.0 · Pro Suite     (•)CoreAudio 48kHz |       |
|               +-------------------------------------------------------+               |
|  WALNUT       | CONSOLE VIEWPORT: Height 684px                        |  WALNUT       |
|  END-CHEEK    | Margin Top/Bottom: 20px, Left/Right: 24px             |  END-CHEEK    |
|  (Left)       |                                                       |  (Right)      |
|               | [3x3 Modular Hardware Strips Grid]                    |               |
|               | Gap Horizontal: 16px, Gap Vertikal: 16px              |               |
+---------------+-------------------------------------------------------+---------------+
```

> **Aturan title bar:** traffic lights (close/minimize/zoom) dan judul jendela dirender oleh **title bar native macOS** (~24 px, di luar area klien $1152 \times 768$). Strip 44 px di dalam klien hanya berisi brand (logo diamond, nama, versi) dan LED CoreAudio — **tanpa traffic lights**. Seluruh ukuran mengikuti angka dokumen ini, bukan gambar referensi `reference/main_dashboard.jpg` (konsep AI 16:9, teks tidak terbaca). Kartu **tidak memiliki baris deskripsi**.

### 5.2 Anggaran Geometri Konsol ($1152 \times 768\text{ px}$)

* **Lebar Konsol Total:** $1152\text{ px}$.
  * Lis Kayu: $16\text{ px} \times 2 = 32\text{ px}$.
  * Margin Horisontal: $24\text{ px} \times 2 = 48\text{ px}$.
  * Ruang Grid Efektif: $1152 - 32 - 48 = 1072\text{ px}$.
  * Lebar 3 Modul: $(1072 - (16 \times 2)) / 3 = 346.6\text{ px} \rightarrow \mathbf{346\text{ px}}$ per modul.
* **Tinggi Konsol Total:** $768\text{ px}$.
  * Titlebar Hardware: $44\text{ px}$.
  * Margin Vertikal: $20\text{ px} \times 2 = 40\text{ px}$.
  * Ruang Grid Efektif: $768 - 44 - 40 = 684\text{ px}$.
  * Tinggi 3 Modul: $(684 - (16 \times 2)) / 3 = 217.3\text{ px} \rightarrow \mathbf{216\text{ px}}$ per modul.
  * Sisa kompensasi ($2\text{ px}$) diserap oleh margin bawah.

```
Anatomi Vertikal Pelat Modul (Total 216px):
+-------------------------------------------------------------+
| Baut Kiri-Atas [x]                        Baut Kanan-Atas [x] |
| Padding Atas: 10px                                          |
| Header Baris 1: Tag [MOD-XX] [TAG] ......... Tombol BROWSE  | -> 18px
| Header Baris 2: Nama Modul (15px Bold)                      | -> 20px
| Gap Separator: 8px                                          |
| INSTRUMENT RACK AREA (Recessed Wells / Knobs / Displays)    | -> 140px
| Padding Bawah: 10px                                         |
| Baut Kiri-Bawah [x]                      Baut Kanan-Bawah [x] |
+-------------------------------------------------------------+
Jumlah = 10 + 18 + 20 + 8 + 140 + 20 = 216px (Presisi tanpa scrollbar)
```

---

## 6. Komponen Hardware

### 6.1 `SquareIlluminatedButton(QPushButton)`
Tombol tekan kotak dengan lensa pendaran lampu pijar (*amber backlighting*), terinspirasi dari tombol *Cue* mixer analog.
* **Dimensi:** Lebar $36\text{ px}$, Tinggi $36\text{ px}$ (atau $40 \times 40\text{ px}$ untuk tombol utama), Radius $6\text{ px}$.
* **Layer Tumpukan Geometri (Urutan Draw):**
  1. Base Recessed Well: Kotak warna `#120E0B` dengan inset border $1\text{ px}$ `#000000`.
  2. Bevel Ring Luar: Logam warna `#2A2016` dengan highlight atas $1\text{ px}$ `rgba(255,255,255,0.15)`.
  3. Lens Body (Kaca): `QLinearGradient` vertikal:
     * *Off State:* `#3D2813` ke `#24180A`.
     * *On / Active State:* `#F59E0B` ke `#D97706`.
  4. Filament Core: Lingkaran oval tengah pendaran `QRadialGradient` warna `#FFF3DB` (alpha $0.8$ ke $0.0$).
  5. Icon / Label Sablon: Masker ikon SVG atau teks font `Inter` $10\text{ px}$ warna `#120E0B` (saat On) atau `#8C7355` (saat Off).
* **Matriks Status:**

| State | Kondisi Lampu | Halo Glow Radius | Y-Offset Cap | Warna Teks / Icon |
| :--- | :--- | :--- | :--- | :--- |
| **Off (Resting)** | Mati / Redup | $0\text{ px}$ | $0\text{ px}$ | `#8C7355` |
| **Hover** | Menyala $40\%$ | $4\text{ px}$ (`rgba(245,158,11,0.2)`) | $0\text{ px}$ | `#D4A265` |
| **Pressed / Drag** | Menyala $100\%$ | $8\text{ px}$ (`rgba(245,158,11,0.5)`) | $+2\text{ px}$ | `#120E0B` |
| **Active / Running** | Menyala Penuh | $10\text{ px}$ (`rgba(245,158,11,0.6)`) | $+1\text{ px}$ | `#120E0B` |

### 6.2 `RotaryKnob(QWidget)`
Knob putar silindris aluminium bertekstur *concentric spun-metal*.
* **Dimensi:** Diameter luar $36\text{ px}$, Diameter cap $28\text{ px}$.
* **Layer Tumpukan Geometri:**
  1. Base Outer Rim: Diameter $36\text{ px}$, warna `#1A140F` dengan garis perimeter tipis.
  2. Indicator Scale Dots: Busur skala dot per $30^\circ$ dari $-135^\circ$ s/d $+135^\circ$ (total rentang putar $270^\circ$).
     * Dot nonaktif: `#382A1D`.
     * Dot aktif (terlewati nilai): `#F59E0B` (Amber) atau `#22C55E` (Green).
  3. Knob Metal Body: `QConicalGradient` mensimulasikan refleksi cahaya silang logam aluminium (*anodized aluminum sheen*). Stop warna: `#4F463D`, `#26211C`, `#4F463D`, `#26211C`.
  4. Indicator Notch: Garis indikator putih gading (`#EDE6DC`, tebal $2\text{ px}$, panjang $8\text{ px}$) ditarik dari tepi luar cap menuju pusat.
* **Fisika & Interaksi:**
  * Mode input: **Vertical Drag** (Kursor mouse otomatis terkunci saat drag: geser ke atas bertambah $+1\%/\text{px}$, geser ke bawah berkurang).
  * Double Click: Reset instan ke nilai default ($0$ atau detent $12\text{ o'clock}$).

### 6.3 `CircularVUMeter(QWidget)`
Panel meteran analog berbingkai bulat dengan jarum galvanometer balistik riil.
* **Dimensi:**
  * Versi Single (Loudness Normalize): Diameter $110\text{ px}$.
  * Versi Dual (Key & Tempo Detect): Diameter $82\text{ px}$ per meter.
* **Layer Tumpukan Geometri:**
  1. Metal Bezel Ring: Rim logam perak gelap `#544B42` tebal $3\text{ px}$ dengan highlight pantulan kaca atas.
  2. Recessed Chamber Face: `QLinearGradient` bernuansa kuning gading lapuk: Stop 0.0 `#E6D7B3`, Stop 1.0 `#C7B283`.
  3. Tanda Skala Cetak:
     * Arc $-20\text{ dB}$ s/d $0\text{ dB}$: Hitam `#14120F`, tebal $1.2\text{ px}$.
     * Arc $0\text{ dB}$ s/d $+3\text{ dB}$: Merah marun `#B91C1C`, tebal $2.0\text{ px}$.
     * Logo Pabrikan: Sablon `"UA"` atau `"VU"` di bagian tengah bawah busur.
  4. Jarum Meteran: Jarum segitiga meruncing panjang warna hitam `#120E0B` dengan ujung merah tipis $10\text{ px}$.
  5. Cap Pivot: Penutup pivot tengah diameter $16\text{ px}$ berwarna hitam dengan pantulan perak.
* **Formula Ballistics:**
  * Sumber data: Buffer audio PCM $\rightarrow \text{RMS} = \sqrt{\frac{1}{N}\sum x_i^2}$.
  * Sudut defleksi: $\theta = \text{clip}\left(\frac{\text{dB} + 20}{23} \times 80^\circ - 40^\circ, -40^\circ, +40^\circ\right)$.
  * Integrasi gerak: $v_{t+1} = (v_t + (\theta_{\text{target}} - \theta_t) \times 0.20) \times 0.70$.

### 6.4 `LEDMeterLadder(QWidget)`
Tangga LED vertikal penunjuk intensitas level audio dan proses.
* **Dimensi:** Lebar $14\text{ px}$, Tinggi $96\text{ px}$, 12 Segmen bulat/persegi kecil.
* **Komposisi Segmen (Dari Bawah ke Atas):**
  * Segmen 1–8: Hijau `#22C55E` (Level normal/aman).
  * Segmen 9–10: Kuning/Amber `#F59E0B` (Mendekati threshold).
  * Segmen 11–12: Merah `#EF4444` (Peak overload / active processing).

### 6.5 `ChassisScrew(QWidget)`
Baut mesin pengikat pelat modular kartu ke sasis utama.
* **Dimensi:** $8 \times 8\text{ px}$.
* **Visual:** Ceruk gelap `$120E0B` dengan kepala baut perak gelap `#4A4035` dan garis minus acak $45^\circ$ ber-highlight 1px.

---

### 6.6 `BrowseButton(QPushButton)`
Tombol pemilih file manual di baris header kartu (kanan), tersedia di semua 9 modul.
* **Dimensi:** tinggi $18\text{ px}$, lebar menyesuaikan teks (padding horizontal $8\text{ px}$), radius $6\text{ px}$ (token `browse_button`).
* **Visual:** pil gelap *raised* (`#120E0B`) dengan bevel `bevel-raised-top/bottom`; ikon dokumen $10\text{ px}$ + teks `BROWSE` font mono, uppercase, $9\text{ px}$ Bold, warna `#B5A899`.
* **State:** Hover teks `#EDE6DC`; Pressed bevel menjadi *recessed* dan bergeser $+1\text{ px}$; Focus ring amber `#F59E0B` $2\text{ px}$.
* **Fungsi:** membuka dialog pilih file audio (setara drag-and-drop).

---

## 7. Layar Konsol & Spesifikasi 9 Modul

### 7.1 Layout Konsol 9 Modul (Grid 3x3)

```
+-----------------------------------+-----------------------------------+-----------------------------------+
| [MOD-01] [CONV]           [BROWSE]| [MOD-02] [STEM]           [BROWSE]| [MOD-03] [MERG]           [BROWSE]|
| Audio Converter                   | AI Stem Separator                 | Track Combiner                    |
|   (O)      (O)      (O)           |   (O)      (O)      [===]  [:::]  |        (•) [ | ]                  |
|  FORMAT  BIT-DEPTH SAMPLE-RATE    | AI MODEL STEM-TARGET WAVE  LED-LAD|  [ ■ ] (•) [ | ] FADER            |
|                                   |                                   |  OPEN  (•) [ | ]                  |
+-----------------------------------+-----------------------------------+-----------------------------------+
| [MOD-04] [DETC]           [BROWSE]| [MOD-05] [PTCH]           [BROWSE]| [MOD-06] [TMP]            [BROWSE]|
| Key & Tempo Detection             | Pitch Shifter                     | Tempo Change                      |
|  (VU-L)   (VU-R)   [BPM: 124.0]   |  (•) (O)  +-------------+         |  +---[==]---+  [ 0.00 ]  (O)      |
|                    [KEY: Amin ]   |  [ ■ ]    | BAR DISPLAY |         |    H-FADER               KNOB     |
|                    (•) (•) (•)    |  MUTE     +-------------+         |  [ ■ ] OPEN                       |
+-----------------------------------+-----------------------------------+-----------------------------------+
| [MOD-07] [TRIM]           [BROWSE]| [MOD-08] [NORM]           [BROWSE]| [MOD-09] [INFO]           [BROWSE]|
| Audio Trim                        | Loudness Normalizer               | Audio Information / Inspector     |
|  (O)  +------------------+  (O)   |            ( VU METER )   [LUFS]  | +-----------------------+   (O)   |
|  TRIM | WAVEFORM DISPLAY |  TRIM  |            |  analog  |   [-14 ]  | | Property: 48kHz 24bit |         |
|  (O)  +--[=]-------------+  [ ]   |   [ ■ ]    +----------+    (•)(•) | | LUFS: -14.2  BPM: 124 |   (O)   |
|  TRIM     TIMECODE     FADE I/O   |   OPEN                            | +-----------------------+  SELECT |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

### 7.2 Spesifikasi Kontrol Per Modul

1. **[MOD-01] Audio Converter:**
   * 3 Rotary Knobs dengan busur dot amber: `FORMAT` (WAV/MP3/FLAC/AIFF), `BIT DEPTH` (16/24/32-bit), `SAMPLE RATE` (44.1k/48k/96k).
   * Tombol Aksi: Header `[BROWSE]` file picker.
2. **[MOD-02] AI Stem Separator:**
   * 2 Knobs: `AI MODEL` (Vocal/Instrumental/Drums/Bass) dan `STEM TARGET`.
   * Mini Waveform Display ($70 \times 44\text{ px}$) bersanding dengan `LEDMeterLadder` 12-segmen vertikal.
3. **[MOD-03] Track Combiner:**
   * 1 Square Backlit Button `[ ■ OPEN ]` amber.
   * 1 Console Fader vertikal perak dengan alur metal, 3 LED dot status trek (Merge ready).
4. **[MOD-04] Key & Tempo Detection:**
   * Dual Circular Analog VU Meters ($82\text{ px}$ diameter) untuk representasi stabilitas harmonic & beat.
   * 2 Box Readout Monospace bertumpuk di kanan: box berlabel `BPM` dan `Key` dengan caption di bawahnya (placeholder saat idle, berisi nilai `124.0` / `A Minor` setelah analisis); 2 LED di antara VU dan 3 LED status di bawah box.
5. **[MOD-05] Pitch Shifter:**
   * 1 Semitone Rotary Knob, 1 Square Button `[ ■ MUTE / OPEN ]`.
   * Digital Bar Pitch Shift Display ($110 \times 54\text{ px}$) bergaris-garis pitch translasi vertikal.
6. **[MOD-06] Tempo Change:**
   * 1 Fader Horizontal ($140\text{ px}$) dengan kepala fader aluminium beralur grip dan tick mark atas-bawah.
   * Numeric Readout Box digital `[ 0.00 ]`, **2** Knob Rotary (tempo coarse dan fine-adjust).
   * 1 Square Backlit Button `[ ■ OPEN ]`.
7. **[MOD-07] Audio Trim:**
   * Display Well Kaca Gelap ($150 \times 54\text{ px}$) menampilkan waveform amber menyala dengan marker in/out logam.
   * 3 Knob Trim Mikro berlabel `TRIM` (2 di kiri, 1 di kanan waveform), Scrub Slider horizontal dengan tombol ◀ ▶ di bawah waveform, 2 Tombol kotak kecil berlabel `FADE IN/OUT`.
8. **[MOD-08] Loudness Normalizer:**
   * 1 Circular VU Meter Besar ($110\text{ px}$ diameter) jarum analog berlabel `"VU"`.
   * Box Display Digital Target dengan caption `LUFS` di atasnya (idle menampilkan `LUFS`; nilai `-14`, `-16`, `-9` saat dipilih), 4 Indikator LED (grid 2×2: True Peak dan status).
   * 1 Square Backlit Button berlabel `MUTE`.
9. **[MOD-09] Audio Information / Inspector:**
   * Display Well Terminal CRT Gelap ($170 \times 74\text{ px}$) teks monospace krem `#EDE6DC` (bukan hijau) memuat info teknis file; scrollbar tipis internal terminal diizinkan (satu-satunya pengecualian aturan tanpa scrollbar).
   * 2 Knobs Selector Vertikal di sisi kanan (ditumpuk, dengan penanda ▼ di antaranya) untuk memilih daftar metadata.

---

## 8. Interaksi dan Motion

### 8.1 Tabel Transisi Animasi

| Pemicu (Trigger) | Komponen Terdampak | Nilai Animasi | Durasi | Easing Curve |
| :--- | :--- | :--- | :--- | :--- |
| Tekan Tombol Kotak | `SquareIlluminatedButton` | Cap Y-shift $+2\text{ px}$, halo glow $10\text{ px}$ | $60\text{ ms}$ | `QEasingCurve.Type.OutQuad` |
| Lepas Tombol Kotak | `SquareIlluminatedButton` | Cap Y-shift $0\text{ px}$, halo glow $4\text{ px}$ | $100\text{ ms}$ | `QEasingCurve.Type.OutBounce` |
| Drag Kursor Vertikal | `RotaryKnob` | Rotasi sudut $-135^\circ$ s/d $+135^\circ$ | Instan | Linear (1:1 Drag Map) |
| Pulsa RMS Audio | `CircularVUMeter` | Defleksi jarum $\theta_t \rightarrow \theta_{\text{target}}$ | Real-time | Ballistic Filter ($20\%$ stiff, $70\%$ damp) |
| File Valid Drag Over | Pelat Modul Kartu | Border groove menyala amber 1px | $120\text{ ms}$ | `QEasingCurve.Type.Linear` |

### 8.2 Logika Drag and Drop Hardware
* Menyeret file `.wav`, `.mp3`, `.flac` langsung ke atas salah satu pelat modul akan mengaktifkan pendaran perimeter pelat (`1px solid #F59E0B`) dan mengarahkan modul seketika memproses file tersebut.

### 8.3 Umpan Balik Auditori (Haptic Sound)
* **Klik Sakelar Mekanik:** File buffer WAV $15\text{ ms}$ sampel sakelar hardware studio berfrekuensi $2.1\text{ kHz}$ dimainkan saat tombol ditekan.
* **Detent Knob:** Bunyi mikro-klik reel $6\text{ ms}$ saat knob melewati titik tengah default.

---

## 9. Konten dan Microcopy

* **Konvensi Huruf:**
  * Penomoran: `[MOD-01]` s/d `[MOD-09]`.
  * Kategori Tag: `[CONV]`, `[STEM]`, `[MERG]`, `[DETC]`, `[PTCH]`, `[TMP]`, `[TRIM]`, `[NORM]`, `[INFO]`.
  * Judul Modul: **Title Case** (`Audio Converter`, `Loudness Normalizer`).
  * Label Kontrol & Knob: **Uppercase Singkat** (`FORMAT`, `BIT DEPTH`, `AI MODEL`, `MUTE`, `BROWSE`).
* **Format Nilai Display:**
  * BPM: `124.0 BPM`
  * Key: `A Minor / 8A`
  * Loudness: `-14.0 LUFS`
  * Audio Info: `WAV | 48.0 kHz | 24-bit`

---

## 10. Aksesibilitas

1. **Navigasi Keyboard:**
   * `Tab` / `Shift+Tab`: Berpindah antar modul dari MOD-01 hingga MOD-09, lalu masuk ke sub-kontrol di dalam modul aktif.
   * `Focus Ring`: Bevel luar pelat modul berganti menjadi garis amber bercahaya tebal $2\text{ px}$ (`#F59E0B`).
   * Tombol Panah `Up`/`Down`: Menyesuaikan parameter rotary knob aktif sebesar $\pm 1\%$.
2. **Kemandirian Warna (Color Independence):**
   * Setiap lampu LED indikator clipping / overload wajib disertai label teks `PK` atau `CLIP` timbul di pelat logam, tidak bergantung hanya pada warna merah.

---

## 11. Anti-Pattern (Larangan Eksplisit)

| Pola Terlarang (DILARANG KERAS) | Dampak Negatif | Pengganti Wajib yang Benar |
| :--- | :--- | :--- |
| Tombol UI Warna-Warni Permen (Cyan/Pink/Neon) | Menghancurkan tema analog console | Square Illuminated Button ber-halo amber `#F59E0B` |
| Knob Diputar dengan Kursor Melingkar | Sulit dikontrol mouse secara presisi | Input drag vertikal (geser atas = naik, bawah = turun) |
| Menghilangkan Lis Kayu Samping | Terlihat seperti web dashboard biasa | Pasang $16\text{ px}$ walnut wood cheek di kiri & kanan |
| Font Serif Jadul atau Efek Karat Berlebih | Terlihat seperti rongsokan vintage | Tipografi modern teknikal (`Inter` + `JetBrains Mono`) |
| Animasi VU Meter Berpola Random Timer | Menipu audio engineer | Wajib bind ke buffer RMS NumPy aktual audio |
| Scrollbar Vertikal pada Layar Utama | Merusak estetika rack mixer utuh | Kunci tinggi modul pada $216\text{ px}$ tanpa scroll |

---

## 12. Aset Referensi

* Direktori Penyimpanan: `/reference/`
  * `/reference/main_dashboard.jpg`: Render konsep UI *Audio Quick Toolkit* edisi konsol 9 modul (16:9, hasil AI, teks tidak terbaca). Dipakai untuk acuan mood, material, dan komposisi saja; **ukuran, gap, dan margin mengikuti DESIGN.md/tokens.json**.
* **Aturan Sumber Kebenaran:** Jika terjadi konflik antara visual gambar referensi dengan nilai numerik di `tokens.json`, implementor **MUST** mematuhi nilai numerik `tokens.json`.

---

## 13. Definition of Done & Keputusan Terbuka

### Checklist Verifikasi Selesai (DoD)
* [ ] Antarmuka berjalan 100% menggunakan Python 3.10+ dan PySide6 native tanpa dependensi web engine.
* [ ] Jendela $1152 \times 768\text{ px}$ menampilkan sasis perunggu dengan lis kayu samping $16\text{ px}$ di kiri dan kanan tanpa scrollbar.
* [ ] Seluruh 9 modul kartu terpasang baut sasis $8\text{ px}$ di keempat sudutnya.
* [ ] Seluruh rotary knob dapat digerakkan secara presisi via vertical drag mouse dan ter-reset saat double click.
* [ ] Tombol kotak backlit memancarkan pendaran halo amber saat aktif dan tertekan $2\text{ px}$ ke bawah.
* [ ] Jarum analog VU meter dan LED ladder terhubung ke buffer audio kalkulasi NumPy.
* [ ] Shortcut `Esc` berfungsi mengembalikan navigasi ke konsol utama.

### Keputusan Terbuka (Open Decisions)

| No | Topik Keputusan | Opsi Tersedia | Default Sementara Implementasi | Pengambil Keputusan |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Tekstur Sasis Logam Perunggu | Baked Static PNG vs Prosedural QImage | Baked Tileable 64x64 PNG (Performa tinggi) | Lead GUI Dev |
| 2 | Model VU Meter Kanal | Stereo Dual-Chamber vs Mono Sum | Stereo Dual-Needle pada Key Detect & Normalize | Audio DSP Lead |