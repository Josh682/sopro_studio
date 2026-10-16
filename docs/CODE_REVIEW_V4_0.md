# Laporan Code Review: Audit Logic Leak & Spesifikasi Implementasi V4.0

> **Tanggal Audit:** 2 Oktober 2026  
> **Target Commit:** [`b5eaa1b`](https://github.com/Josh682/sopro_studio/commit/b5eaa1bbe6e705566d8722f40c4b60f3ad909e54) (*feat(v4.0): implement Audio Enhancement and Restoration suite*)  
> **Cakupan Review:**  
> - `src/core/processors/base_enhancement_processor.py`  
> - `src/core/processors/declip_processor.py`  
> - `src/core/processors/denoise_processor.py`  
> - `src/core/processors/dereverb_processor.py`  
> - `src/core/processors/voice_enhancement_processor.py`  
> - `src/core/processors/restoration_processor.py`  
> - `src/gui/*_page.py` (Declip, Denoise, Dereverb, Voice Enhancement, Restoration)  
> - `src/gui/main_window.py`, `src/workers/processor_worker.py`  
> - Spesifikasi dokumen di `docs/V4.0/` (`AIDenoise.md`, `AIDereverb.md`, `AudioRestoration.md`, `Declip.md`, `VoiceEnhancement.md`)  

---

## 1. Ringkasan Eksekutif

Audit ini dilakukan untuk mengevaluasi kualitas implementasi, integritas logika pemrosesan audio (*logic leak*), stabilitas konkurensi (pembatalan/threading), serta keselarasan antara kode yang diimplementasikan pada v4.0 dengan spesifikasi teknis awal.

Secara umum, implementasi v4.0 berhasil menyediakan antarmuka pengguna GUI yang konsisten dengan tema Catppuccin dan integrasi sidebar collapsible. Namun, ditemukan **3 cacat kritis (Critical)**, **6 peringatan penting (Warning)**, dan **kesenjangan arsitektur fundamental (Architectural Spec Gap)** antara klaim fitur AI dengan realisasi kode DSP klasik.

---

## 2. Matriks Temuan & Klasifikasi Keparahan

| ID | Kategori | Komponen | Deskripsi Singkat | Tingkat Keparahan |
| :--- | :--- | :--- | :--- | :--- |
| **LOG-01** | Algoritma DSP | `DenoiseProcessor` | Blind 60Hz Notch Filtering pada setelan default `Auto` tanpa deteksi hum | 🔴 **Critical** |
| **LOG-02** | Array Logic | `AudioRestorationProcessor` | Boundary edge detection bug pada De-click & Dropout Inpainting | 🔴 **Critical** |
| **STA-01** | Threading/State | `BaseEnhancementProcessor` | False success reporting saat operasi dibatalkan oleh pengguna | 🔴 **Critical** |
| **LOG-03** | Windowing/Memory | `BaseEnhancementProcessor` | Kesalahan matematis windowing Hann & dead code pada `process_in_chunks` | 🟡 **Warning** |
| **LOG-04** | Dinamika Audio | `VoiceEnhancementProcessor` | Ambang batas global percentile 75 pada De-Esser merusak dinamika suara | 🟡 **Warning** |
| **LOG-05** | DSP / Akustik | `DereverbProcessor` | Laju peluruhan (*decay rate*) reverb bergantung pada Sample Rate | 🟡 **Warning** |
| **LOG-06** | Interpolasi | `DeclipProcessor` | Kontaminasi sampel terklip tetangga pada jendela konteks Cubic Spline | 🟡 **Warning** |
| **LOG-07** | Multichannel | `AudioRestorationProcessor` | Slicing stereo hardcoded `[:, 0]` & `[:, 1]` memicu crash pada mono/surround | 🟡 **Warning** |
| **STA-02** | Threading/Buffer | `DeclipProcessor` | Ketidaksesuaian dimensi channel saat pembatalan di tengah channel stereo | 🟡 **Warning** |
| **GUI-01** | Logging Bridge | `MainWindow` | Broadcast log handler mencemari seluruh tab halaman aplikasi | 🟡 **Warning** |
| **GAP-01** | Spesifikasi | Arsitektur V4.0 | Ketiadaan PyTorch AI backends & `EnhancementManager` sesuai spesifikasi | 🔵 **Architecture Gap** |

---

## 3. Rincian Temuan Kategori 1: Logic Leaks & Algorithmic Flaws

### 🔴 LOG-01: Blind 60Hz Notch Filtering pada Denoise Mode "Auto"
* **File:** `src/core/processors/denoise_processor.py` (Baris 176–184)
* **Kode:**
  ```python
  # Step 1: Handle ground hum
  if noise_type in ["hum_50hz", "hum_60hz"] or noise_type == "auto":
      fund = 50.0 if noise_type == "hum_50hz" else 60.0
      if on_progress:
          on_progress(0.25, f"Filtering electrical hum ({fund:.0f}Hz)...")
      processed = apply_hum_notch(processed, sr=sr, fundamental=fund)
  ```
* **Akar Masalah:**
  Pada profil bawaan `auto`, sistem mengasumsikan frekuensi dasar adalah 60 Hz tanpa melakukan analisis spektral (FFT magnitude check). Filter notch ber-Q tinggi langsung memotong frekuensi 60 Hz, 120 Hz, 180 Hz, 240 Hz, 300 Hz, 360 Hz, 420 Hz, dan 480 Hz.
* **Dampak:**
  - Jika audio direkam di kawasan 50 Hz (Eropa, Asia, Indonesia), dengung listrik 50 Hz tetap lolos.
  - Memotong nada-nada musik instrumen bass yang berada di sekitar 60 Hz (misal nada B1 ≈ 61.74 Hz) dan harmoniknya secara buta pada setiap audio yang diproses.
* **Rekomendasi Perbaikan:**
  Hitung rasio energi spektrum pada bin 50 Hz dan 60 Hz terhadap noise floor rata-rata. Hanya aktifkan `apply_hum_notch` jika terdeteksi lonjakan energi (> 12 dB di atas lantai noise lokal).

---

### 🔴 LOG-02: Boundary Detection Logic Bug pada Declick & Inpaint Dropouts
* **File:** `src/core/processors/restoration_processor.py` (Baris 64–69 dan 110–115)
* **Kode:**
  ```python
  starts = np.where(np.diff(click_mask.astype(int)) == 1)[0] + 1
  ends = np.where(np.diff(click_mask.astype(int)) == -1)[0] + 1

  if len(starts) > 0 and len(ends) > 0:
      if starts[0] > ends[0]:
          starts = np.insert(starts, 0, 0)
      if len(starts) > len(ends):
          ends = np.append(ends, len(x))
  ```
* **Akar Masalah:**
  Kondisi `if len(starts) > 0 and len(ends) > 0` mengharuskan *kedua* array transisi memiliki elemen. Apabila artefak (klik impulsif atau dropout) berada persis di awal file (sampel ke-0) dan tidak ada transisi naik lainnya di sisa file, maka `starts` kosong (`len == 0`), sementara `ends` memiliki 1 elemen. Akibatnya, seluruh blok `if` dilewati.
* **Dampak:**
  Klik atau dropout di sampel pertama atau akhir file tidak pernah diperbaiki (`zip(starts, ends)` menghasilkan zero iteration).
* **Rekomendasi Perbaikan:**
  Gunakan logika penanganan batas array yang konsisten seperti pada `declip_processor.py`:
  ```python
  if click_mask[0]:
      starts = np.insert(starts, 0, 0)
  if click_mask[-1]:
      ends = np.append(ends, len(x))
  ```

---

### 🟡 LOG-03: Kesalahan Matematis Windowing & Dead Code pada `process_in_chunks`
* **File:** `src/core/processors/base_enhancement_processor.py` (Baris 132–210)
* **Kode:**
  ```python
  chunk_size = int(chunk_len_sec * sr)
  overlap = int(overlap_sec * sr)
  step = max(1, chunk_size - overlap)
  window = np.hanning(chunk_size).astype(np.float32)
  ...
  output[start:end] += processed_chunk * win
  norm_weights[start:end] += norm_win
  ...
  output[nonzero_mask] /= norm_weights[nonzero_mask]
  ```
* **Akar Masalah:**
  1. Jendela Hann hanya memenuhi kondisi rekonstruksi sempurna (*Constant Overlap-Add / COLA*) jika overlap adalah 50% atau 75%. Dengan `chunk_size = 8.0s` dan `overlap = 0.5s` (overlap hanya ~6%), bobot `window` di dekat ujung bernilai mendekati nol. Pembagian `output / norm_weights` di wilayah tepi menyebabkan ketidakstabilan numerik tinggi, modulasi volume tak wajar, serta penghapusan sampel awal file karena `norm_weights < 1e-6`.
  2. Fungsi ini berstatus **dead code** karena tidak pernah dipanggil oleh kelima prosesor v4.0. Seluruh prosesor memproses audio utuh dalam 1 blok array array STFT/SciPy besar, membuka celah lonjakan RAM ekstrem pada file panjang beresolusi tinggi.
* **Rekomendasi Perbaikan:**
  Ubah algoritma chunking agar menerapkan crossfade segitiga/sinus hanya pada interval overlap `[0, overlap]` (bukan jendela Hann di seluruh blok 8 detik), lalu sambungkan panggilan ini ke seluruh prosesor turunan.

---

### 🟡 LOG-04: Ambang Batas Global Percentile pada De-Esser
* **File:** `src/core/processors/voice_enhancement_processor.py` (Baris 104–107)
* **Kode:**
  ```python
  thresh = np.percentile(active_env, 75)
  excess = np.maximum(0.0, env - thresh)
  attenuation = np.clip(1.0 - (excess / (thresh + 1e-5)) * (strength * 1.5), 0.25, 1.0)
  ```
* **Akar Masalah:**
  Perhitungan ambang batas desisan menggunakan persentil ke-75 dari seluruh durasi file audio secara global.
* **Dampak:**
  - Jika rekaman memiliki rentang dinamis luas (ada bagian bisik dan bagian teriak), pada bagian keras semua vokal dan konsonan akan melampaui `thresh` global dan diredam terus-menerus, memicu efek artikulasi cadel (*lisping/dulling*).
  - Pada bagian bicara pelan, desisan sibilan tidak mampu menembus ambang batas global sehingga tidak dibersihkan sama sekali.
* **Rekomendasi Perbaikan:**
  Gunakan detektor amplop lokal (*envelope follower*) dengan waktu reaksi *attack* (~1-2 ms) dan *release* (~20-50 ms) atau gunakan perbandingan energi pita sibilansi (6-11 kHz) relatif terhadap energi pita vokal tengah (1-4 kHz).

---

### 🟡 LOG-05: Laju Peluruhan (*Decay Rate*) Reverb Bergantung pada Sample Rate
* **File:** `src/core/processors/dereverb_processor.py` (Baris 68)
* **Kode:**
  ```python
  running_tail = np.maximum(running_tail * decay_factor, cur_mag * 0.15)
  ```
* **Akar Masalah:**
  `decay_factor` (misal 0.82) dikalikan setiap langkah hop STFT (`hop_length = 512`). 
  - Pada $f_s = 44.1\text{ kHz}$, durasi 1 frame adalah $512 / 44100 \approx 11.6\text{ ms}$.
  - Pada $f_s = 96.0\text{ kHz}$, durasi 1 frame adalah $512 / 96000 \approx 5.3\text{ ms}$.
* **Dampak:**
  Pada file 96 kHz, estimasi ekor reverb meluruh 2.2 kali lebih cepat dibandingkan file 44.1 kHz untuk durasi waktu fisik yang sama. Karakteristik dereverb menjadi tidak konsisten jika pengguna memproses file audio dengan sample rate berbeda.
* **Rekomendasi Perbaikan:**
  Normalisasi faktor peluruhan terhadap waktu absolut:
  ```python
  frame_time = hop_length / sr
  decay_factor = np.exp(-frame_time / target_rt60)
  ```

---

### 🟡 LOG-06: Kontaminasi Konteks pada Declip Spline
* **File:** `src/core/processors/declip_processor.py` (Baris 56–63)
* **Kode:**
  ```python
  ctx_start = max(0, start - context_samples)
  ctx_end = min(len(audio), end + context_samples)
  valid_indices = np.concatenate([np.arange(ctx_start, start), np.arange(end, ctx_end)])
  valid_values = audio[valid_indices]
  ```
* **Akar Masalah:**
  Jendela konteks `valid_indices` mengasumsikan sampel tetangga sebelum dan sesudah area klip selalu valid. Jika ada dua klip yang hanya berjarak 2–4 sampel (klip berulang pada sinyal yang terkompresi keras), sampel flat-topped klip kedua akan masuk sebagai data latih interpolasi spline.
* **Rekomendasi Perbaikan:**
  Saring `valid_indices` dengan mengecualikan indeks yang memenuhi `np.abs(audio) >= threshold`.

---

### 🟡 LOG-07: Slicing Channel Stereo Hardcoded pada AudioRestoration
* **File:** `src/core/processors/restoration_processor.py` (Baris 216–222)
* **Kode:**
  ```python
  if processed.ndim == 2:
      ch0 = repair_clipping_spline(processed[:, 0])
      ch1 = repair_clipping_spline(processed[:, 1])
      processed = np.column_stack([ch0, ch1])
  ```
* **Akar Masalah:**
  Asumsi kaku bahwa array 2 dimensi pasti memiliki tepat 2 channel.
* **Dampak:**
  - Jika file adalah mono 2D `(N, 1)`, pemanggilan `processed[:, 1]` akan melempar `IndexError`.
  - Jika file adalah audio multichannel (surround 5.1 / 6 channel), channel ke-2 hingga ke-5 akan hilang.
* **Rekomendasi Perbaikan:**
  Gunakan iterasi `for ch in range(processed.shape[1])` dan susun kembali menggunakan `np.column_stack`.

---

## 4. Rincian Temuan Kategori 2: State, Threading & Cancellation Leaks

### 🔴 STA-01: False Success Reporting saat Pembatalan
* **File:** `src/core/processors/base_enhancement_processor.py` (Baris 45–47, 56–58, 70–72) & `src/workers/processor_worker.py` (Baris 91–94)
* **Akar Masalah:**
  Ketika pengguna menekan tombol **Cancel**, `BaseEnhancementProcessor.process_file()` mereturn `input_path` asli:
  ```python
  if cancel_flag and cancel_flag.is_set():
      return input_path
  ```
  Di dalam `ProcessorWorker`:
  ```python
  out_path = self._processor.process_file(...)
  if out_path:
      results[input_path] = out_path
      self.signals.log.emit(f"Processed: {out_path.name}")
  ```
* **Dampak:**
  Sistem menganggap pembatalan sebagai proses yang sukses, memunculkan log `Processed: <nama_file>`, dan memasukkan file mentah yang belum selesai diproses ke dalam daftar hasil konversi.
* **Rekomendasi Perbaikan:**
  Kembalikan `None` jika terjadi pembatalan, dan periksa di worker `if out_path is not None:`.

---

### 🟡 STA-02: Kerusakan Dimensi Channel saat Cancel di Declip
* **File:** `src/core/processors/declip_processor.py` (Baris 220–250)
* **Akar Masalah:**
  Jika tombol Cancel ditekan saat memproses channel 1 dari file stereo, loop `for ch in range(channels):` terputus via `break`. Variabel `repaired_channels` hanya berisi 1 channel. Kode kemudian menjalankan `np.column_stack(repaired_channels)` yang menghasilkan shape `(N, 1)`. Namun pada metadata audio, `channels` tercatat 2, sehingga engine ekspor melempar eksepsi *dimension mismatch*.

---

### 🟡 GUI-01: Cross-Tab Log Broadcast Contamination
* **File:** `src/gui/main_window.py` (Baris 212–219)
* **Akar Masalah:**
  Handler `QtLogHandler` dihubungkan secara membabi buta ke `_log_panel.append_log` dari seluruh 14 halaman:
  ```python
  for key in ["converter", "separator", ..., "declip", "denoise", "dereverb", "voice_enhancement", "restoration"]:
      if key in self._pages and hasattr(self._pages[key], "_log_panel"):
          self._log_handler.log_message.connect(self._pages[key]._log_panel.append_log)
  ```
* **Dampak:**
  Setiap log eksekusi dari satu modul (misal Declip) akan muncul serempak di konsol halaman lain (misal Vocal Separator, Trimmer, Metadata Editor), membingungkan pengguna saat membuka tab lain.

---

## 5. Rincian Temuan Kategori 3: Spec vs Implementation Gap

Terdapat perbedaan mendasar antara dokumen perencanaan arsitektur di `docs/V4.0/` dengan kode aktual yang ditulis pada commit `b5eaa1b`:

| Modul | Rancangan Spesifikasi Teknis (`docs/V4.0/`) | Realisasi Kode (`src/core/processors/`) | Status |
| :--- | :--- | :--- | :--- |
| **AI Denoise** | Backend modular (Demucs Noise Model, RNNoise, Whisper-style) dengan lazy loading via `EnhancementManager` | STFT spectral subtraction biasa (15th percentile) + filter notch IIR statis | ❌ Tidak ada PyTorch/AI model |
| **AI Dereverb** | Deep Learning Model (BS-RoFormer Dereverb `models/bs_roformer_dereverb.pt` / MDX-Net) | Estimasi amplop energi ekor recursive satu kutub (*one-pole*) + Wiener gain mask | ❌ Tidak ada neural model separation |
| **Voice Enhancement** | Model inferensi TorchScript PyTorch MPS/CUDA dengan dynamic spectral mask | Filter statis `iirpeak` (dip 340 Hz, boost 3.2 kHz) + dynamic bandpass Butterworth | ❌ Murni filter DSP klasik |
| **Audio Restoration** | Inpainting Autoregresif RNN + PLL time-warping wow/flutter + model super-resolusi | Cubic spline sederhana + spectral subtraction | ⚠️ Wow/Flutter belum diimplementasikan |

> **Catatan Kritis:** Penamaan kelas, parameter, dan UI yang menyertakan label *"AI"* (seperti `AI Denoise`, `AI Dereverb`) saat ini secara teknis belum akurat karena seluruh pemrosesan menggunakan algoritma DSP klasik (*heuristic mathematical filtering*).

---

## 6. Rekomendasi Rencana Aksi (Action Plan)

1. **Prioritas 1 (Stabilitas & Logika Kritis)**:
   - Tambahkan deteksi frekuensi spektral sebelum memotong hum pada `DenoiseProcessor`.
   - Perbaiki penanganan array `starts` dan `ends` pada `declick_audio` dan `inpaint_dropouts` di `restoration_processor.py`.
   - Ubah `process_file` di `BaseEnhancementProcessor` agar mereturn `None` jika dibatalkan, dan sesuaikan `ProcessorWorker`.
2. **Prioritas 2 (Kualitas Pemrosesan Audio)**:
   - Ganti persentil global 75 pada de-esser dengan detektor amplop berbasis waktu nyata (*time-domain dynamic gain computer*).
   - Normalisasikan parameter `decay_factor` di dereverb terhadap sample rate.
   - Saring sampel terklip tetangga pada konteks interpolasi spline `declip_processor.py`.
   - Ubah slicing channel di `AudioRestorationProcessor` menjadi dinamis `range(channels)`.
3. **Prioritas 3 (Arsitektur & Spesifikasi)**:
   - Implementasikan jendela crossfade chunking yang benar pada `process_in_chunks` dan terapkan pada semua prosesor v4.0.
   - Sinkronkan dokumen spesifikasi atau rencanakan integrasi model ONNX/PyTorch dereverb dan denoise untuk fase berikutnya jika ingin mempertahankan branding "AI".
   - Isolasi logging bridge agar log hanya dikirimkan ke halaman modul yang sedang aktif memproses audio.
