"""Magik Resolution Selector — ComfyUI custom node pack.

Contains two nodes:
  * MagikResolutionSelector       -> outputs (width, height)
  * MagikTwoResolutionsSelector   -> outputs (width_1, height_1, width_2, height_2)
                                     with two independently configured resolutions
                                     sharing one aspect-ratio preset.

Each node derives its resolution pair(s) from:
  * an aspect-ratio preset (asp),
  * a megapixel target (megapixels),
  * a snapping grid (multiple).

All outputs are INT and are snapped to the nearest multiple of `multiple`,
so they land on clean grids (32, 64, ...) that diffusion models like.

Math:
  ratio          = ratio_w / ratio_h
  target_pixels  = megapixels * 1_000_000
  height_ideal   = sqrt(target_pixels / ratio)
  width_ideal    = height_ideal * ratio
  width, height  = round(ideal / multiple) * multiple   (min. one multiple)
"""

import math

# ---------------------------------------------------------------------------
# Aspect-ratio presets: (label, ratio_width, ratio_height)
# Ordered from widest landscape to tallest portrait; 15 presets in total.
# ---------------------------------------------------------------------------
_ASPECT_RATIO_DEFS = [
    ("2.35:1 (Anamorphic Widescreen)", 2.35, 1.0),
    ("21:9 (Cinematic Widescreen)", 21.0, 9.0),
    ("2:1 (Panorama)", 2.0, 1.0),
    ("1.85:1 (Cinematic Flat)", 1.85, 1.0),
    ("16:9 (Widescreen)", 16.0, 9.0),
    ("16:10 (Landscape Widescreen)", 16.0, 10.0),
    ("3:2 (Landscape Photo)", 3.0, 2.0),
    ("5:4 (Landscape Large Format)", 5.0, 4.0),
    ("4:3 (Landscape Classic)", 4.0, 3.0),
    ("1:1 (Square)", 1.0, 1.0),
    ("4:5 (Portrait Large Format)", 4.0, 5.0),
    ("3:4 (Portrait Classic)", 3.0, 4.0),
    ("2:3 (Portrait Photo)", 2.0, 3.0),
    ("1:2 (Portrait Panorama)", 1.0, 2.0),
    ("9:16 (Portrait Widescreen)", 9.0, 16.0),
]

ASPECT_RATIOS = [label for label, _, _ in _ASPECT_RATIO_DEFS]
ASPECT_RATIO_MAP = {label: (float(w), float(h)) for label, w, h in _ASPECT_RATIO_DEFS}

DEFAULT_ASPECT_RATIO = "9:16 (Portrait Widescreen)"
DEFAULT_MEGAPIXELS = 0.2
DEFAULT_MULTIPLE = 32


class MagikResolutionSelector:
    """Selects an output resolution from an aspect ratio, megapixels and multiple."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "asp": (
                    ASPECT_RATIOS,
                    {
                        "default": DEFAULT_ASPECT_RATIO,
                        "tooltip": "Aspect-ratio preset (width:height) that shapes the output resolution.",
                    },
                ),
                "megapixels": (
                    "FLOAT",
                    {
                        "default": DEFAULT_MEGAPIXELS,
                        "min": 0.01,
                        "max": 16.0,
                        "step": 0.01,
                        "display": "number",
                        "tooltip": "Target total pixel count (width x height) in megapixels. 0.2 MP is roughly a 512x512-class image.",
                    },
                ),
                "multiple": (
                    "INT",
                    {
                        "default": DEFAULT_MULTIPLE,
                        "min": 1,
                        "max": 512,
                        "step": 1,
                        "display": "number",
                        "tooltip": "Width and height are snapped to the nearest multiple of this value (use 8, 16, 32 or 64 for model-friendly grids).",
                    },
                ),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "select"
    CATEGORY = "Magik"
    DESCRIPTION = (
        "Selects an output resolution from an aspect-ratio preset, a megapixel target "
        "and a multiple. Outputs width and height as INT."
    )

    @staticmethod
    def compute_resolution(asp: str, megapixels: float, multiple: int):
        """Pure helper: returns (width, height) as ints. Kept static for easy testing."""
        if asp not in ASPECT_RATIO_MAP:
            raise ValueError(f"Unknown aspect-ratio preset: {asp!r}")

        ratio_w, ratio_h = ASPECT_RATIO_MAP[asp]
        ratio = ratio_w / ratio_h
        target_pixels = max(0.0, float(megapixels)) * 1_000_000.0

        height_ideal = math.sqrt(target_pixels / ratio)
        width_ideal = height_ideal * ratio

        m = max(1, int(multiple))
        width = max(m, int(round(width_ideal / m)) * m)
        height = max(m, int(round(height_ideal / m)) * m)
        return width, height

    def select(self, asp: str, megapixels: float, multiple: int):
        width, height = self.compute_resolution(asp, megapixels, multiple)
        return (width, height)


class MagikTwoResolutionsSelector:
    """Merge of two Magik Resolution Selectors sharing the same aspect-ratio preset.

    Resolution 1 (megapixels_1 / multiple_1) and resolution 2 (megapixels_2 /
    multiple_2) are configured independently, so one node can drive two stages
    of a workflow (e.g. a low-res draft latent and a high-res refiner latent)
    with identical framing.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "asp": (
                    ASPECT_RATIOS,
                    {
                        "default": DEFAULT_ASPECT_RATIO,
                        "tooltip": "Aspect-ratio preset (width:height) shared by BOTH output resolutions.",
                    },
                ),
                "megapixels_1": (
                    "FLOAT",
                    {
                        "default": DEFAULT_MEGAPIXELS,
                        "min": 0.01,
                        "max": 16.0,
                        "step": 0.01,
                        "display": "number",
                        "tooltip": "Resolution 1: target total pixel count (width_1 x height_1) in megapixels.",
                    },
                ),
                "multiple_1": (
                    "INT",
                    {
                        "default": DEFAULT_MULTIPLE,
                        "min": 1,
                        "max": 512,
                        "step": 1,
                        "display": "number",
                        "tooltip": "Resolution 1: width_1 and height_1 are snapped to the nearest multiple of this value.",
                    },
                ),
                "megapixels_2": (
                    "FLOAT",
                    {
                        "default": DEFAULT_MEGAPIXELS,
                        "min": 0.01,
                        "max": 16.0,
                        "step": 0.01,
                        "display": "number",
                        "tooltip": "Resolution 2: target total pixel count (width_2 x height_2) in megapixels.",
                    },
                ),
                "multiple_2": (
                    "INT",
                    {
                        "default": DEFAULT_MULTIPLE,
                        "min": 1,
                        "max": 512,
                        "step": 1,
                        "display": "number",
                        "tooltip": "Resolution 2: width_2 and height_2 are snapped to the nearest multiple of this value.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT", "INT")
    RETURN_NAMES = ("width_1", "height_1", "width_2", "height_2")
    FUNCTION = "select"
    CATEGORY = "Magik"
    DESCRIPTION = (
        "Merge of two resolution selectors sharing the same aspect-ratio preset. "
        "Each resolution has its own megapixels and multiple; outputs four INTs: "
        "width_1, height_1, width_2, height_2."
    )

    def select(self, asp: str, megapixels_1: float, multiple_1: int,
               megapixels_2: float, multiple_2: int):
        width_1, height_1 = MagikResolutionSelector.compute_resolution(
            asp, megapixels_1, multiple_1)
        width_2, height_2 = MagikResolutionSelector.compute_resolution(
            asp, megapixels_2, multiple_2)
        return (width_1, height_1, width_2, height_2)


NODE_CLASS_MAPPINGS = {
    "MagikResolutionSelector": MagikResolutionSelector,
    "MagikTwoResolutionsSelector": MagikTwoResolutionsSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MagikResolutionSelector": "Magik Resolution Selector",
    "MagikTwoResolutionsSelector": "Magik Two Resolutions Selector",
}
