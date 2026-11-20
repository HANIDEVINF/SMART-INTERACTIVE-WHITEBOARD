"""Camera -> board geometry: planar homography estimated with the DLT.

Coordinate systems
------------------
camera  : pixels of the camera image, origin top-left, x right, y down.
board   : pixels of the projected screen (= the application canvas),
          origin at the board's upper-left corner, x right, y down
          (the (0,0) axes drawn in the project figure).

The board is a plane, so image -> board is a 3x3 homography H (8 DOF):

        [u']   [h11 h12 h13] [x]
        [v'] ~ [h21 h22 h23] [y]      u = u'/w',  v = v'/w'
        [w']   [h31 h32  1 ] [1]

Each point pair gives two linear equations in h (Direct Linear Transform);
four pairs solve H exactly, more pairs give a least-squares solution.
Hartley normalisation (centre + scale the points) makes the SVD well
conditioned.  np.linalg.svd is the only "predefined" geometry routine used.

Lens distortion
---------------
A homography assumes a perfect pinhole camera.  Cheap wide-angle webcams bend
straight lines (barrel distortion), which gives errors near the board edges.
With >= 8 calibration points we also estimate ONE radial coefficient k1:

    p_undistorted = c + (p - c) * (1 + k1 * r^2)       r = |p - c| / (half the image diagonal)

k1 is chosen on a grid by leave-one-out cross-validation (fit H on all points
but one, measure the error on the left-out point) and is only kept when it
improves that error clearly - otherwise k1 = 0 (plain homography).
"""
from __future__ import annotations

import json
import os
from typing import Optional, Sequence, Tuple

import numpy as np


def _normalisation(pts: np.ndarray) -> np.ndarray:
    c = pts.mean(axis=0)
    d = np.sqrt(((pts - c) ** 2).sum(axis=1)).mean()
    s = np.sqrt(2) / max(d, 1e-12)
    return np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]], float)


def compute_homography(src: Sequence, dst: Sequence) -> np.ndarray:
    """Return H such that dst ~ H @ src (>= 4 correspondences)."""
    src = np.asarray(src, float)
    dst = np.asarray(dst, float)
    if len(src) < 4 or len(src) != len(dst):
        raise ValueError("need >= 4 matching point pairs")
    Ts, Td = _normalisation(src), _normalisation(dst)
    sh = np.c_[src, np.ones(len(src))] @ Ts.T
    dh = np.c_[dst, np.ones(len(dst))] @ Td.T
    rows = []
    for (x, y, _), (u, v, _) in zip(sh, dh):
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.array(rows))
    H = vt[-1].reshape(3, 3)
    H = np.linalg.inv(Td) @ H @ Ts
    return H / H[2, 2]


def apply_homography(H: np.ndarray, pts) -> np.ndarray:
    pts = np.atleast_2d(np.asarray(pts, float))
    ph = np.c_[pts, np.ones(len(pts))] @ H.T
    return ph[:, :2] / ph[:, 2:3]


def calibration_targets(w: int, h: int, margin: float, n: int = 4) -> np.ndarray:
    """Calibration targets in board pixels.  n = 4: TL, TR, BR, BL.
    n = 9: 3x3 grid, row by row (top-left first)."""
    mx, my = w * margin, h * margin
    if n >= 9:
        return np.array([[x, y] for y in (my, h / 2.0, h - my) for x in (mx, w / 2.0, w - mx)], float)
    return np.array([[mx, my], [w - mx, my], [w - mx, h - my], [mx, h - my]], float)


class Calibration:
    """Holds H (camera -> board), its inverse, the lens coefficient k1 and the points they came from."""

    def __init__(self, board_w: int, board_h: int):
        self.board_w, self.board_h = board_w, board_h
        self.H: Optional[np.ndarray] = None
        self.H_inv: Optional[np.ndarray] = None
        self.cam_pts: Optional[np.ndarray] = None
        self.board_pts: Optional[np.ndarray] = None
        self.k1 = 0.0
        self.cam_w, self.cam_h = 1280, 1280 * 9 // 16      # updated from the first camera frame
        self.loo_error: Optional[float] = None             # leave-one-out error of the chosen model (board px)

    @property
    def calibrated(self) -> bool:
        return self.H is not None

    def set_camera_size(self, w: int, h: int) -> None:
        self.cam_w, self.cam_h = int(w), int(h)

    # ---- radial distortion ---------------------------------------------------------------
    def _norm(self) -> float:
        return 0.5 * float(np.hypot(self.cam_w, self.cam_h))

    def undistort(self, pts, k1: Optional[float] = None) -> np.ndarray:
        k1 = self.k1 if k1 is None else k1
        pts = np.atleast_2d(np.asarray(pts, float))
        if k1 == 0.0:
            return pts
        c = np.array([self.cam_w / 2.0, self.cam_h / 2.0])
        d = pts - c
        r2 = (d ** 2).sum(axis=1, keepdims=True) / self._norm() ** 2
        return c + d * (1.0 + k1 * r2)

    def distort(self, pts) -> np.ndarray:
        """Inverse of undistort (fixed-point iteration, 6 steps are plenty for small k1)."""
        pts = np.atleast_2d(np.asarray(pts, float))
        if self.k1 == 0.0:
            return pts
        c = np.array([self.cam_w / 2.0, self.cam_h / 2.0])
        du = pts - c
        d = du.copy()
        for _ in range(6):
            r2 = (d ** 2).sum(axis=1, keepdims=True) / self._norm() ** 2
            d = du / (1.0 + self.k1 * r2)
        return c + d

    def _loo(self, cam_pts, board_pts, k1) -> float:
        """Mean leave-one-out error (board px) for a given k1."""
        u = self.undistort(cam_pts, k1)
        errs = []
        for i in range(len(u)):
            keep = np.arange(len(u)) != i
            H = compute_homography(u[keep], board_pts[keep])
            errs.append(np.linalg.norm(apply_homography(H, u[i]) - board_pts[i]))
        return float(np.mean(errs))

    def estimate_k1(self, cam_pts, board_pts) -> float:
        """Grid search of k1 by leave-one-out cross-validation (needs >= 8 points)."""
        base = self._loo(cam_pts, board_pts, 0.0)
        best_k, best_e = 0.0, base
        for k in np.linspace(-0.35, 0.35, 29):
            e = self._loo(cam_pts, board_pts, float(k))
            if e < best_e:
                best_k, best_e = float(k), e
        if best_e < 0.8 * base:                    # keep it only if it clearly helps
            self.loo_error = best_e
            return best_k
        self.loo_error = base
        return 0.0

    # ---- fitting ------------------------------------------------------------------------------
    def fit(self, cam_pts, board_pts, estimate_distortion: bool = False) -> None:
        self.cam_pts = np.asarray(cam_pts, float)
        self.board_pts = np.asarray(board_pts, float)
        self.k1 = 0.0
        self.loo_error = None
        if estimate_distortion and len(self.cam_pts) >= 8:
            self.k1 = self.estimate_k1(self.cam_pts, self.board_pts)
        self.H = compute_homography(self.undistort(self.cam_pts), self.board_pts)
        self.H_inv = np.linalg.inv(self.H)

    def cam_to_board(self, x: float, y: float) -> Tuple[float, float]:
        p = apply_homography(self.H, self.undistort((x, y)))[0]
        return float(p[0]), float(p[1])

    def board_to_cam(self, x: float, y: float) -> Tuple[float, float]:
        p = self.distort(apply_homography(self.H_inv, (x, y)))[0]
        return float(p[0]), float(p[1])

    def board_quad_in_camera(self) -> Optional[np.ndarray]:
        """The four board corners seen in the camera image (for ROI / debug)."""
        if not self.calibrated:
            return None
        corners = [(0, 0), (self.board_w, 0), (self.board_w, self.board_h), (0, self.board_h)]
        return self.distort(apply_homography(self.H_inv, corners))

    def residuals(self, cam_pts, board_pts) -> np.ndarray:
        """Euclidean error (board pixels) of mapping cam_pts -> board_pts."""
        mapped = apply_homography(self.H, self.undistort(cam_pts))
        return np.linalg.norm(mapped - np.asarray(board_pts, float), axis=1)

    # ---- persistence ---------------------------------------------------------------------------
    def save(self, path: str) -> None:
        data = {"board_size": [self.board_w, self.board_h],
                "camera_size": [self.cam_w, self.cam_h],
                "k1": self.k1,
                "cam_pts": self.cam_pts.tolist(),
                # stored as fractions so the file stays valid if the resolution changes
                "board_pts_norm": (self.board_pts / [self.board_w, self.board_h]).tolist()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        self.cam_w, self.cam_h = d.get("camera_size", [self.cam_w, self.cam_h])
        board = np.array(d["board_pts_norm"], float) * [self.board_w, self.board_h]
        self.fit(np.array(d["cam_pts"], float), board)
        self.k1 = float(d.get("k1", 0.0))          # reuse the saved distortion, refit H with it
        self.H = compute_homography(self.undistort(self.cam_pts), self.board_pts)
        self.H_inv = np.linalg.inv(self.H)
        return True
