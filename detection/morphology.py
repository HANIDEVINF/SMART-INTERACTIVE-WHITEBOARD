"""Morphology helpers.

The actual erosion/dilation algorithms are implemented manually with
NumPy in ``utils.image_processing``; this module simply re-exports them
under detection-pipeline names.
"""

from __future__ import annotations

from utils.image_processing import (binary_dilation, binary_erosion,
                                    morphological_close, morphological_open)

__all__ = [
    "binary_dilation",
    "binary_erosion",
    "morphological_open",
    "morphological_close",
]
