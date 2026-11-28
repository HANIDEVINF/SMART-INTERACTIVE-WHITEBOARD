"""Fast connected-component labelling for BIG blobs (a hand), vectorised with NumPy.

The flood fill in imgproc.py is made for a tiny dot.  For a hand (thousands of pixels) we label a
coarse copy of the mask instead:
  1. OR the mask in ``block`` x ``block`` cells   (keeps thin fingers connected),
  2. give every set cell its own number, then repeat "take the largest number among the 8
     neighbours" until nothing changes - every connected group ends with one number,
  3. enlarge the labels back to the mask size and keep them only on the real mask pixels.
The number of iterations is about the blob diameter in cells, so it stays cheap.
"""
from __future__ import annotations

import numpy as np


def label_components(mask: np.ndarray, block: int = 4) -> np.ndarray:
    """int32 label image (0 = background, 1..n = components), same shape as ``mask``."""
    h, w = mask.shape
    H2, W2 = -(-h // block), -(-w // block)
    pad = np.zeros((H2 * block, W2 * block), bool)
    pad[:h, :w] = mask
    coarse = pad.reshape(H2, block, W2, block).any(axis=(1, 3))
    lab = np.zeros((H2, W2), np.int32)
    lab[coarse] = np.arange(1, int(coarse.sum()) + 1, dtype=np.int32)
    for _ in range(H2 + W2):                                   # cannot need more than this
        p = np.pad(lab, 1)
        m = lab.copy()
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                np.maximum(m, p[dy:dy + H2, dx:dx + W2], out=m)
        m[~coarse] = 0
        if np.array_equal(m, lab):
            break
        lab = m
    full = np.repeat(np.repeat(lab, block, axis=0), block, axis=1)[:h, :w]
    full[~mask] = 0
    return full
