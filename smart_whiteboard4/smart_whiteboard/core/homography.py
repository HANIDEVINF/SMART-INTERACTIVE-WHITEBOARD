"""Planar homography estimated with the Direct Linear Transform (DLT), in NumPy.

What a homography is
--------------------
A flat board seen by a camera is related to the ideal, fronto-parallel board by a projective
transformation. In homogeneous coordinates it is a 3x3 matrix H (defined up to scale):

        [x']       [h11 h12 h13] [x]
        [y']  ~    [h21 h22 h23] [y]          (x', y') = (X / W, Y / W)   <- normalisation
        [ 1 ]      [h31 h32 h33] [1]

The matrix produces homogeneous output (X, Y, W); dividing by W gives the 2-D point. Lines stay
lines, but parallel lines may converge (perspective), which is why the board looks like a
trapezium in the camera image.

Why four points
---------------
H has 9 numbers but only 8 degrees of freedom (scale is irrelevant). Each point pair (x, y) -> (u, v)
gives two independent equations, so 4 pairs give exactly 8 equations. The 4 points must be in
general position (no three on a line), otherwise the system is rank-deficient.

How it is computed (DLT)
------------------------
From u = (h11 x + h12 y + h13) / (h31 x + h32 y + h33) and the analogous v, cross-multiplying gives
two linear equations in the unknown vector h = (h11 ... h33):

        -x -y -1  0  0  0  u*x u*y u        . h = 0
         0  0  0 -x -y -1  v*x v*y v

Stacking all pairs gives A h = 0 (A is 2n x 9). The non-trivial solution with |h| = 1 that
minimises |A h| is the right singular vector of A belonging to its smallest singular value (last
row of V^T in the SVD). For n = 4 the solution is exact; for n > 4 it is the least-squares fit.

Hartley normalisation: raw pixel coordinates (hundreds) and the constant 1 have very different
magnitudes, which makes the SVD numerically poor. Both point sets are first translated so their
centroid is at the origin and scaled so their mean distance is sqrt(2); the estimated matrix is
then mapped back:  H = T_dst^-1 . H_normalised . T_src.

OpenCV's cv2.getPerspectiveTransform solves the same 8x8 system; the tests compare both.
"""
from __future__ import annotations

import numpy as np


class HomographyError(ValueError):
    """The point configuration is degenerate or the matrix is unusable."""


def _normalization(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centroid = points.mean(axis=0)
    mean_dist = np.linalg.norm(points - centroid, axis=1).mean()
    if mean_dist < 1e-9:
        raise HomographyError("All points are identical")
    s = np.sqrt(2.0) / mean_dist
    T = np.array([[s, 0.0, -s * centroid[0]],
                  [0.0, s, -s * centroid[1]],
                  [0.0, 0.0, 1.0]])
    return T, (points - centroid) * s


def estimate_homography(src, dst) -> np.ndarray:
    """3x3 matrix H with  dst ~ H @ src  (>= 4 correspondences, DLT with normalisation)."""
    src = np.asarray(src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(dst, dtype=np.float64).reshape(-1, 2)
    if src.shape != dst.shape or len(src) < 4:
        raise HomographyError("At least four point pairs are required")
    if not (np.isfinite(src).all() and np.isfinite(dst).all()):
        raise HomographyError("Points contain NaN or infinity")

    t_src, ns = _normalization(src)
    t_dst, nd = _normalization(dst)

    rows = []
    for (x, y), (u, v) in zip(ns, nd):
        rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u])
        rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])
    A = np.asarray(rows)
    _, sing, vt = np.linalg.svd(A)
    if sing.size >= 8 and sing[7] < 1e-9 * sing[0]:
        raise HomographyError("Degenerate configuration: points are collinear or coincident")

    H = np.linalg.inv(t_dst) @ vt[-1].reshape(3, 3) @ t_src
    if abs(H[2, 2]) > 1e-12:
        H = H / H[2, 2]
    else:
        H = H / np.linalg.norm(H)
    return H


def apply_homography(H: np.ndarray, points) -> np.ndarray:
    """Map points through H and normalise by the homogeneous coordinate W.
    Points whose W is ~0 (they lie on the horizon line) come back as NaN instead of inf."""
    pts = np.asarray(points, dtype=np.float64)
    single = pts.ndim == 1
    pts = pts.reshape(-1, 2)
    homogeneous = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    w = homogeneous[:, 2:3]
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.abs(w) > 1e-12, homogeneous[:, :2] / w, np.nan)
    return out[0] if single else out


def homography_problems(H) -> list[str]:
    """Reasons why H cannot be used (empty list = valid)."""
    try:
        H = np.asarray(H, dtype=np.float64)
    except (TypeError, ValueError):
        return ["The matrix is not numeric"]
    if H.shape != (3, 3):
        return ["The matrix is not 3 x 3"]
    if not np.isfinite(H).all():
        return ["The matrix contains NaN or infinity"]
    sv = np.linalg.svd(H, compute_uv=False)
    if sv[0] <= 0 or sv[2] / sv[0] < 1e-10:
        return ["The matrix is singular (degenerate transformation)"]
    return []


def reprojection_error(H: np.ndarray, src, dst) -> float:
    """Root-mean-square distance between H(src) and dst (in dst units)."""
    mapped = apply_homography(H, src)
    diff = mapped - np.asarray(dst, dtype=np.float64).reshape(-1, 2)
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))
