"""Four-corner board calibration: validation, homography, JSON persistence.

The user marks the four corners of the physical board in the camera image, always in the order

        0 Top-left   1 Top-right   2 Bottom-right   3 Bottom-left

They are associated with the corners of the rectangular board coordinate system
(0,0) (W,0) (W,H) (0,H); W x H is the logical board size (1600 x 900 by default). Coordinates are
continuous: the board spans [0, W] x [0, H] and its centre is (W/2, H/2).

The stored file contains the corners, the camera resolution and the mirroring flag used during
calibration. The matrix is saved for readability but is always *recomputed* from the corners on
load (and compared with the stored one), so a hand-edited or corrupted file cannot inject a bad
transformation.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from core.homography import (HomographyError, apply_homography, estimate_homography,
                             homography_problems, reprojection_error)

CORNER_NAMES = ("Top-left", "Top-right", "Bottom-right", "Bottom-left")
CORNER_SHORT = ("TL", "TR", "BR", "BL")
FORMAT_VERSION = 1

Point = tuple[float, float]


class CalibrationError(ValueError):
    def __init__(self, problems: list[str] | str) -> None:
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("; ".join(self.problems))


def board_corners(board_size: tuple[int, int]) -> list[Point]:
    w, h = board_size
    return [(0.0, 0.0), (float(w), 0.0), (float(w), float(h)), (0.0, float(h))]


# ---------------------------------------------------------------- ordering / validation
def order_corners(points) -> list[Point]:
    """Sort four points into TL, TR, BR, BL (image coordinates, y pointing down).

    Top-left has the smallest x+y, bottom-right the largest x+y; of the remaining two, top-right
    has the smallest y-x (it is up and to the right), bottom-left the largest.
    """
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) != 4:
        raise CalibrationError("Exactly four corners are required")
    s = [x + y for x, y in pts]
    d = [y - x for x, y in pts]
    tl, br = pts[int(np.argmin(s))], pts[int(np.argmax(s))]
    tr, bl = pts[int(np.argmin(d))], pts[int(np.argmax(d))]
    return [tl, tr, br, bl]


def _polygon_area(pts: list[Point]) -> float:
    """Shoelace formula; positive for TL->TR->BR->BL in image coordinates (y down)."""
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def validate_corners(corners, camera_size: tuple[int, int]) -> list[str]:
    """Return the list of problems (empty = the four corners are acceptable)."""
    try:
        pts = [(float(x), float(y)) for x, y in corners]
    except (TypeError, ValueError):
        return ["The corners are not numeric (x, y) pairs"]
    if len(pts) != 4:
        return [f"Four corners are required (got {len(pts)})"]
    if not all(math.isfinite(v) for p in pts for v in p):
        return ["A corner has an invalid coordinate"]
    cw, ch = camera_size
    tol = 2.0
    if any(not (-tol <= x <= cw + tol and -tol <= y <= ch + tol) for x, y in pts):
        return ["A corner lies outside the camera image"]
    for i in range(4):
        for j in range(i + 1, 4):
            if math.dist(pts[i], pts[j]) < 10.0:
                return [f"Corners {CORNER_SHORT[i]} and {CORNER_SHORT[j]} are almost at the same place"]
    area = _polygon_area(pts)
    if area <= 0:
        return ["The corners are not in the order Top-left, Top-right, Bottom-right, Bottom-left "
                "(or they form a twisted shape)"]
    for k in range(4):                       # convexity: every turn has the same direction
        (x1, y1), (x2, y2), (x3, y3) = pts[k], pts[(k + 1) % 4], pts[(k + 2) % 4]
        if (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2) <= 0:
            return ["The four corners do not form a convex quadrilateral"]
    if area < 0.01 * cw * ch:
        return ["The marked board is too small in the image (less than 1 % of the frame)"]
    return []


def fit_ok(p) -> bool:
    return all(math.isfinite(v) for v in p)


# ---------------------------------------------------------------- calibration object
@dataclass
class Calibration:
    corners: list[Point]
    camera_size: tuple[int, int]
    board_size: tuple[int, int]
    mirror: bool = False
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    H: np.ndarray = field(init=False, repr=False)          # camera -> board
    H_inv: np.ndarray = field(init=False, repr=False)      # board -> camera
    rms_error: float = field(init=False, default=0.0)      # board px, on the four corners
    warnings: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.corners = [(float(x), float(y)) for x, y in self.corners]
        self.camera_size = (int(self.camera_size[0]), int(self.camera_size[1]))
        self.board_size = (int(self.board_size[0]), int(self.board_size[1]))
        self._compute()

    def _compute(self) -> None:
        problems = validate_corners(self.corners, self.camera_size)
        if self.board_size[0] <= 0 or self.board_size[1] <= 0:
            problems.append("The board size is invalid")
        if problems:
            raise CalibrationError(problems)

        dst = board_corners(self.board_size)
        try:
            H = estimate_homography(self.corners, dst)
        except HomographyError as exc:
            raise CalibrationError(str(exc)) from exc
        problems = homography_problems(H)
        if problems:
            raise CalibrationError(problems)

        # the four corners and the quad centre must all be in front of the camera plane (W of the same sign)
        probe = np.array(self.corners + [tuple(np.mean(self.corners, axis=0))])
        w = np.hstack([probe, np.ones((5, 1))]) @ H[2]
        if not (np.all(w > 0) or np.all(w < 0)):
            raise CalibrationError("The transformation is not valid over the whole marked area")
        mapped = apply_homography(H, probe)
        if not np.isfinite(mapped).all():
            raise CalibrationError("Corner mapping produced invalid coordinates")

        err = reprojection_error(H, self.corners, dst)
        centre = mapped[4]
        bw, bh = self.board_size
        if not (0 < centre[0] < bw and 0 < centre[1] < bh):
            raise CalibrationError("The centre of the marked area does not map inside the board")
        if err > 1.0:
            raise CalibrationError(f"Reprojection error too large ({err:.2f} px)")

        self.H, self.H_inv, self.rms_error = H, np.linalg.inv(H), err
        self.warnings = []
        area = _polygon_area(self.corners) / (self.camera_size[0] * self.camera_size[1])
        if area < 0.08:
            self.warnings.append("The board occupies a small part of the image; accuracy will be limited.")

    @classmethod
    def from_corners(cls, corners, camera_size, board_size, mirror: bool = False) -> "Calibration":
        return cls(list(corners), tuple(camera_size), tuple(board_size), bool(mirror))

    # -------------------------------------------------------------- serialisation
    def to_dict(self) -> dict:
        return {
            "version": FORMAT_VERSION,
            "created": self.created,
            "camera_resolution": list(self.camera_size),
            "mirror": self.mirror,
            "board_size": list(self.board_size),
            "corners_px": [[x, y] for x, y in self.corners],
            "corner_order": list(CORNER_NAMES),
            "homography_camera_to_board": self.H.tolist(),
            "reprojection_error_px": self.rms_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Calibration":
        try:
            if int(data.get("version", 0)) != FORMAT_VERSION:
                raise CalibrationError("Unsupported calibration file version")
            cal = cls(corners=data["corners_px"], camera_size=tuple(data["camera_resolution"]),
                      board_size=tuple(data["board_size"]), mirror=bool(data.get("mirror", False)))
            cal.created = str(data.get("created", cal.created))
            stored = np.asarray(data.get("homography_camera_to_board"), dtype=np.float64)
            if stored.shape != (3, 3) or not np.allclose(stored, cal.H, rtol=1e-6, atol=1e-9):
                raise CalibrationError("The stored matrix does not match the stored corners (file corrupted)")
            return cal
        except CalibrationError:
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise CalibrationError(f"Calibration data is incomplete or malformed ({exc})") from exc


def save_calibration(path: str | os.PathLike, cal: Calibration) -> None:
    """Atomic write (temp file + replace) so a crash never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cal.to_dict(), handle, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_calibration(path: str | os.PathLike) -> tuple[Calibration | None, str | None]:
    """Returns (calibration, None) or (None, error message). A missing file is not an error."""
    path = Path(path)
    if not path.is_file():
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise CalibrationError("The calibration file has an unexpected structure")
        return Calibration.from_dict(data), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Calibration file could not be read ({exc}). Please recalibrate."
    except CalibrationError as exc:
        return None, f"Saved calibration is invalid: {exc}. Please recalibrate."


def check_compatibility(cal: Calibration, frame_size: tuple[int, int], mirror: bool) -> tuple[str, str]:
    """Is the calibration still valid for the frames the camera delivers now?

    "ok"       same resolution and mirroring
    "scaled"   same aspect ratio, other resolution -> coordinates are rescaled automatically
    "mismatch" other aspect ratio (different field of view / crop) or mirroring -> recalibrate
    """
    if bool(mirror) != cal.mirror:
        return "mismatch", "Camera mirroring changed since calibration - please recalibrate."
    cw, ch = cal.camera_size
    fw, fh = frame_size
    if (cw, ch) == (fw, fh):
        return "ok", ""
    if abs(cw / ch - fw / fh) > 0.02:
        return "mismatch", (f"Camera resolution changed (calibrated at {cw}x{ch}, now {fw}x{fh}) "
                            "- please recalibrate.")
    return "scaled", (f"Camera resolution changed ({cw}x{ch} -> {fw}x{fh}); the calibration is "
                      "rescaled automatically. Recalibrate for best accuracy.")
