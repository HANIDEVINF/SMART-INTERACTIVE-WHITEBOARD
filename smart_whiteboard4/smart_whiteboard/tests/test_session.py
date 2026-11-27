import numpy as np
import pytest

from tools.session_file import SessionError, load_session, save_session


def _ink():
    ink = np.zeros((90, 160, 4), np.uint8)
    ink[10:20, 30:60] = (10, 20, 30, 255)
    return ink


def test_round_trip_with_image_and_view(tmp_path):
    src = (np.arange(40 * 60 * 3) % 251).astype(np.uint8).reshape(40, 60, 3)
    p = save_session(tmp_path / "a", _ink(), src, (0, 5, 160, 80), 2.5, -30.0, -12.0)
    assert p.suffix == ".lumina" and not list(tmp_path.glob("*.tmp"))
    d = load_session(p, (160, 90))
    assert (d.ink == _ink()).all() and (d.source == src).all()
    assert d.placement == (0, 5, 160, 80) and (d.zoom, d.ox, d.oy) == (2.5, -30.0, -12.0)


def test_round_trip_without_image(tmp_path):
    p = save_session(tmp_path / "b.lumina", _ink(), None, None, 1.0, 0.0, 0.0)
    d = load_session(p, (160, 90))
    assert d.source is None and d.placement is None


@pytest.mark.parametrize("content", [b"", b"not a zip at all", b"PK\x03\x04garbage"])
def test_damaged_files_give_clear_errors(tmp_path, content):
    p = tmp_path / "bad.lumina"
    p.write_bytes(content)
    with pytest.raises(SessionError):
        load_session(p, (160, 90))


def test_missing_file_and_foreign_npz_and_wrong_board(tmp_path):
    with pytest.raises(SessionError, match="does not exist"):
        load_session(tmp_path / "none.lumina", (160, 90))
    np.savez(tmp_path / "x.npz", a=np.zeros(3))
    with pytest.raises(SessionError, match="not a LuminaBoard session"):
        load_session(tmp_path / "x.npz", (160, 90))
    p = save_session(tmp_path / "c", _ink(), None, None, 1, 0, 0)
    with pytest.raises(SessionError, match="board"):
        load_session(p, (1600, 900))
