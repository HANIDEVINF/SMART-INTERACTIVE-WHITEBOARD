"""Save / load a whiteboard session (drawing layer + image + view) in one ``.lumina`` file.

The file is a compressed NumPy archive (``np.savez_compressed``) read with ``allow_pickle=False`` so a damaged or
foreign file can never execute code.  Contents::

    ink        BGRA uint8 (H, W, 4)   the drawing layer
    source     BGR  uint8 (h, w, 3)   the original image shown behind the drawing (absent when there is none)
    placement  int (4,)               where the image sits on the board (x, y, w, h)
    view       float (3,)             zoom, offset x, offset y
    board      int (2,)               board size (W, H) the drawing was made on
    version    int
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SESSION_VERSION = 1
SESSION_SUFFIX = ".lumina"


class SessionError(Exception):
    """The session file cannot be written or read (the message is shown to the user)."""


@dataclass
class SessionData:
    ink: np.ndarray
    source: np.ndarray | None
    placement: tuple[int, int, int, int] | None
    zoom: float
    ox: float
    oy: float


def save_session(path: str | Path, ink: np.ndarray, source: np.ndarray | None, placement, zoom: float, ox: float,
                 oy: float) -> Path:
    path = Path(path)
    if path.suffix.lower() != SESSION_SUFFIX:
        path = path.with_suffix(SESSION_SUFFIX)
    arrays = {"ink": np.ascontiguousarray(ink), "view": np.array([zoom, ox, oy], dtype=np.float64),
              "board": np.array([ink.shape[1], ink.shape[0]], dtype=np.int64),
              "version": np.array(SESSION_VERSION, dtype=np.int64)}
    if source is not None and placement is not None:
        arrays["source"] = np.ascontiguousarray(source)
        arrays["placement"] = np.array(placement, dtype=np.int64)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:                 # atomic: a crash never leaves a half-written session
            np.savez_compressed(fh, **arrays)
        os.replace(tmp, path)
    except OSError as exc:
        raise SessionError(f"Could not save '{path.name}': {exc}") from None
    return path


def load_session(path: str | Path, board_size: tuple[int, int]) -> SessionData:
    path = Path(path)
    try:
        with np.load(path, allow_pickle=False) as z:
            names = set(z.files)
            if not {"ink", "view", "board", "version"} <= names:
                raise SessionError(f"'{path.name}' is not a LuminaBoard session")
            version = int(z["version"])
            if version != SESSION_VERSION:
                raise SessionError(f"'{path.name}' uses session format {version}; this version reads {SESSION_VERSION}")
            ink = z["ink"]
            board = tuple(int(v) for v in z["board"])
            view = z["view"]
            source = z["source"] if "source" in names else None
            placement = tuple(int(v) for v in z["placement"]) if "placement" in names else None
    except FileNotFoundError:
        raise SessionError(f"'{path.name}' does not exist") from None
    except SessionError:
        raise
    except (OSError, ValueError, KeyError, EOFError) as exc:
        raise SessionError(f"'{path.name}' could not be read ({exc})") from None
    except Exception as exc:                            # zip/format corruption surfaces as several exception types
        raise SessionError(f"'{path.name}' is damaged or not a session file ({type(exc).__name__})") from None
    w, h = board_size
    if board != (w, h) or ink.shape != (h, w, 4) or ink.dtype != np.uint8:
        raise SessionError(f"'{path.name}' was made on a {board[0]} x {board[1]} board; this board is {w} x {h}")
    if source is not None:
        if source.ndim != 3 or source.shape[2] != 3 or source.dtype != np.uint8 or placement is None or len(placement) != 4:
            raise SessionError(f"The image stored in '{path.name}' is damaged")
    if view.shape != (3,) or not np.isfinite(view).all():
        raise SessionError(f"The view stored in '{path.name}' is damaged")
    return SessionData(ink, source, placement, float(view[0]), float(view[1]), float(view[2]))
