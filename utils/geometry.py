"""Manual NumPy geometry: homography estimation and point transforms.

A homography is a 3x3 projective transform that maps points from one
plane to another (here: camera image plane -> whiteboard plane).

For a point correspondence (x, y) -> (x', y') the homography satisfies

    x' = (h11 x + h12 y + h13) / (h31 x + h32 y + h33)
    y' = (h21 x + h22 y + h23) / (h31 x + h32 y + h33)

Cross-multiplying gives two LINEAR equations per correspondence:

    h11 x + h12 y + h13 - x' h31 x - x' h32 y - x' h33 = 0
    h21 x + h22 y + h23 - y' h31 x - y' h32 y - y' h33 = 0

With 4 correspondences we get 8 equations for the 8 unknowns obtained by
fixing h33 = 1 (the scale of a homography is arbitrary).  The resulting
8x8 system is solved directly with np.linalg.solve -- this is the classic
DLT (direct linear transform) restricted to exactly 4 points.
"""

from __future__ import annotations

import numpy as np


def compute_homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Estimate the 3x3 homography mapping ``src`` points to ``dst`` points.

    Parameters
    ----------
    src : (4, 2) array of source points (camera pixels).
    dst : (4, 2) array of destination points (board coordinates).

    Returns
    -------
    H : (3, 3) float64 homography such that dst ~ H @ [src, 1].

    Raises
    ------
    ValueError if the inputs are degenerate (fewer than 4 points, repeated
    points, or a singular system -- e.g. collinear calibration points).
    """
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)
    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError("homography requires exactly 4 point pairs")
    if len(np.unique(src, axis=0)) < 4 or len(np.unique(dst, axis=0)) < 4:
        raise ValueError("calibration points must be distinct")

    # Build the 8x8 linear system A h = b with h33 fixed to 1.
    A = np.zeros((8, 8), dtype=np.float64)
    b = np.zeros(8, dtype=np.float64)
    for i, ((x, y), (xp, yp)) in enumerate(zip(src, dst)):
        # Row for the x' equation.
        A[2 * i] = [x, y, 1.0, 0.0, 0.0, 0.0, -xp * x, -xp * y]
        b[2 * i] = xp
        # Row for the y' equation.
        A[2 * i + 1] = [0.0, 0.0, 0.0, x, y, 1.0, -yp * x, -yp * y]
        b[2 * i + 1] = yp

    try:
        h = np.linalg.solve(A, b)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "degenerate calibration: points are collinear or the system "
            "is singular") from exc

    H = np.array([
        [h[0], h[1], h[2]],
        [h[3], h[4], h[5]],
        [h[6], h[7], 1.0],
    ], dtype=np.float64)
    return H


def transform_points(H: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Apply a homography to an array of points.

    ``points`` may be (N, 2) or a single (2,) point.  Returns points in
    the destination plane, shape (N, 2).  The perspective divide by the
    third homogeneous coordinate is performed explicitly.
    """
    pts = np.asarray(points, dtype=np.float64)
    single = pts.ndim == 1
    if single:
        pts = pts.reshape(1, 2)

    ones = np.ones((pts.shape[0], 1), dtype=np.float64)
    homog = np.hstack([pts, ones])          # (N, 3)
    out = homog @ H.T                        # (N, 3)
    w = out[:, 2]
    if np.any(np.abs(w) < 1e-12):
        raise ValueError("point maps to infinity under this homography")
    xy = out[:, :2] / w[:, None]
    return xy[0] if single else xy


def is_valid_quad(points: np.ndarray, min_area: float = 1000.0) -> bool:
    """Check that 4 calibration points form a usable convex quadrilateral.

    Rejects degenerate selections: fewer than 4 distinct points, near-zero
    area, or three collinear points (which make the DLT system singular).
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.shape != (4, 2):
        return False
    if len(np.unique(pts, axis=0)) < 4:
        return False

    # Shoelace formula for polygon area.
    x, y = pts[:, 0], pts[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    if area < min_area:
        return False

    # Collinearity check: every consecutive triple must have a non-zero
    # cross product (with a small tolerance relative to the quad size).
    scale = max(area, 1.0)
    for i in range(4):
        p0 = pts[i]
        p1 = pts[(i + 1) % 4]
        p2 = pts[(i + 2) % 4]
        d1 = p1 - p0
        d2 = p2 - p1
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cross) < scale * 1e-4:
            return False
    return True


def is_clockwise_convex(points: np.ndarray) -> bool:
    """True if the 4 points form a convex quad in clockwise order on screen.

    Image coordinates have y pointing down, so the expected click order
    top-left -> top-right -> bottom-right -> bottom-left turns "right" at
    every corner, which gives a positive cross product at all four.  A
    wrong order (e.g. counter-clockwise) would silently build a mirrored
    homography and flip the pointer, so calibration rejects it.
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.shape != (4, 2):
        return False
    for i in range(4):
        d1 = pts[(i + 1) % 4] - pts[i]
        d2 = pts[(i + 2) % 4] - pts[(i + 1) % 4]
        if d1[0] * d2[1] - d1[1] * d2[0] <= 0:
            return False
    return True


def point_in_rect(point, rect) -> bool:
    """True if ``point`` (x, y) lies inside ``rect`` (x, y, w, h)."""
    x, y = point
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh
