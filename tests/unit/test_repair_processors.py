"""Unit tests for Clip & Click Repair module and Enhancement Processors.

Verifies:
1. DeclipProcessor.process_file executes cleanly without NameError ('Path' is defined).
2. AudioRestorationProcessor.process_file executes cleanly without NameError.
3. VoiceEnhancementProcessor.process_file executes cleanly without NameError.
4. DenoiseProcessor.process_file executes cleanly without NameError.
5. DereverbProcessor.process_file executes cleanly without NameError.
6. WorkspacePage Clip & Click Repair Chain executes end-to-end.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from src.ui.qt import QApplication
from src.core.processors.declip_processor import DeclipProcessor
from src.core.processors.restoration_processor import AudioRestorationProcessor
from src.core.processors.voice_enhancement_processor import VoiceEnhancementProcessor
from src.core.processors.denoise_processor import DenoiseProcessor
from src.core.processors.dereverb_processor import DereverbProcessor
from src.ui.views.workspace_template import WorkspacePage

app = QApplication.instance()
if app is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)


class TestRepairAndEnhancementProcessors(unittest.TestCase):
    """Test suite verifying file processing in declip, restoration, and enhancement processors."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.out_dir = self.tmp_path / "output"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # Generate a small 0.5-second test audio with slight clipping
        self.sr = 22050
        t = np.linspace(0, 0.5, int(self.sr * 0.5), endpoint=False)
        sig = 1.2 * np.sin(2 * np.pi * 300 * t)  # exceeds 1.0 (clipped)
        sig = np.clip(sig, -0.99, 0.99)
        self.test_wav = (self.tmp_path / "test_clipped.wav").resolve()
        sf.write(str(self.test_wav), sig.astype(np.float32), self.sr)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_declip_process_file(self) -> None:
        """Verify DeclipProcessor.process_file executes without NameError: Path."""
        declip = DeclipProcessor()
        out = declip.process_file(
            self.test_wav,
            output_dir=self.out_dir,
            options={"threshold": 0.95},
        )
        self.assertTrue(out.exists())
        self.assertIn("declip", out.name.lower())

    def test_restoration_process_file(self) -> None:
        """Verify AudioRestorationProcessor.process_file executes without NameError: Path."""
        resto = AudioRestorationProcessor()
        out = resto.process_file(
            self.test_wav,
            output_dir=self.out_dir,
            options={"target_artifacts": ["digital_glitch"], "restoration_strength": 0.5},
        )
        self.assertTrue(out.exists())
        self.assertIn("restoration", out.name.lower())

    def test_voice_enhancement_process_file(self) -> None:
        """Verify VoiceEnhancementProcessor.process_file executes without NameError: Path."""
        enh = VoiceEnhancementProcessor()
        out = enh.process_file(
            self.test_wav,
            output_dir=self.out_dir,
            options={"target_use": "podcast", "clarity_strength": 0.5},
        )
        self.assertTrue(out.exists())
        self.assertIn("voice", out.name.lower())

    def test_denoise_process_file(self) -> None:
        """Verify DenoiseProcessor.process_file executes without NameError: Path."""
        denoise = DenoiseProcessor()
        out = denoise.process_file(
            self.test_wav,
            output_dir=self.out_dir,
            options={"noise_type": "auto", "strength": 0.5},
        )
        self.assertTrue(out.exists())
        self.assertIn("denoise", out.name.lower())

    def test_dereverb_process_file(self) -> None:
        """Verify DereverbProcessor.process_file executes without NameError: Path."""
        dereverb = DereverbProcessor()
        out = dereverb.process_file(
            self.test_wav,
            output_dir=self.out_dir,
            options={"amount": "moderate", "preserve_warmth": True},
        )
        self.assertTrue(out.exists())
        self.assertIn("dereverb", out.name.lower())

    def test_repair_chain_in_workspace(self) -> None:
        """Verify WorkspacePage runs the Clip & Click Repair Chain end-to-end."""
        from unittest.mock import patch
        from src.utils.config import AppConfig

        with patch.object(AppConfig, "output_dir", self.out_dir):
            workspace = WorkspacePage()
            workspace.show()

            mod_info = {
                "id": "repair",
                "code": "[MOD-07]",
                "tag": "[REPR]",
                "title": "Clip & Click Repair",
                "button_text": "Open Repair",
                "action_text": "Repair Audio",
                "accent_key": "tempo",
            }
            workspace.configure_module(mod_info, str(self.test_wav))

            # Engage inpaint_clicks option to trigger the dual chain
            inpaint_ctrl = workspace._rack_controller.controls.get("inpaint_clicks")
            if inpaint_ctrl and hasattr(inpaint_ctrl, "setChecked"):
                inpaint_ctrl.setChecked(True)

            workspace.execute_action()
            self.assertIsNotNone(workspace._current_task)

            # Wait for task completion
            import time
            start_t = time.time()
            while not workspace._current_task.is_finished and time.time() - start_t < 10.0:
                app.processEvents()
                time.sleep(0.05)

            self.assertTrue(workspace._current_task.is_finished)
            self.assertEqual(workspace._current_task.status.value, "completed")
            self.assertIsNotNone(workspace._last_output_file)
            self.assertTrue(Path(workspace._last_output_file).exists())

            workspace.deleteLater()


if __name__ == "__main__":
    unittest.main()
