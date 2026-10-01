# DESIGN.md — Audio Quick Toolkit

> Dokumen spesifikasi aturan visual, UX, arsitektur komponen, layout, dan interaksi untuk Audio Quick Toolkit. Dokumen ini mengikat implementasi antarmuka pada platform desktop Python (PySide6).

---

## 0. Cara Pakai Dokumen

1. **Sumber Kebenaran:** File `tokens.json` adalah sumber kebenaran tunggal untuk seluruh nilai numerik (hex warna, ukuran piksel, margin, radius, durasi, dan kurva fisika). Jika terdapat kontradiksi antara teks naratif di `DESIGN.md` dan nilai di `tokens.json`, implementor **MUST** memenangkan nilai di `tokens.json`.
2. **Hierarki Prioritas Aturan:**
   * Prioritas 1: `tokens.json` (Nilai token absolut).
   * Prioritas 2: Bagian 1 — Non-Negotiables (Aturan mutlak lulus/gagal).
   * Prioritas 3: Bagian 6 & 7 — Komponen dan Layar (Spesifikasi geometri dan tata letak).
   * Prioritas 4: Bagian 2 s/d 5, 8 s/d 13 — Panduan visual, microcopy, dan aksesibilitas.
3. **Batasan Improvisasi AI / Developer:**
   * **Boleh Diimprovisasi:** Struktur kode internal Python class, private helper functions, pembagian modul file internal, dan algoritma matematika optimasi rendering canvas buffer.
   * **DILARANG Diimprovisasi (NEVER):** Mengubah warna hex, menambah komponen visual di luar layout 4-slot, mengubah label tombol, memperbesar ukuran font, mengganti font keluarga, atau mengubah parameter ballistics instrumen.

---

## 1. Non-Negotiables

1. GUI **MUST** menggunakan **Python 3.10+** dengan **PySide6 (Qt 6.6+)**; framework berbasis browser/webview dilarang.
2. Menu utama **MUST** menggunakan **Dark Modern Bento Grid**; Ruang kerja editing **MUST** menggunakan **Tactile Industrial Skeuomorphism**.
3. Seluruh 9 modul ruang kerja **MUST** mengimplementasikan template 4-slot seragam: Top Bar ($48\text{ px}$), Deck ($210\text{ px}$), Rack ($280\text{ px}$), dan Footer ($64\text{ px}$).
4. Dimensi default window adalah $1152 \times 768\text{ px}$; Ukuran minimum mutlak adalah $1024 \times 680\text{ px}$.
5. Menu utama pada resolusi standar ($1152 \times 768\text{ px}$) **NEVER** menampilkan scrollbar horizontal maupun vertikal.
6. Deskripsi kartu launcher **MUST** elided maksimal 2 baris ($34\text{ px}$); teks yang melebihi batas dipotong dengan `...`.
7. Tombol taktil `ChunkyButton` **MUST** memiliki bevel 3D bawah $4\text{ px}$ pada state default dan menyusut ke $1\text{ px}$ dengan translasi `y + 3px` pada state active/pressed.
8. Warna teks di atas SEMUA tombol aksen kartu **MUST** `#090B0E` (Hitam pekat, Weight 700); teks putih dilarang keras.
9. Token aksen Tempo Change **MUST** `#2DD4BF` (Teal), token Loudness Normalize **MUST** `#38BDF8` (Sky Blue).
10. Jarum VU Meter **MUST** digerakkan oleh kalkulasi buffer audio RMS real-time ($50\text{ ms}$ window via NumPy); dilarang menggunakan animasi timer acak.
11. Orientasi Fader: Pitch Shifter **MUST** vertikal, Tempo Change **MUST** horizontal, AI Stem Separator **MUST** 4x fader vertikal.
12. Tombol keyboard `Esc` di seluruh ruang kerja **MUST** mengembalikan tampilan ke Dashboard Launcher (Index 0).
13. Font antarmuka **MUST** `Inter`; Font data numerik, BPM, LUFS, dan label pelat rack **MUST** `JetBrains Mono`.
14. Frame rate rendering custom canvas (VU meter, waveform, spectrum) **MUST** terkunci pada $60\text{ FPS}$ ($16.6\text{ ms}$ interval timer).
15. **3 Hal yang MUST terlihat di screenshot mana pun:** Background gelap pekat `#090B0E`, bezel/border presisi $1\text{ px}$, dan aksen warna solid berkontras tinggi dengan teks hitam tebal.
16. **Hal yang NEVER muncul sama sekali:** Gradient pelangi ungu-biru generik, border radius di luar token, teks deskripsi overflow, drop-shadow kabur yang menyebar luas, dan emoji sebagai icon tombol.

---

## 2. Arah Visual

### Mood Desain
* **3 Kata Representasi:** *Tactile*, *Utilitarian*, *Focused*.
* **3 Kata Dilarang:** *Toy-like*, *SaaS-generic*, *Hyper-futuristic*.

### Referensi Konkret
1. **Braun ET66 / Dieter Rams Audio Hardware:**
   * *Diambil:* Bentuk tombol cembung mekanik dengan feedback tactile nyata, tata letak keypad berbasis grid presisi, pemisahan fungsi kontrol berbasis blok warna diskret.
   * *Ditinggalkan:* Warna bodi plastik krem/putih terang. Seluruh perangkat diadaptasi ke dalam palet dark slate metalik.
2. **Studer A800 / Revox Tape Deck Console:**
   * *Diambil:* Visualisasi dual-chamber VU Meter analog dengan dial bertekstur kuning gading, jarum mekanik dengan ballistics realistis, tuas toggle fader berkontur.
   * *Ditinggalkan:* Tekstur kayu samping, karat buatan, dan sekrup analog berlebihan yang membebani ruang pandang layar.
3. **Teenage Engineering (OP-1 / Field Series):**
   * *Diambil:* Tipografi teknis monospaced yang sangat tajam, indikator dot-matrix/segmentasi LED digital, kontras grafis tegas tanpa degradasi visual.
   * *Ditinggalkan:* Navigasi eksperimental yang abstrak. Pola navigasi tetap konvensional dan ramah bagi pengguna kasual.

---

## 3. Batasan Teknis

* **Core Runtime:** Python 3.10+ (64-bit).
* **GUI Framework:** PySide6 (Qt 6.6+) murni via `QtWidgets`, `QtGui`, `QtCore`, dan `QtSvg`.
* **Audio DSP Stack:** `numpy` (vektor PCM), `scipy.signal` (filter & loudness), `soundfile` (I/O file), `librosa` (pitch & time-stretch), `sounddevice` (output stream).
* **AI Engine:** `onnxruntime` / `torch` CPU/DirectML backend.
* **Icon Library:** Lucide Icons (format `.svg`, single color mask, ukuran $16\text{ px}$ dan $20\text{ px}$).
* **Font UI:** `Inter` (Regular 400, Medium 500, SemiBold 600, Bold 700).
* **Font Data/Monospace:** `JetBrains Mono` (Medium 500, Bold 700).
* **Performance Budget:**
  * UI Frame Rate: Terkunci $60\text{ FPS}$ untuk visualizer aktif; $0\text{ FPS}$ (idle repaint) saat audio berhenti.
  * Idle RAM: $< 120\text{ MB}$.
  * Cold Startup: $< 800\text{ ms}$ hingga window interaktif.
* **Window Size:**
  * Default: Lebar $1152\text{ px}$, Tinggi $768\text{ px}$.
  * Minimum: Lebar $1024\text{ px}$, Tinggi $680\text{ px}$.
  * Maximum: Tidak dibatasi (tampilan memusat secara horizontal pada lebar $> 1440\text{ px}$).

---

## 4. Design Tokens

### 4.1 Token Warna Aksen Modul

| Nama Token | Nilai Base | Nilai Darker (Shadow) | Nilai Glow / Trans | Teks di Atasnya | WCAG AAA Contrast |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `accent-converter` | `#5B9BFA` | `#2D5EA6` | `rgba(91,155,250,0.30)` | `#090B0E` | 9.2:1 (Pass) |
| `accent-separator` | `#FF8A50` | `#B84A17` | `rgba(255,138,80,0.30)` | `#090B0E` | 8.8:1 (Pass) |
| `accent-combiner` | `#6EE795` | `#2EA053` | `rgba(110,231,149,0.30)` | `#090B0E` | 12.1:1 (Pass) |
| `accent-detect` | `#FCD34D` | `#B5911B` | `rgba(252,211,77,0.30)` | `#090B0E` | 14.5:1 (Pass) |
| `accent-pitch` | `#F472B6` | `#AD3071` | `rgba(244,114,182,0.30)` | `#090B0E` | 8.5:1 (Pass) |
| `accent-tempo` | `#2DD4BF` | `#0F8273` | `rgba(45,212,191,0.30)` | `#090B0E` | 11.2:1 (Pass) |
| `accent-trim` | `#FB7185` | `#BA243B` | `rgba(251,113,133,0.30)` | `#090B0E` | 8.1:1 (Pass) |
| `accent-normalize` | `#38BDF8` | `#0C7DB1` | `rgba(56,189,248,0.30)` | `#090B0E` | 10.4:1 (Pass) |
| `accent-info` | `#A78BFA` | `#6341C7` | `rgba(167,139,250,0.30)` | `#090B0E` | 7.9:1 (Pass) |

### 4.2 Token Warna Permukaan & Teks Netral

| Token | Nilai Hex / RGBA | Peruntukan Fungsional |
| :--- | :--- | :--- |
| `bg-app` | `#090B0E` | Background terluar jendela root |
| `surface-card` | `#131720` | Permukaan kartu Bento Grid default |
| `surface-card-hover` | `#181E2A` | Permukaan kartu saat kursor melayang (hover) |
| `surface-rack` | `#11141A` | Chassis kontrol instrumen rack analog |
| `surface-well` | `#0A0C10` | Cekungan/lubang fader, slot deck, dan layar CRT |
| `border-subtle` | `rgba(255, 255, 255, 0.07)` | Border pembagi section dan garis slot |
| `border-card` | `rgba(255, 255, 255, 0.12)` | Border perimeter kartu default |
| `border-card-hover` | `rgba(255, 255, 255, 0.22)` | Border perimeter kartu hover |
| `text-primary` | `#F0F3F8` | Judul, label utama, angka parameter penting |
| `text-secondary` | `#8E9AA8` | Deskripsi modul, satuan unit, label sekunder |
| `text-muted` | `#525D6B` | Label nonaktif, hint shortcut, watermarking |
| `focus-ring` | `#3B82F6` | Garis seleksi fokus keyboard 2px |
| `semantic-error` | `#EF4444` | Pesan galat, LED error, zona bahaya VU meter |
| `semantic-success` | `#22C55E` | LED status selesai, indikator ready |

### 4.3 Dimensi, Radius, Spacing, dan Typo Scale

* **Radius:** `radius-sm: 4px`, `radius-md: 8px`, `radius-lg: 14px`, `radius-full: 9999px`.
* **Spacing:** `space-1: 4px`, `space-2: 8px`, `space-3: 12px`, `space-4: 16px`, `space-5: 20px`, `space-6: 24px`, `space-8: 32px`.
* **Typography:**
  * `title-h1`: Inter SemiBold $18\text{ px}$, line-height $24\text{ px}$.
  * `title-card`: Inter SemiBold $16\text{ px}$, line-height $22\text{ px}$.
  * `body-regular`: Inter Regular $13\text{ px}$, line-height $17\text{ px}$.
  * `body-small`: Inter Regular $11\text{ px}$, line-height $15\text{ px}$.
  * `data-mono-lg`: JetBrains Mono Bold $28\text{ px}$, line-height $32\text{ px}$.
  * `data-mono-md`: JetBrains Mono Medium $14\text{ px}$, line-height $18\text{ px}$.
  * `data-mono-sm`: JetBrains Mono Medium $11\text{ px}$, line-height $14\text{ px}$.

---

## 5. Layout dan Grid

### 5.1 Shell Jendela Terluar

```
+-----------------------------------------------------------------------------------+
| SHELL TITLEBAR: Height 44px (Logo, Window Title, Audio Engine Status Dot)        |
+-----------------------------------------------------------------------------------+
| MAIN VIEWPORT CONTAINER: Height 724px (Fixed at 1152x768 Window Budget)          |
| Margin Top/Bottom: 24px, Left/Right: 32px                                         |
|                                                                                   |
| [QStackedWidget: Index 0 = Bento Grid, Index 1..9 = Dedicated Workspaces]        |
+-----------------------------------------------------------------------------------+
```

### 5.2 Anggaran Vertikal Bento Grid ($1152 \times 768\text{ px}$)

* Lebar Konten Aktif: $1152 - (32 \times 2) = 1088\text{ px}$.
* Grid: 3 Kolom $\times$ 3 Baris.
  * Lebar Kolom: $(1088 - (24 \times 2)) / 3 = 346.6\text{ px}$.
* Tinggi Konten Aktif: $768 - 44\text{ (Titlebar)} - (24 \times 2\text{ Margins}) = 676\text{ px}$.
* Baris Grid (3 Baris):
  * Total Ruang Vertikal: $3 \times 194\text{ px} + 2 \times 20\text{ px (Row Gap)} = 622\text{ px}$.
  * Sisa Ruang Bebas: $676 - 622 = 54\text{ px}$ (didistribusikan merata pada margin container).

```
Perhitungan Presisi Kartu (Total 194px):
+----------------------------------------------------+
| Padding Top: 16px                                  |
| Header Judul Modul: 22px                           |
| Gap Antara: 8px                                    |
| Deskripsi 2-Baris (Word-wrap elided): 34px        |
| Gap Antara: 16px                                   |
| Tombol Mekanik (ChunkyButton): 38px                |
| Offset Clearance Bawah (Shadow travel): 4px        |
| Padding Bottom: 16px                               |
+----------------------------------------------------+
Jumlah = 16 + 22 + 8 + 34 + 16 + 38 + 4 + 16 = 154px (Muat sempurna dalam alokasi 194px)
```

### 5.3 Perilaku Breakpoint

* **Lebar $< 1024\text{ px}$ atau Tinggi $< 680\text{ px}$:** Ditolak oleh sistem (`setMinimumSize(1024, 680)`). Jendela tidak dapat dikecilkan di bawah batas ini.
* **$1024 \times 680\text{ px}$ s/d $1151 \times 767\text{ px}$:** Jendela masuk ke mode Compact Bento. Margin luar mengecil ke $16\text{ px}$, spasi antar kolom mengecil ke $16\text{ px}$, dan tinggi kartu disesuaikan ke $176\text{ px}$.
* **$\ge 1152 \times 768\text{ px}$:** Layout ideal standar. Grid berpusat di tengah viewport (*fixed-width layout* jika monitor berada di atas resolusi $1440\text{ px}$).

---

## 6. Komponen

### 6.1 `ChunkyButton(QPushButton)`
Tombol taktil 3D berbasis custom `paintEvent`.
* **Dimensi:**
  * Launcher: Lebar $100\%$, Tinggi $38\text{ px}$, Radius $8\text{ px}$.
  * Workspace Footer: Lebar Otomatis (min $160\text{ px}$), Tinggi $44\text{ px}$, Radius $8\text{ px}$.
* **Matriks Status:**

| State | Background Body | Bottom Bevel Layer | Y-Offset | Warna Teks |
| :--- | :--- | :--- | :--- | :--- |
| **Default** | `accent-base` | $4\text{ px}$ `accent-darker` | $0\text{ px}$ | `#090B0E` |
| **Hover** | `accent-base` (lightness +4%) | $4\text{ px}$ `accent-darker` | $0\text{ px}$ | `#090B0E` |
| **Pressed / Active** | `accent-base` | $1\text{ px}$ `accent-darker` | $+3\text{ px}$ | `#090B0E` |
| **Focus Visible** | `accent-base` + border 2px `#3B82F6` | $4\text{ px}$ `accent-darker` | $0\text{ px}$ | `#090B0E` |
| **Disabled** | `#202531` | $2\text{ px}$ `#141720` | $0\text{ px}$ | `#525D6B` |

### 6.2 `VUMeterWidget(QWidget)`
Dual-chamber pengukur tegangan audio RMS bergaya analog.
* **Dimensi:** Lebar $320\text{ px}$, Tinggi $180\text{ px}$, Radius $6\text{ px}$.
* **Layer Tumpukan Geometri (Urutan Draw):**
  1. Base Recess Chamber: `#0A0C10` (border $1\text{ px}$ `#000000`).
  2. Dial Face: `QLinearGradient` (Stop 0.0: `#EAD9B4`, Stop 0.85: `#DFCA97`, Stop 1.0: `#CFB478`).
  3. Arc Skala Cetak:
     * Arc $-20\text{ dB}$ s/d $0\text{ dB}$: `#1A1D20`, tebal $1.5\text{ px}$.
     * Arc $0\text{ dB}$ s/d $+3\text{ dB}$: `#D32F2F`, tebal $2.5\text{ px}$.
  4. Pivot Point: Koordinat $X=160.0$, $Y=195.0$.
  5. Jarum Indikator: `QPolygonF` meruncing, warna `#111315`, panjang $155\text{ px}$.
  6. Cap Pivot Cover: Lingkaran diameter $24\text{ px}$, gradasi perak metalik `#5A6270` ke `#1E2229`.
  7. Bevel Glass Glare: Highlight transparan putih diagonal `QLinearGradient` alpha 0.15 ke 0.0.
* **Fisika Gerak Jarum (Ballistics):**
  * Target sudut: $\theta = \text{clip}\left(\frac{\text{dB} + 20}{23} \times 90^\circ - 45^\circ, -45^\circ, +45^\circ\right)$.
  * Pegas: `stiffness = 0.18`, `damping = 0.72`.
  * Fallback Reduced Motion: Jarum bergerak linear tanpa inersia osilasi bounce.

### 6.3 `ConsoleFader(QSlider)`
Slider bergaya mixer analog konsol audio.
* **Dimensi:**
  * Track Vertikal: Lebar $6\text{ px}$, Tinggi $180\text{ px}$, Warna `#080A0D`.
  * Track Horizontal: Tinggi $6\text{ px}$, Lebar $240\text{ px}$, Warna `#080A0D`.
  * Thumb Cap: Vertikal $32 \times 18\text{ px}$, Horizontal $18 \times 32\text{ px}$, Radius $3\text{ px}$.
* **Visual Thumb:** Metalik bertingkat (`#434C5A` ke `#14171C`) dengan 3 garis alur grip pegangan horizontal (`QColor(0, 0, 0, 160)`). Garis indikator tengah berwarna putih solid $1.5\text{ px}$.
* **Interaksi:**
  * Drag klik kiri memanipulasi nilai linear.
  * Double Click (`mouseDoubleClickEvent`) **MUST** seketika mengembalikan fader ke detent default ($0\text{ dB}$, 100%, atau 0 semitone).
  * Scroll Wheel: Menyesuaikan parameter per langkah kecil ($0.1\text{ unit}$).

### 6.4 `CRTScreenWidget(QWidget)`
Layar katoda miniatur untuk terminal status pemrosesan.
* **Dimensi:** Lebar $100\%$, Tinggi $120\text{ px}$, Radius $6\text{ px}$.
* **Layer Tumpukan Geometri:**
  1. Base Glass: Vignette `QRadialGradient` dari `#102418` (pusat) ke `#030805` (tepi).
  2. Scanline Overlay: Garis horizontal genap (`y % 2 == 0`) dengan warna `rgba(0, 0, 0, 0.35)`.
  3. Phosphor Text: Font `JetBrains Mono` $11\text{ px}$ warna `#22C55E`, dirender dua kali (layer bayangan offset $1\text{ px}$ alpha 0.25).
* **Fallback Reduced Motion:** Menghilangkan denyut pendaran phosphor dan efek scanline flicker.

---

## 7. Layar (Screens)

### 7.1 Template Workspace Kontrak 4-Slot

```
+-----------------------------------------------------------------------------------+
| SLOT 1: TOP BAR (Height: 48px, Margin: 0 16px)                                    |
| [<- ESC: DASHBOARD]          MODULE TITLE (16px SemiBold)     [LED: ENGINE READY] |
+-----------------------------------------------------------------------------------+
| SLOT 2: THE DECK / VISUAL STAGE (Height: 210px, Recessed Chassis)                 |
| +-------------------------------------------------------------------------------+ |
| | (Tampilan Waveform / Analog VU Meter Chamber / Multi-Track / Monitor CRT)     | |
| +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
| SLOT 3: HARDWARE CONTROL RACK (Height: 280px, 3 Control Clusters)                 |
| +-------------------------+ +-------------------------+ +-----------------------+ |
| | CLUSTER A: PRIMARY      | | CLUSTER B: SECONDARY    | | CLUSTER C: PRESETS    | |
| +-------------------------+ +-------------------------+ +-----------------------+ |
+-----------------------------------------------------------------------------------+
| SLOT 4: EXECUTION FOOTER (Height: 64px, Fixed Bottom Bar)                         |
| [File: audio_rec_01.wav | 44.1kHz 24-bit]             [Reset]  [ACTION CTA BUTTON]|
+-----------------------------------------------------------------------------------+
```

### 7.2 Spesifikasi 9 Modul Kerja

#### 1. Audio Converter
* **Slot 2 (Deck):** Table list file queue latar `#0A0C10` menampilkan nama file, format asal, estimasi ukuran baru, dan status bar.
* **Slot 3 (Rack):** Format selector mekanik (WAV, MP3, FLAC, AAC), selector Bit Depth (16, 24, 32-float), Sample Rate slider.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#5B9BFA`, label `"Convert Files"`. Shortcut: `Ctrl+Enter`.

#### 2. AI Stem Separator
* **Slot 2 (Deck):** `CRTScreenWidget` menampilkan log isolasi frekuensi dan 4 garis progres gelombang pemisahan trek.
* **Slot 3 (Rack):** 4 Console Fader Vertikal individual (Vocals, Drums, Bass, Other) dengan tombol toggle kancing `[M]` (Mute) dan `[S]` (Solo).
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#FF8A50`, label `"Separate Stems"`. Shortcut: `Ctrl+Enter`.

#### 3. Track Combiner
* **Slot 2 (Deck):** Dual/Quad horizontal waveform stacking canvas dengan indikator tabrakan gain (*clipping alert*).
* **Slot 3 (Rack):** Rotary Pan & Gain balance knob per trek, master output volume knob, toggle switch `[Normalize Master Spikes]`.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#6EE795`, label `"Merge Tracks"`. Shortcut: `Ctrl+Enter`.

#### 4. Key & Tempo Detect
* **Slot 2 (Deck):** Dual Mechanical Flip-Card Display. Kiri: Indikator Key (`"A Minor"`), Kanan: Indikator BPM (`"124.0 BPM"`).
* **Slot 3 (Rack):** Tabel harmoni Camelot Wheel, tombol mekanik `"Tap Tempo"`, tombol `"Copy Analysis"`.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#FCD34D`, label `"Export Key & Tempo"`. Shortcut: `Ctrl+S`.

#### 5. Pitch Shifter
* **Slot 2 (Deck):** Interactive Waveform Stage dengan grid translasi nada semitone.
* **Slot 3 (Rack):** Fader Vertikal Utama rentang $-12$ s/d $+12\text{ Semitones}$ (detent 0), Fine Pitch Knob ($-50$ s/d $+50\text{ Cents}$), toggle `[Preserve Formants]`.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#F472B6`, label `"Shift Pitch"`. Shortcut: `Ctrl+Enter`.

#### 6. Tempo Change
* **Slot 2 (Deck):** Time-Stretch Elastic Waveform Canvas dengan penggaris hitungan birama (Bars/Beats).
* **Slot 3 (Rack):** Fader Horizontal Utama rentang $50\%$ s/d $200\%$ (detent 100%), Spinbox Target BPM langsung, toggle switch `[Lock Pitch]`.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#2DD4BF`, label `"Apply Tempo Change"`. Shortcut: `Ctrl+Enter`.

#### 7. Audio Trim
* **Slot 2 (Deck):** Visual Tape Window Waveform dengan 2 pin geser logam pembatas batas potong (In/Out markers) dan playhead jarum merah.
* **Slot 3 (Rack):** Tuts tape recorder fisik (`[REWIND]`, `[PLAY/PAUSE]`, `[FAST-FWD]`), input numerik start/end timecode (`00:00.000`), switch toggle `[Crossfade 10ms]`.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#FB7185`, label `"Trim Audio"`. Shortcut: `Ctrl+Enter`.

#### 8. Loudness Normalize
* **Slot 2 (Deck):** Dual `VUMeterWidget` Chamber (Kanal L dan Kanal R) terikat RMS audio aktual.
* **Slot 3 (Rack):** 3 Tombol preset target tebal (`"Streaming (-14 LUFS)"`, `"Podcast (-16 LUFS)"`, `"Club Loud (-9 LUFS)"`), pembacaan numerik digital Integrated LUFS dan True Peak dBTP.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#38BDF8`, label `"Normalize Loudness"`. Shortcut: `Ctrl+Enter`.

#### 9. Audio Information
* **Slot 2 (Deck):** Real-time 31-Band FFT Audio Spectrum Analyzer ($20\text{ Hz} - 20\text{ kHz}$) berlatar grid osciloscope.
* **Slot 3 (Rack):** Pelat rack bersekrup memuat rincian audio: format container, exact sample rate, bit depth, channels, bitrate, encoder engine.
* **Slot 4 (Footer):** CTA `ChunkyButton` warna `#A78BFA`, label `"Copy Metadata"`. Shortcut: `Ctrl+C`.

---

## 8. Interaksi dan Motion

### 8.1 Tabel Transisi Animasi

| Pemicu (Trigger) | Properti Terdampak | Durasi | Easing Curve |
| :--- | :--- | :--- | :--- |
| Klik Tombol Launcher | Opacity QStackedWidget | $180\text{ ms}$ | `QEasingCurve.Type.OutCubic` |
| Tekan Tombol `Esc` | Opacity QStackedWidget | $150\text{ ms}$ | `QEasingCurve.Type.OutQuad` |
| Hover Kartu Bento | Border color & Surface BG | $120\text{ ms}$ | `QEasingCurve.Type.Linear` |
| Tekan Tombol 3D | Y-Translate $+3\text{ px}$, Lip $-3\text{ px}$ | $60\text{ ms}$ | `QEasingCurve.Type.OutQuad` |
| Lepas Tombol 3D | Y-Translate $0\text{ px}$, Lip $+4\text{ px}$ | $90\text{ ms}$ | `QEasingCurve.Type.OutBounce` |

### 8.2 Logika Drag and Drop File

* **Hover Over Card:**
  * File Valid (`.wav`, `.mp3`, `.flac`, `.ogg`): Border kartu berganti seketika ke `2px solid var(--accent-base)`, kursor `Qt.DragCopyCursor`.
  * File Invalid (format tak didukung): Border kartu berganti ke `2px solid #EF4444`, kursor `Qt.ForbiddenCursor`.
* **Drop Event:** Window seketika berpindah ke workspace modul terkait dan memicu loading waveform audio.

### 8.3 Umpan Balik Audio (Tactile Audio FX)

* **Tombol Tekan:** Suara klik sakelar mekanik pendek ($12\text{ ms}$, frekuensi tengah $1.8\text{ kHz}$, format uncompressed PCM buffer).
* **Toggle / Detent:** Suara klik relay miniatur ($8\text{ ms}$).
* **Aturan Bunyi:** Volume default $30\%$; opsi pematian audio feedback tersedia via tombol mute global di Titlebar.

---

## 9. Konten dan Microcopy

* **Kapitalisasi:**
  * Judul Tombol & Aksi: **Title Case** (contoh: `"Convert Files"`, `"Separate Stems"`).
  * Label Teknis & Satuan: **Uppercase Monospace** (contoh: `"LUFS"`, `"BPM"`, `"48 KHZ"`, `"MOD-01"`).
  * Deskripsi Kartu: **Sentence case**, maksimal 140 karakter (2 baris).

### 9.1 Whitelist & Blacklist Istilah Teknis

* **WHITELIST (Boleh Tampil):** `LUFS`, `True Peak`, `dBTP`, `BPM`, `Semitone`, `Sample Rate`, `Bit Depth`, `WAV`, `MP3`, `FLAC`, `Stems`, `Crossfade`.
* **BLACKLIST (Dilarang Muncul di UI Kasual):** `MelBand-RoFormer`, `Krumhansl-Schmuckler`, `FFT Window Size`, `Biquad Coefficients`, `Phase Vocoder Hop Length`.

### 9.2 Template Pesan Sistem

* **Error State:**
  * *Template:* `[Apa yang gagal] + [Penyebab ringkas] + [Langkah perbaikan].`
  * *Contoh:* `"Gagal memproses file audio. Format file korup atau terproteksi DRM. Pilih file WAV atau MP3 lain."`
* **Success State:**
  * *Template:* `[Nama operasi] + "berhasil disimpan ke" + [Lokasi direktori].`
  * *Contoh:* `"Normalisasi selesai. File berhasil disimpan ke folder /Export."`

---

## 10. Aksesibilitas

1. **Pemetaan Fokus Keyboard:**
   * Tombol `Tab`: Berpindah maju ke kontrol interaktif berikutnya.
   * Tombol `Shift+Tab`: Berpindah mundur ke kontrol sebelumnya.
   * `Focus Ring`: Kotak garis luar tegas berjarak $2\text{ px}$ dengan warna `#3B82F6` dan tebal $2\text{ px}$.
2. **Navigasi Global:**
   * Tombol `Esc`: Kembali ke Menu Launcher Utama dari workspace manapun.
   * Tombol `Space` / `Enter`: Memicu tombol atau mengaktifkan fader terpilih.
   * Tombol Panah `Up`/`Down`/`Left`/`Right`: Menyesuaikan nilai fader atau knob bertahap.
3. **Indikator Bebas Ketergantungan Warna:**
   * Status error atau warning tidak boleh hanya ditandai dengan lampu merah/kuning; wajib disertai icon SVG tanda seru (`alert-triangle`) dan teks keterangan eksplisit di sebelahnya.

---

## 11. Anti-Pattern (Larangan Eksplisit)

| Pola Terlarang (DILARANG) | Dampak Masalah | Pengganti Wajib yang Benar |
| :--- | :--- | :--- |
| Background Gradasi Ungu-Biru | Merusak tema utilitarian | `#090B0E` pekat dengan surface kartu `#131720` |
| Teks Putih di Tombol Aksen | Gagal kontras rasio WCAG AAA | Teks `#090B0E` tebal (Bold 700) |
| Scrollbar pada Menu Utama 1152x768 | Tampilan terpotong, layout buruk | Budget vertikal $194\text{ px}$ terkunci tanpa scroll |
| Animasi Jarum Timer Random | Menipu pengguna, tidak fungsional | Data binding ke buffer RMS riil via NumPy |
| Knob Putar 360 Derajat untuk Tempo | Kursor canggung bagi kasual | Fader geser linear horizontal atau vertikal |
| Emoji Sebagai Icon Tombol | Mengesankan aplikasi mainan | Lucide Icon format SVG monokrom |

---

## 12. Aset Referensi

* Direktori Penyimpanan: `/reference/`
  * `/reference/dashboard_grid.png`: Screenshot tata letak baku Bento Grid 9 kartu.
  * `/reference/vu_meter_spec.png`: Ilustrasi dial plate, radius pivot, dan sudut busur VU meter.
  * `/reference/button_states.png`: Detail gambar state 3D normal vs tertekan.
* **Resolusi Konflik:** Jika terdapat perbedaan visual antara mockup gambar di `/reference/` dengan nilai numerik di `tokens.json`, maka implementor **MUST** memenangkan nilai numerik `tokens.json`.

---

## 13. Definition of Done & Keputusan Terbuka

### Checklist Verifikasi Selesai (DoD)
* [ ] Antarmuka berjalan 100% pada Python 3.10+ & PySide6 tanpa komponen web.
* [ ] Jendela $1152 \times 768\text{ px}$ bersih tanpa scrollbar pada menu utama.
* [ ] Seluruh tombol aksen kartu menggunakan teks `#090B0E` dengan bobot Bold.
* [ ] Tombol `ChunkyButton` memiliki translasi klik $3\text{ px}$ ke bawah dengan bayangan menyusut ke $1\text{ px}$.
* [ ] Seluruh 9 modul ruang kerja mengimplementasikan hierarki 4-slot terpadu.
* [ ] Gerakan jarum VU meter terhubung dengan buffer RMS audio riil.
* [ ] Tombol `Esc` di seluruh ruang kerja berfungsi kembali ke menu utama.
* [ ] Tidak ada teks deskripsi modul yang melebihi 2 baris atau terpotong kasar tanpa elide.

### Keputusan Terbuka (Open Decisions)

| No | Topik Keputusan | Opsi yang Tersedia | Default Sementara Implementasi | Pengambil Keputusan |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Mesin Pemisahan AI | ONNX Runtime vs PyTorch Lib | ONNX Runtime (ukuran bundle lebih ringkas) | Lead Audio Engineer |
| 2 | Lokasi Penyimpanan File Export | Direktori Asal vs Subfolder `/Export` | Subfolder `/Export` di direktori file sumber | Product Owner |
| 3 | Format Default Rekaman Baru | WAV 24-bit vs FLAC Level 5 | WAV 24-bit (kompatibilitas DAW universal) | Audio Lead |