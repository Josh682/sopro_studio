# Sound Processor Roadmap

## Overview

| Version | Theme | Status | Description |
| :--- | :--- | :--- | :--- |
| **Foundation** | Infra/Architecture | Done | Core architecture, UI framework, and audio engine scaffolding. |
| **V1.0** | Core Audio | Done | Standard DSP, format conversions, and batch processing essentials. |
| **V2.0** | Music Processing | Not Started | Advanced music-specific AI features like stem separation and analysis. |
| **V3.0** | Audio Utilities | Not Started | Essential tools for restoration, noise reduction, and dynamics. |
| **V4.0** | AI Enhancement | Not Started | Cutting-edge AI capabilities for upscaling and smart suggestions. |

---

## Foundation: Infrastructure & Architecture
**Theme:** Laying the groundwork for a robust, scalable, and beautiful application.
**Goal:** Establish the core application skeleton, data models, and UI paradigms.
**Status:** Done

### Features
- [x] Project Structure
- [x] Audio Engine (Loader/Writer/Metadata)
- [x] Export Engine
- [x] Configuration System
- [x] Logging System
- [x] UI Framework (PyQt6 with Catppuccin Mocha theme)
- [x] Threading Model (Background workers for processing)
- [x] Error Handling & Crash Reporting
- [x] Processor Framework (Plugin-style architecture for audio tasks)

**Notes:** Focus on stability and extensibility. The Processor Framework must support both standard DSP and heavy AI models seamlessly.

---

## V1.0: Core Audio
**Theme:** Essential audio preparation and batch processing.
**Goal:** Deliver a functional product that solves immediate, everyday audio management tasks.
**Status:** Done

### Features
- [x] Format Conversion (WAV, MP3, FLAC, OGG, AAC)
- [x] Sample Rate Conversion
- [x] Bit Depth Conversion
- [x] Channel Conversion (Mono/Stereo)
- [x] Loudness Normalization (EBU R128)
- [x] Silence Trimming
- [x] Batch Processing UI & Queue Management

**Notes:** This release must prove the "batch-first" design philosophy. The UI needs to handle large lists of files gracefully.

---

## V2.0: Music Processing
**Theme:** AI-powered tools for music producers.
**Goal:** Introduce advanced machine learning models to analyze and deconstruct musical audio.
**Status:** Not Started

### Features
- [ ] Stem Separation (Integration of MelBand RoFormer & BS-RoFormer)
- [ ] BPM Detection
- [ ] Key Detection
- [ ] Beat Grid Alignment
- [ ] Audio Stretching / Pitch Shifting

**Notes:** Model loading and inference can be resource-intensive. Ensure the Threading Model from the Foundation phase handles these tasks without freezing the UI.

---

## V3.0: Audio Utilities
**Theme:** Restoration and mixing preparation.
**Goal:** Provide tools to clean up and prepare rough audio for professional mixing or broadcast.
**Status:** Not Started

### Features
- [ ] Noise Reduction
- [ ] Dynamic Range Compression
- [ ] EQ Presets
- [ ] Reverb Removal
- [ ] Audio Repair / Declip

**Notes:** Focus on parameter simplification. These tools should provide great results with minimal tweaking, leaning on sensible defaults and AI analysis where possible.

---

## V4.0: AI Enhancement
**Theme:** Next-generation audio intelligence.
**Goal:** Implement cutting-edge AI features that push the boundaries of offline audio processing.
**Status:** Not Started

### Features
- [ ] AI Upscaling (Bandwidth extension for low-res audio)
- [ ] AI Mastering Suggestions
- [ ] AI Tagging / Classification (Instruments, Mood, Genre)
- [ ] AI Scene Detection for Video Audio

**Notes:** These features represent the "North Star" vision and will require significant R&D.

---

## Guiding Principles
- **Non-destructive:** Original files are never modified or overwritten.
- **Batch-first:** The application must excel at processing 1,000 files just as easily as 1 file.
- **AI-native:** AI is central to the feature set, not a gimmick.
- **Modular:** The processor architecture must allow for easy addition of new DSP or AI tasks.
- **macOS-first:** Developed and optimized primarily for macOS, ensuring native feel and performance.

## Release Timeline Notes
*All dates are approximate and subject to change based on R&D progress.*
- **Foundation:** Current focus.
- **V1.0:** Expected shortly after Foundation stability.
- **V2.0 - V4.0:** Rolling releases, prioritizing features based on user feedback and model availability.
