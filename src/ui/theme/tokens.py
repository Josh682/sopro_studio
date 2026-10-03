"""Design token loader and strongly-typed theme bridge for Audio Quick Toolkit.

Single Source of Truth: tokens.json (root or docs/tokens.json).
Adheres strictly to DESIGN.md Non-Negotiables.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from src.ui.qt import QColor, QFont

log = logging.getLogger("sound_processor.tokens")


@lru_cache(maxsize=256)
def hex_to_qcolor(color_str: str) -> QColor:
    """Convert hex, rgb, or rgba string from tokens.json to QColor.
    
    Supports:
      - #RRGGBB (e.g. "#090B0E")
      - #RGB (e.g. "#FFF")
      - rgba(r, g, b, a) (e.g. "rgba(255, 255, 255, 0.12)")
      - rgb(r, g, b)
    """
    cleaned = color_str.strip()
    if cleaned.startswith("#"):
        return QColor(cleaned)

    rgba_match = re.match(r"^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d\.]+))?\s*\)$", cleaned)
    if rgba_match:
        r = int(rgba_match.group(1))
        g = int(rgba_match.group(2))
        b = int(rgba_match.group(3))
        alpha_val = rgba_match.group(4)
        if alpha_val is not None:
            a = int(round(float(alpha_val) * 255.0))
            return QColor(r, g, b, a)
        return QColor(r, g, b)

    # Fallback to Qt default string parser
    return QColor(cleaned)


@dataclass(frozen=True)
class AccentToken:
    name: str
    base: str
    darker: str
    glow: str

    @property
    def base_qcolor(self) -> QColor:
        return hex_to_qcolor(self.base)

    @property
    def darker_qcolor(self) -> QColor:
        return hex_to_qcolor(self.darker)

    @property
    def glow_qcolor(self) -> QColor:
        return hex_to_qcolor(self.glow)


@dataclass(frozen=True)
class BackgroundColors:
    app: str = "#090B0E"
    chassis: str = "#090B0E"
    surface_card: str = "#131720"
    surface_card_hover: str = "#181E2A"
    surface_rack: str = "#11141A"
    surface_well: str = "#0A0C10"
    surface_display_glass: str = "#18130E"

    @property
    def app_qcolor(self) -> QColor:
        return hex_to_qcolor(self.app)

    @property
    def chassis_qcolor(self) -> QColor:
        return hex_to_qcolor(self.chassis)

    @property
    def surface_card_qcolor(self) -> QColor:
        return hex_to_qcolor(self.surface_card)

    @property
    def surface_card_hover_qcolor(self) -> QColor:
        return hex_to_qcolor(self.surface_card_hover)

    @property
    def surface_rack_qcolor(self) -> QColor:
        return hex_to_qcolor(self.surface_rack)

    @property
    def surface_well_qcolor(self) -> QColor:
        return hex_to_qcolor(self.surface_well)

    @property
    def surface_display_glass_qcolor(self) -> QColor:
        return hex_to_qcolor(self.surface_display_glass)


@dataclass(frozen=True)
class TextColors:
    primary: str = "#F0F3F8"
    secondary: str = "#8E9AA8"
    muted: str = "#525D6B"
    button_dark: str = "#090B0E"
    on_accent: str = "#0B0C10"

    @property
    def primary_qcolor(self) -> QColor:
        return hex_to_qcolor(self.primary)

    @property
    def secondary_qcolor(self) -> QColor:
        return hex_to_qcolor(self.secondary)

    @property
    def muted_qcolor(self) -> QColor:
        return hex_to_qcolor(self.muted)

    @property
    def button_dark_qcolor(self) -> QColor:
        return hex_to_qcolor(self.button_dark)

    @property
    def on_accent_qcolor(self) -> QColor:
        return hex_to_qcolor(self.on_accent)


@dataclass(frozen=True)
class BorderColors:
    subtle: str = "rgba(255, 255, 255, 0.07)"
    card: str = "rgba(255, 255, 255, 0.08)"
    card_hover: str = "rgba(255, 255, 255, 0.22)"
    highlight: str = "rgba(255, 255, 255, 0.18)"
    focus: str = "#5B9BFA"

    @property
    def subtle_qcolor(self) -> QColor:
        return hex_to_qcolor(self.subtle)

    @property
    def card_qcolor(self) -> QColor:
        return hex_to_qcolor(self.card)

    @property
    def card_hover_qcolor(self) -> QColor:
        return hex_to_qcolor(self.card_hover)

    @property
    def highlight_qcolor(self) -> QColor:
        return hex_to_qcolor(self.highlight)

    @property
    def focus_qcolor(self) -> QColor:
        return hex_to_qcolor(self.focus)


@dataclass(frozen=True)
class SemanticColors:
    success: str = "#22C55E"
    warning: str = "#F59E0B"
    error: str = "#EF4444"

    @property
    def success_qcolor(self) -> QColor:
        return hex_to_qcolor(self.success)

    @property
    def warning_qcolor(self) -> QColor:
        return hex_to_qcolor(self.warning)

    @property
    def error_qcolor(self) -> QColor:
        return hex_to_qcolor(self.error)


@dataclass(frozen=True)
class ColorTokens:
    background: BackgroundColors = field(default_factory=BackgroundColors)
    text: TextColors = field(default_factory=TextColors)
    border: BorderColors = field(default_factory=BorderColors)
    accents: Dict[str, AccentToken] = field(default_factory=dict)
    semantic: SemanticColors = field(default_factory=SemanticColors)


@dataclass(frozen=True)
class WindowDimensions:
    default_width: int = 1152
    default_height: int = 768
    min_width: int = 1024
    min_height: int = 680


@dataclass(frozen=True)
class ShellDimensions:
    titlebar_height: int = 44
    statusbar_height: int = 0
    margin_x: int = 24
    margin_y: int = 20


@dataclass(frozen=True)
class GridDimensions:
    columns: int = 3
    rows: int = 3
    gap_x: int = 16
    gap_y: int = 16
    card_width: int = 346
    card_height: int = 216


@dataclass(frozen=True)
class WorkspaceDimensions:
    slot1_topbar_height: int = 48
    slot2_deck_height: int = 210
    slot3_rack_height: int = 280
    slot4_footer_height: int = 64


@dataclass(frozen=True)
class ButtonDimensions:
    height: int = 44
    padding_x: int = 20
    launcher_height: int = 44
    workspace_footer_height: int = 44
    bevel_depth: int = 4
    pressed_translation_y: int = 3
    pressed_bevel_depth: int = 1


@dataclass(frozen=True)
class VUMeterDimensions:
    width: int = 320
    height: int = 180
    pivot_x: float = 160.0
    pivot_y: float = 195.0
    needle_length: float = 155.0
    arc_min_deg: float = -45.0
    arc_max_deg: float = 45.0


@dataclass(frozen=True)
class DimensionTokens:
    window: WindowDimensions = field(default_factory=WindowDimensions)
    shell: ShellDimensions = field(default_factory=ShellDimensions)
    grid: GridDimensions = field(default_factory=GridDimensions)
    workspace: WorkspaceDimensions = field(default_factory=WorkspaceDimensions)
    button: ButtonDimensions = field(default_factory=ButtonDimensions)
    vu_meter: VUMeterDimensions = field(default_factory=VUMeterDimensions)


@dataclass(frozen=True)
class RadiiTokens:
    sm: int = 4
    md: int = 8
    lg: int = 14
    card: int = 4
    button: int = 6
    input: int = 8
    pill: int = 999
    full: int = 9999


@dataclass(frozen=True)
class SpacingTokens:
    space_0: int = 0
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 20
    space_6: int = 24
    space_8: int = 32


@dataclass(frozen=True)
class TypographyItem:
    size: int
    weight: int
    line_height: int


@dataclass(frozen=True)
class TypographyTokens:
    font_family_ui: str = "Inter"
    font_family_mono: str = "JetBrains Mono"
    title_h1: TypographyItem = field(default_factory=lambda: TypographyItem(size=18, weight=600, line_height=24))
    title_card: TypographyItem = field(default_factory=lambda: TypographyItem(size=16, weight=600, line_height=22))
    body_regular: TypographyItem = field(default_factory=lambda: TypographyItem(size=13, weight=400, line_height=17))
    body_small: TypographyItem = field(default_factory=lambda: TypographyItem(size=11, weight=400, line_height=15))
    data_mono_lg: TypographyItem = field(default_factory=lambda: TypographyItem(size=28, weight=700, line_height=32))
    data_mono_md: TypographyItem = field(default_factory=lambda: TypographyItem(size=14, weight=500, line_height=18))
    data_mono_sm: TypographyItem = field(default_factory=lambda: TypographyItem(size=11, weight=500, line_height=14))

    def create_font(self, item_name: str) -> QFont:
        """Create a QFont configured with token family, point/pixel size, and weight."""
        item = getattr(self, item_name, None)
        if not isinstance(item, TypographyItem):
            return QFont(self.font_family_ui, 13)

        family = self.font_family_mono if "mono" in item_name else self.font_family_ui
        font = QFont(family)
        font.setPixelSize(item.size)

        # Map integer weights (400, 500, 600, 700) to QFont.Weight
        weight_map = {
            400: QFont.Weight.Normal,
            500: QFont.Weight.Medium,
            600: QFont.Weight.DemiBold,
            700: QFont.Weight.Bold,
        }
        font.setWeight(weight_map.get(item.weight, QFont.Weight.Normal))
        return font


@dataclass(frozen=True)
class VUMeterPhysics:
    stiffness: float = 0.18
    damping: float = 0.72
    fps: int = 60
    interval_ms: int = 16


@dataclass(frozen=True)
class PhysicsTokens:
    vu_meter: VUMeterPhysics = field(default_factory=VUMeterPhysics)


@dataclass(frozen=True)
class DesignTokens:
    name: str = "Audio Quick Toolkit Design Tokens"
    version: str = "2.0.0"
    colors: ColorTokens = field(default_factory=ColorTokens)
    dimensions: DimensionTokens = field(default_factory=DimensionTokens)
    radii: RadiiTokens = field(default_factory=RadiiTokens)
    spacing: SpacingTokens = field(default_factory=SpacingTokens)
    typography: TypographyTokens = field(default_factory=TypographyTokens)
    physics: PhysicsTokens = field(default_factory=PhysicsTokens)


def _find_tokens_file(custom_path: Path | str | None = None) -> Optional[Path]:
    """Search for tokens.json in root and docs directories."""
    candidates = []
    if custom_path:
        candidates.append(Path(custom_path))

    here = Path(__file__).resolve()
    # ../../../tokens.json
    candidates.append(here.parent.parent.parent.parent / "tokens.json")
    candidates.append(here.parent.parent.parent.parent / "docs" / "tokens.json")
    candidates.append(Path.cwd() / "tokens.json")
    candidates.append(Path.cwd() / "docs" / "tokens.json")

    for path in candidates:
        if path.is_file():
            return path
    return None


def _filter_dataclass_kwargs(cls: Any, data: Any) -> Dict[str, Any]:
    """Filter dictionary to only contain fields defined on the dataclass."""
    if not isinstance(data, dict):
        return {}
    valid_fields = getattr(cls, "__dataclass_fields__", {})
    return {k: v for k, v in data.items() if k in valid_fields}


def load_tokens(custom_path: Path | str | None = None) -> DesignTokens:
    """Load design tokens from tokens.json and return a typed DesignTokens instance."""
    token_path = _find_tokens_file(custom_path)
    if not token_path:
        log.warning("tokens.json not found on disk. Falling back to default design token values.")
        return _create_default_tokens()

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        colors_data = data.get("colors", {})
        bg_data = colors_data.get("background", {})
        text_data = colors_data.get("text", {})
        border_data = colors_data.get("border", {})
        sem_data = colors_data.get("semantic", {})
        accents_data = colors_data.get("accents", {})

        accents: Dict[str, AccentToken] = {}
        for acc_name, acc_val in accents_data.items():
            accents[acc_name] = AccentToken(
                name=acc_name,
                base=acc_val.get("base", "#5B9BFA"),
                darker=acc_val.get("darker", "#2D5EA6"),
                glow=acc_val.get("glow", "rgba(91, 155, 250, 0.30)"),
            )

        color_tokens = ColorTokens(
            background=BackgroundColors(**_filter_dataclass_kwargs(BackgroundColors, bg_data)) if bg_data else BackgroundColors(),
            text=TextColors(**_filter_dataclass_kwargs(TextColors, text_data)) if text_data else TextColors(),
            border=BorderColors(**_filter_dataclass_kwargs(BorderColors, border_data)) if border_data else BorderColors(),
            accents=accents,
            semantic=SemanticColors(**_filter_dataclass_kwargs(SemanticColors, sem_data)) if sem_data else SemanticColors(),
        )

        dim_data = data.get("dimensions", {})
        dim_tokens = DimensionTokens(
            window=WindowDimensions(**_filter_dataclass_kwargs(WindowDimensions, dim_data.get("window", {}))),
            shell=ShellDimensions(**_filter_dataclass_kwargs(ShellDimensions, dim_data.get("shell", {}))),
            grid=GridDimensions(**_filter_dataclass_kwargs(GridDimensions, dim_data.get("grid", {}))),
            workspace=WorkspaceDimensions(**_filter_dataclass_kwargs(WorkspaceDimensions, dim_data.get("workspace", {}))),
            button=ButtonDimensions(**_filter_dataclass_kwargs(ButtonDimensions, dim_data.get("button", {}))),
            vu_meter=VUMeterDimensions(**_filter_dataclass_kwargs(VUMeterDimensions, dim_data.get("vu_meter", {}))),
        )

        radii_tokens = RadiiTokens(**_filter_dataclass_kwargs(RadiiTokens, data.get("radii", {})))
        spacing_tokens = SpacingTokens(**_filter_dataclass_kwargs(SpacingTokens, data.get("spacing", {})))

        typo_data = data.get("typography", {})
        typo_items = {}
        for key in ["title_h1", "title_card", "body_regular", "body_small", "data_mono_lg", "data_mono_md", "data_mono_sm"]:
            if key in typo_data:
                typo_items[key] = TypographyItem(**_filter_dataclass_kwargs(TypographyItem, typo_data[key]))

        typo_tokens = TypographyTokens(
            font_family_ui=typo_data.get("font_family_ui", "Inter"),
            font_family_mono=typo_data.get("font_family_mono", "JetBrains Mono"),
            **typo_items,
        )

        phys_data = data.get("physics", {})
        vu_phys = phys_data.get("vu_meter", {})
        physics_tokens = PhysicsTokens(vu_meter=VUMeterPhysics(**_filter_dataclass_kwargs(VUMeterPhysics, vu_phys)) if vu_phys else VUMeterPhysics())

        return DesignTokens(
            name=data.get("name", "Audio Quick Toolkit Design Tokens"),
            version=data.get("version", "2.0.0"),
            colors=color_tokens,
            dimensions=dim_tokens,
            radii=radii_tokens,
            spacing=spacing_tokens,
            typography=typo_tokens,
            physics=physics_tokens,
        )
    except Exception as exc:
        log.error("Failed to parse tokens.json (%s). Using default tokens.", exc)
        return _create_default_tokens()


def _create_default_tokens() -> DesignTokens:
    """Create default tokens matching DESIGN.md specification."""
    accents = {
        "converter": AccentToken("converter", "#5B9BFA", "#2D5EA6", "rgba(91, 155, 250, 0.30)"),
        "separator": AccentToken("separator", "#FF8A50", "#B84A17", "rgba(255, 138, 80, 0.30)"),
        "combiner": AccentToken("combiner", "#6EE795", "#2EA053", "rgba(110, 231, 149, 0.30)"),
        "detect": AccentToken("detect", "#FCD34D", "#B5911B", "rgba(252, 211, 77, 0.30)"),
        "pitch": AccentToken("pitch", "#F472B6", "#AD3071", "rgba(244, 114, 182, 0.30)"),
        "tempo": AccentToken("tempo", "#2DD4BF", "#0F8273", "rgba(45, 212, 191, 0.30)"),
        "trim": AccentToken("trim", "#FB7185", "#BA243B", "rgba(251, 113, 133, 0.30)"),
        "normalize": AccentToken("normalize", "#38BDF8", "#0C7DB1", "rgba(56, 189, 248, 0.30)"),
        "info": AccentToken("info", "#A78BFA", "#6341C7", "rgba(167, 139, 250, 0.30)"),
    }
    return DesignTokens(
        colors=ColorTokens(accents=accents),
        dimensions=DimensionTokens(),
        radii=RadiiTokens(),
        spacing=SpacingTokens(),
        typography=TypographyTokens(),
        physics=PhysicsTokens(),
    )


# Globally accessible singleton instance initialized at import time
TOKENS: DesignTokens = load_tokens()
