"""Connected-component analysis.

The *labelling* step (assigning an integer id to every connected blob) is
delegated to ``cv2.connectedComponents`` because an efficient union-find /
run-length CCL in pure Python would be too slow for 720p frames at 30 fps.
Everything else -- area filtering, centroid and bounding-box computation --
is implemented manually with NumPy in ``utils.image_processing``.
"""

from __future__ import annotations

import cv2
import numpy as np

from utils.image_processing import component_stats


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Label 8-connected foreground regions.

    Returns (labels, n_labels) where labels is an int32 image and
    n_labels includes the background label 0.
    """
    # OpenCV 4.x returns (labels, n); OpenCV 5.x returns (n, labels).
    first, second = cv2.connectedComponents(mask.astype(np.uint8),
                                            connectivity=8)
    if isinstance(first, np.ndarray):
        labels, n = first, int(second)
    else:
        n, labels = int(first), second
    return labels.astype(np.int32), n


def analyse_components(mask: np.ndarray,
                       min_area: int = 100,
                       max_area: int | None = None) -> list[dict]:
    """Return statistics for every component that passes the area filter.

    Each returned dict contains:
        label, area, centroid (x, y), bbox (x0, y0, x1, y1)
    sorted by descending area so index 0 is the largest blob.
    """
    labels, n = label_components(mask)
    if n <= 1:
        return []
    stats = component_stats(labels, n)
    frame_area = mask.shape[0] * mask.shape[1]
    limit = max_area if max_area is not None else frame_area

    blobs = []
    for label, s in stats.items():
        if min_area <= s["area"] <= limit:
            blobs.append({
                "label": label,
                "area": s["area"],
                "centroid": s["centroid"],
                "bbox": s["bbox"],
            })
    blobs.sort(key=lambda b: b["area"], reverse=True)
    return blobs
