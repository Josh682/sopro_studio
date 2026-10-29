"""Dynamic Rack Control Factory for Umbra Workspace.

Inspects ParameterDescriptor collections from BaseProcessor instances and builds
skeuomorphic analog control clusters for Slot 3 (Cluster A, Cluster B, Cluster C).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.processors.base_processor import ParameterDescriptor
from src.ui.qt import (
    QFont,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.ui.theme.tokens import TOKENS
from src.ui.widgets.analog_controls import (
    AnalogChoiceSelector,
    AnalogFader,
    AnalogKnob,
    AnalogToggle,
)

log = logging.getLogger("sound_processor.ui.components.rack_control_factory")


class RackClusterContainer(QWidget):
    """Container hosting controls for a specific rack cluster."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(6, 4, 6, 4)
        self.layout_root.setSpacing(6)

        # Content container
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.layout_root.addWidget(self.content_widget)


class DynamicRackController:
    """Manages the creation, data binding, and query of hardware controls for a module."""

    def __init__(self) -> None:
        self._controls: Dict[str, QWidget] = {}
        self._descriptors: Dict[str, ParameterDescriptor] = {}

    @property
    def controls(self) -> Dict[str, QWidget]:
        return self._controls

    def clear(self) -> None:
        """Clear all registered controls."""
        self._controls.clear()
        self._descriptors.clear()

    def build_clusters(
        self,
        descriptors: List[ParameterDescriptor],
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> Tuple[QWidget, QWidget, QWidget]:
        """Construct 3 cluster widgets (Cluster A, B, C) populated with skeuomorphic controls.

        Args:
            descriptors: ParameterDescriptor list from the active processor.
            accent_color: Theme accent color for illumination and highlights.
            parent: Parent Qt widget.

        Returns:
            Tuple of (cluster_a_widget, cluster_b_widget, cluster_c_widget).
        """
        self.clear()

        panel_a = RackClusterContainer("PRIMARY", parent)
        panel_b = RackClusterContainer("ENGINE", parent)
        panel_c = RackClusterContainer("PRESETS", parent)

        if not descriptors:
            # Fallback placeholder
            for panel in (panel_a, panel_b, panel_c):
                lbl = QLabel("NO PARAMETERS AVAILABLE", panel)
                lbl.setFont(TOKENS.typography.create_font("data_mono_sm"))
                lbl.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")
                panel.content_layout.addWidget(lbl)
            return panel_a, panel_b, panel_c

        # Partition descriptors into 3 clusters:
        # Cluster C: Booleans / Toggles / Modifiers
        # Cluster A: Primary choice selectors or first 2 primary numeric controls
        # Cluster B: Remaining fine-tuning numeric controls or engine filters
        bool_descs: List[ParameterDescriptor] = []
        numeric_descs: List[ParameterDescriptor] = []
        choice_descs: List[ParameterDescriptor] = []

        for d in descriptors:
            self._descriptors[d.name] = d
            d_type = str(d.type).lower()
            if "bool" in d_type:
                bool_descs.append(d)
            elif "choice" in d_type or (d.choices and len(d.choices) > 0):
                choice_descs.append(d)
            else:
                numeric_descs.append(d)

        # Distribute into Cluster A, B, C
        cluster_a_descs: List[ParameterDescriptor] = []
        cluster_b_descs: List[ParameterDescriptor] = []
        cluster_c_descs: List[ParameterDescriptor] = list(bool_descs)

        # Primary choices go to A
        if choice_descs:
            cluster_a_descs.append(choice_descs[0])
            if len(choice_descs) > 1:
                cluster_b_descs.append(choice_descs[1])
            if len(choice_descs) > 2:
                cluster_a_descs.extend(choice_descs[2:])

        # Numeric descriptors
        for i, nd in enumerate(numeric_descs):
            if len(cluster_a_descs) < 2 and (not choice_descs or len(cluster_a_descs) < 3):
                cluster_a_descs.append(nd)
            elif len(cluster_b_descs) < 3:
                cluster_b_descs.append(nd)
            else:
                cluster_c_descs.append(nd)

        # If Cluster C is empty, borrow from B or A
        if not cluster_c_descs and len(cluster_b_descs) > 1:
            cluster_c_descs.append(cluster_b_descs.pop())

        # Build controls in each panel
        self._populate_cluster(panel_a, cluster_a_descs, accent_color)
        self._populate_cluster(panel_b, cluster_b_descs, accent_color)
        self._populate_cluster(panel_c, cluster_c_descs, accent_color)

        return panel_a, panel_b, panel_c

    def _populate_cluster(
        self,
        panel: RackClusterContainer,
        descs: List[ParameterDescriptor],
        accent_color: str,
    ) -> None:
        """Instantiate appropriate analog widgets for a list of descriptors."""
        if not descs:
            lbl = QLabel("READY · DEFAULT PROFILE", panel)
            lbl.setFont(TOKENS.typography.create_font("data_mono_sm"))
            lbl.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")
            panel.content_layout.addWidget(lbl)
            return

        # If all descriptors in this cluster are Choice selectors or Toggles, arrange vertically
        # If knobs, arrange horizontally
        has_choice = any(str(d.type).lower() in ("choice",) or d.choices for d in descs)
        if has_choice:
            # Vertical column arrangement for choice bars
            col_layout = QVBoxLayout()
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(6)
            col_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for d in descs:
                widget = self._create_widget_for_descriptor(d, accent_color, panel)
                self._controls[d.name] = widget
                col_layout.addWidget(widget)
            panel.content_layout.addLayout(col_layout)
        else:
            for d in descs:
                widget = self._create_widget_for_descriptor(d, accent_color, panel)
                self._controls[d.name] = widget
                panel.content_layout.addWidget(widget)

    def _create_widget_for_descriptor(
        self,
        d: ParameterDescriptor,
        accent_color: str,
        parent: QWidget,
    ) -> QWidget:
        """Instantiate single skeuomorphic widget from ParameterDescriptor."""
        d_type = str(d.type).lower()

        if "bool" in d_type:
            return AnalogToggle(
                name=d.name,
                label=d.name.replace("_", " ").title(),
                default_state=bool(d.default),
                accent_color=accent_color,
                parent=parent,
            )

        if "choice" in d_type or (d.choices and len(d.choices) > 0):
            choices = [str(c) for c in (d.choices or [])]
            return AnalogChoiceSelector(
                name=d.name,
                choices=choices,
                label=d.name.replace("_", " ").title(),
                default_choice=str(d.default),
                accent_color=accent_color,
                parent=parent,
            )

        if "string" in d_type or "path" in d_type:
            container = QWidget(parent)
            c_layout = QVBoxLayout(container)
            c_layout.setContentsMargins(4, 2, 4, 2)
            c_layout.setSpacing(2)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_lbl = QLabel((d.label or d.name.replace("_", " ").title()).upper()[:16], container)
            title_lbl.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            title_lbl.setStyleSheet(f"color: {TOKENS.colors.text.silkscreen_tag}; background: transparent;")
            val_box = QLabel(str(d.default or "—"), container)
            val_box.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
            val_box.setStyleSheet(f"color: #FCD34D; background: #120C08; border: 1px solid rgba(255,255,255,0.15); border-radius: 3px; padding: 4px 8px;")
            c_layout.addWidget(title_lbl)
            c_layout.addWidget(val_box)
            container.text = lambda: val_box.text()
            return container

        # Numeric float or int
        min_cand = getattr(d, "min_value", None) if getattr(d, "min_value", None) is not None else getattr(d, "min", None)
        max_cand = getattr(d, "max_value", None) if getattr(d, "max_value", None) is not None else getattr(d, "max", None)
        min_v = float(min_cand if min_cand is not None else 0.0)
        max_v = float(max_cand if max_cand is not None else 100.0)
        try:
            def_v = float(d.default if d.default is not None and str(d.default).strip() != "" else min_v)
        except (ValueError, TypeError):
            def_v = min_v

        step_cand = getattr(d, "step", None)
        step_v = float(step_cand if step_cand is not None else 1.0)
        unit_str = getattr(d, "unit", "") or ""

        # If descriptor is a fader-like control (e.g. master, gain, trim)
        if any(term in d.name.lower() for term in ("fader", "level", "master")):
            return AnalogFader(
                name=d.name,
                label=d.name.replace("_", " ").title(),
                min_val=min_v,
                max_val=max_v,
                default_val=def_v,
                step=step_v,
                unit=unit_str,
                accent_color=accent_color,
                parent=parent,
            )

        return AnalogKnob(
            name=d.name,
            label=d.name.replace("_", " ").title(),
            min_val=min_v,
            max_val=max_v,
            default_val=def_v,
            step=step_v,
            unit=unit_str,
            accent_color=accent_color,
            parent=parent,
        )

    def get_parameters(self) -> Dict[str, Any]:
        """Collect current values from all hardware controls.

        Returns:
            Dictionary matching the parameter names and values expected by the processor.
        """
        params: Dict[str, Any] = {}
        for name, widget in self._controls.items():
            desc = self._descriptors.get(name)
            if isinstance(widget, AnalogKnob):
                val = widget.value()
                if desc and str(desc.type).lower() == "int":
                    params[name] = int(round(val))
                else:
                    params[name] = float(val)
            elif isinstance(widget, AnalogFader):
                val = widget.value()
                if desc and str(desc.type).lower() == "int":
                    params[name] = int(round(val))
                else:
                    params[name] = float(val)
            elif isinstance(widget, AnalogToggle):
                params[name] = widget.isChecked()
            elif isinstance(widget, AnalogChoiceSelector):
                val = widget.currentChoice()
                if desc and desc.choices:
                    choice_map = {str(c): c for c in desc.choices}
                    params[name] = choice_map.get(val, val)
                elif desc and str(desc.type).lower() == "int":
                    try:
                        params[name] = int(val)
                    except (ValueError, TypeError):
                        params[name] = val
                else:
                    params[name] = val
            else:
                log.warning("Unknown widget type for control %s", name)

        return params

    def reset_to_defaults(self) -> None:
        """Reset all hardware controls to their descriptor default values."""
        for name, widget in self._controls.items():
            desc = self._descriptors.get(name)
            if not desc:
                continue
            if isinstance(widget, AnalogKnob):
                widget.setValue(float(desc.default or 0.0))
            elif isinstance(widget, AnalogFader):
                widget.setValue(float(desc.default or 0.0))
            elif isinstance(widget, AnalogToggle):
                widget.setChecked(bool(desc.default))
            elif isinstance(widget, AnalogChoiceSelector):
                widget.setCurrentChoice(str(desc.default))
