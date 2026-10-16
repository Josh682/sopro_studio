"""Dynamic stem badge preview widget driven by model metadata."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

#: Dynamic mapping of stem names to distinct indicator color codes
STEM_COLORS: dict[str, str] = {
    "vocals": "#89b4fa",        # Blue
    "instrumental": "#a6e3a1",  # Green
    "drums": "#f38ba8",         # Red
    "bass": "#f9e2af",          # Yellow
    "other": "#cba6f7",         # Mauve
    "piano": "#eeba90",         # Peach
    "guitar": "#89dceb",        # Sky
    "clean": "#a6e3a1",         # Green
    "residual": "#94e2d5",      # Teal
}


class StemPreviewWidget(QWidget):
    """Visual panel showing badge chips for target output stems.

    Rebuilds dynamically when the current model is changed, helping users see
    exactly what files will be produced prior to separation.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        # Header label
        header = QLabel("Output Stems")
        header.setStyleSheet("color: #cdd6f4; font-weight: 600; font-size: 13px;")
        self._layout.addWidget(header)

        # Container for the badge list
        self._badge_container = QWidget()
        self._badge_layout = QHBoxLayout(self._badge_container)
        self._badge_layout.setContentsMargins(0, 0, 0, 0)
        self._badge_layout.setSpacing(8)
        self._badge_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self._layout.addWidget(self._badge_container)
        self._badges: list[QWidget] = []

    def update_stems(self, stem_names: tuple[str, ...]) -> None:
        """Clear existing badges and build new ones dynamically.

        Args:
            stem_names: Tuple of stem labels from ModelMetadata.
        """
        # Delete old widgets
        for badge in self._badges:
            self._badge_layout.removeWidget(badge)
            badge.deleteLater()
        self._badges.clear()

        # Build fresh badges
        for name in stem_names:
            badge = QWidget()
            badge_lay = QHBoxLayout(badge)
            badge_lay.setContentsMargins(10, 4, 10, 4)
            badge_lay.setSpacing(6)

            # Determine indicator dot color
            color = STEM_COLORS.get(name.lower(), "#bac2de")

            # Colored indicator dot
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background-color: {color}; border-radius: 4px;"
            )

            # Text label
            label = QLabel(name.capitalize())
            label.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 500;")

            badge_lay.addWidget(dot)
            badge_lay.addWidget(label)

            # Capsule badge shape styling
            badge.setStyleSheet(
                """
                QWidget {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 12px;
                }
                """
            )

            self._badge_layout.addWidget(badge)
            self._badges.append(badge)
