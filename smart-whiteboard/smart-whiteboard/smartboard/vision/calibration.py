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


def calibration_targets(w: int, h: int, margin: float) -> np.ndarray:
    """Four calibration targets in board pixels: TL, TR, BR, BL."""
    mx, my = w * margin, h * margin
    return np.array([[mx, my], [w - mx, my], [w - mx, h - my], [mx, h - my]], float)


class Calibration:
    """Holds H (camera -> board), its inverse, and the points it came from."""

    def __init__(self, board_w: int, board_h: int):
        self.board_w, self.board_h = board_w, board_h
        self.H: Optional[np.ndarray] = None
        self.H_inv: Optional[np.ndarray] = None
        self.cam_pts: Optional[np.ndarray] = None
        self.board_pts: Optional[np.ndarray] = None

    @property
    def calibrated(self) -> bool:
        return self.H is not None

    def fit(self, cam_pts, board_pts) -> None:
        self.cam_pts = np.asarray(cam_pts, float)
        self.board_pts = np.asarray(board_pts, float)
        self.H = compute_homography(self.cam_pts, self.board_pts)
        self.H_inv = np.linalg.inv(self.H)

    def cam_to_board(self, x: float, y: float) -> Tuple[float, float]:
        p = apply_homography(self.H, (x, y))[0]
        return float(p[0]), float(p[1])

    def board_to_cam(self, x: float, y: float) -> Tuple[float, float]:
        p = apply_homography(self.H_inv, (x, y))[0]
        return float(p[0]), float(p[1])

    def board_quad_in_camera(self) -> Optional[np.ndarray]:
        """The four board corners seen in the camera image (for ROI / debug)."""
        if not self.calibrated:
            return None
        corners = [(0, 0), (self.board_w, 0), (self.board_w, self.board_h), (0, self.board_h)]
        return apply_homography(self.H_inv, corners)

    def residuals(self, cam_pts, board_pts) -> np.ndarray:
        """Euclidean error (board pixels) of mapping cam_pts -> board_pts."""
        mapped = apply_homography(self.H, cam_pts)
        return np.linalg.norm(mapped - np.asarray(board_pts, float), axis=1)

    # ---- persistence ---------------------------------------------------------
    def save(self, path: str) -> None:
        data = {"board_size": [self.board_w, self.board_h],
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
        board = np.array(d["board_pts_norm"], float) * [self.board_w, self.board_h]
        self.fit(np.array(d["cam_pts"], float), board)
        return True
