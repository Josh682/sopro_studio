"""Automated verification suite for Phase 1 (Foundation & Launcher).

Runs offscreen using QT_QPA_PLATFORM=offscreen.
"""

from __future__ import annotations

import os
import sys

# Force offscreen rendering for headless CI / testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_API"] = "pyside6"

from src.ui.qt import (
    QApplication,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QKeyEvent,
    QMimeData,
    QMouseEvent,
    QPainter,
    QPixmap,
    QPoint,
    Qt,
    QUrl,
)

from src.ui.main_window import MainWindow
from src.ui.theme.tokens import TOKENS, hex_to_qcolor
from src.ui.views.launcher_grid import MODULE_DEFINITIONS
from src.ui.widgets.launcher_card import LauncherCard
from src.ui.widgets.tactile_button import TactileButton


def test_token_bridge() -> None:
    print("--- 1. Testing Token Bridge ---")
    assert TOKENS.name == "Audio Quick Toolkit Design Tokens", f"Unexpected name: {TOKENS.name}"
    assert len(TOKENS.colors.accents) == 9, f"Expected 9 accents, got {len(TOKENS.colors.accents)}"

    # Test exact accent values from tokens.json
    expected_accents = {
        "converter": "#5B9BFA",
        "separator": "#FF8A50",
        "combiner": "#6EE795",
        "detect": "#FCD34D",
        "pitch": "#F472B6",
        "tempo": "#2DD4BF",
        "trim": "#FB7185",
        "normalize": "#38BDF8",
        "info": "#A78BFA",
    }
    for key, hex_val in expected_accents.items():
        assert key in TOKENS.colors.accents, f"Missing accent: {key}"
        assert TOKENS.colors.accents[key].base.upper() == hex_val.upper(), f"Mismatch for {key}: {TOKENS.colors.accents[key].base} vs {hex_val}"
        assert isinstance(TOKENS.colors.accents[key].base_qcolor, QColor)
        assert isinstance(TOKENS.colors.accents[key].darker_qcolor, QColor)

    # Test hex and rgba conversion
    c_hex = hex_to_qcolor("#090B0E")
    assert c_hex.name() == "#090b0e"
    c_rgba = hex_to_qcolor("rgba(255, 255, 255, 0.12)")
    assert c_rgba.alpha() == 31  # round(0.12 * 255) = 31

    print("✓ Token bridge loaded and verified all 9 accents and colors.")


def test_tactile_button() -> None:
    print("\n--- 2. Testing TactileButton ---")
    click_fired = False

    def on_click():
        nonlocal click_fired
        click_fired = True

    btn = TactileButton(
        text="Open Converter",
        accent_key="converter",
        face_height=38,
        audio_click_callback=on_click,
    )
    btn.resize(160, 42)

    # Verify initial dimensions
    assert btn.height() == 42, f"Expected total height 42, got {btn.height()}"

    # Verify rendering to offscreen pixmap
    pix = QPixmap(160, 42)
    pix.fill(Qt.GlobalColor.transparent)
    btn.render(pix)

    # Simulate mouse press to test audio hook and travel
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    btn.mousePressEvent(press_event)
    assert click_fired is True, "Audio click callback did not fire on mousePressEvent"

    print("✓ TactileButton rendered successfully with 3D layers and audio callback.")


def test_launcher_card() -> None:
    print("\n--- 3. Testing LauncherCard & Drag-and-Drop ---")
    card = LauncherCard(
        module_id="converter",
        code="[MOD-01]",
        tag="[CONV]",
        title="Audio Converter",
        description="Convert between WAV, MP3, FLAC and AIFF with maximum fidelity.",
        button_text="Open Converter",
        accent_key="converter",
    )
    card.resize(340, 194)

    assert card.height() == 216, f"Expected height 216, got {card.height()}"
    assert card.lbl_title.text() == "Audio Converter"

    # Test Drag & Drop signals
    dropped_result = None

    def on_dropped(mod_id, path):
        nonlocal dropped_result
        dropped_result = (mod_id, path)

    card.file_dropped.connect(on_dropped)

    # Simulate DragEnter with a valid audio file
    mime_valid = QMimeData()
    mime_valid.setUrls([QUrl.fromLocalFile("/path/to/test_audio.wav")])
    drag_enter = QDragEnterEvent(
        QPoint(50, 50),
        Qt.DropAction.CopyAction,
        mime_valid,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.dragEnterEvent(drag_enter)
    assert card._drag_state == "valid", f"Expected drag state 'valid', got {card._drag_state}"

    # Simulate Drop
    drop_event = QDropEvent(
        QPoint(50, 50),
        Qt.DropAction.CopyAction,
        mime_valid,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    card.dropEvent(drop_event)
    assert dropped_result == ("converter", "/path/to/test_audio.wav"), f"Unexpected drop result: {dropped_result}"

    print("✓ LauncherCard Drag-and-Drop native interaction verified.")


def test_main_window_navigation() -> None:
    print("\n--- 4. Testing MainWindow & Stacked Navigation ---")
    win = MainWindow()
    win.resize(1152, 768)

    # 1. Initial State: Must be at index 0 (LauncherGridPage)
    assert win.stack.currentIndex() == 0, f"Expected index 0, got {win.stack.currentIndex()}"
    assert win.width() == 1152 and win.height() == 768
    assert win.minimumWidth() <= 960 and win.minimumHeight() <= 640

    # 2. Test Navigation to Module
    win.navigate_to_module("pitch")
    assert win.stack.currentIndex() == 1, f"Expected index 1 after navigation, got {win.stack.currentIndex()}"
    assert "[MOD-05]  PITCH SHIFTER" in win.page_workspace.lbl_module_header.text()
    assert win.page_workspace.btn_action_cta.text() == "Shift Pitch"

    # 3. Test Global Esc Shortcut
    esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(esc_event)
    assert win.stack.currentIndex() == 0, f"Expected index 0 after Esc key, got {win.stack.currentIndex()}"

    # 4. Test Navigation with File Drop
    win.navigate_to_module_with_file("normalize", "/music/track_01.flac")
    assert win.stack.currentIndex() == 1
    assert "[MOD-08]  LOUDNESS NORMALIZE" in win.page_workspace.lbl_module_header.text()
    assert "track_01.flac" in win.page_workspace.lbl_file_pill.text()
    assert win.page_workspace.btn_action_cta.text() == "Normalize Loudness"

    # Esc back to launcher
    win.keyPressEvent(esc_event)
    assert win.stack.currentIndex() == 0

    print("✓ MainWindow shell, 4-slot workspace template, and Esc shortcut verified.")


def test_manual_file_selection():
    print("\n--- 5. Testing Manual Audio File Selection Across All 9 Modules ---")
    win = MainWindow()

    # 1. Verify every single module card has a manual Browse button
    launcher = win.page_launcher
    for mod in MODULE_DEFINITIONS:
        card = launcher.get_card(mod["id"])
        assert card is not None, f"Card {mod['id']} missing from launcher"
        assert hasattr(card, "btn_browse"), f"Card {mod['id']} missing manual browse button"
        assert "Browse" in card.btn_browse.text()

    print("✓ All 9 Bento Grid module cards have dedicated manual 'Browse' buttons.")

    # 2. Verify WorkspacePage manual file selection components
    ws = win.page_workspace
    assert hasattr(ws, "btn_browse"), "WorkspacePage missing manual btn_browse"
    assert "Browse" in ws.btn_browse.text()
    assert hasattr(ws, "interactive_deck"), "WorkspacePage missing interactive_deck"
    assert hasattr(ws, "lbl_file_pill"), "WorkspacePage missing clickable lbl_file_pill"

    # 3. Test loading single file manually
    test_file = "/audio/sample_master.wav"
    for mod in MODULE_DEFINITIONS:
        ws.configure_module(mod)
        assert "NO FILE LOADED" in ws.lbl_file_pill.text()

        ws.load_file(test_file)
        assert "sample_master.wav" in ws.lbl_file_pill.text()
        assert ws.interactive_deck.lbl_title.text() == "sample_master.wav"
        assert ws.lbl_deck_badge.text() == "BUFFER LOADED"

    # 4. Test loading multiple files (batch modules)
    batch_files = ["/audio/stem_vocals.wav", "/audio/stem_drums.wav", "/audio/stem_bass.wav"]
    ws.load_files(batch_files)
    assert "3 FILES" in ws.lbl_file_pill.text()
    assert "3 Audio Files Selected" in ws.interactive_deck.lbl_title.text()

    # 5. Test reset defaults / clear file buffer
    ws.reset_file_and_params()
    assert "NO FILE LOADED" in ws.lbl_file_pill.text()
    assert ws.interactive_deck.lbl_title.text() == "Select Audio File"
    assert ws.lbl_deck_badge.text() == "READY"

    print("✓ WorkspacePage interactive deck, footer browse button, and batch file buffer verified.")


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    test_token_bridge()
    test_tactile_button()
    test_launcher_card()
    test_main_window_navigation()
    test_manual_file_selection()

    print("\n==========================================")
    print("ALL PHASE 1 ARCHITECTURE TESTS PASSED! 🎉")
    print("==========================================")


if __name__ == "__main__":
    main()

