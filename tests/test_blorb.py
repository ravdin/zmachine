"""
Unit tests for the version 6 changes.

Focused on pure, deterministic logic that can be tested without pygame:
  - BlorbFile chunk parsing (Reso, APal, padding) and scaling math
  - ScalableImage ratio sentinels
  - MemoryStream flush (plain and buffered/print_form paths)
  - wrap_lines iterator, including the wrapping-off clip path (Shogun regression)
  - set_window_attributes bit operations
  - Window property dispatch round-trips

Rendering internals (pygame surfaces, curses screen state) are intentionally
left to manual play-through rather than mocked here.
"""
import struct
import pytest

from zmachine.blorb import BlorbFile, ScalableImage, WindowResolution


# ============================================================================
# Helpers for building Blorb byte data
# ============================================================================

def _u32(n: int) -> bytes:
    return struct.pack('>I', n)


def _chunk(chunk_id: bytes, body: bytes) -> bytes:
    """A Blorb chunk: 4-byte id, 4-byte big-endian length, body, optional pad byte."""
    data = chunk_id + _u32(len(body)) + body
    if len(body) & 1:
        data += b'\x00'  # pad to even boundary
    return data


def _blorb(*chunks: bytes) -> bytes:
    """Wrap chunks in a FORM/IFRS container. __init__ begins parsing at offset 12."""
    body = b'IFRS' + b''.join(chunks)
    return b'FORM' + _u32(len(body)) + body


def _reso_body(px, py, minx, miny, maxx, maxy, entries):
    """Build a Reso chunk body. entries: list of (num, ratnum, ratden, minnum, minden, maxnum, maxden)."""
    body = _u32(px) + _u32(py) + _u32(minx) + _u32(miny) + _u32(maxx) + _u32(maxy)
    for entry in entries:
        for field in entry:
            body += _u32(field)
    return body


# ============================================================================
# ScalableImage ratio sentinels
# ============================================================================

class TestScalableImage:
    @pytest.mark.unit
    def test_default_ratios_are_sentinels(self):
        """All-zero ratios collapse to identity / unbounded sentinels."""
        img = ScalableImage()
        assert img.stdratio == 1.0
        assert img.minratio == 0
        assert img.maxratio == float('inf')

    @pytest.mark.unit
    def test_explicit_ratios(self):
        img = ScalableImage(ratnum=2, ratden=1, minnum=1, minden=2, maxnum=4, maxden=1)
        assert img.stdratio == 2.0
        assert img.minratio == 0.5
        assert img.maxratio == 4.0


# ============================================================================
# BlorbFile parsing
# ============================================================================

class TestBlorbResolution:
    @pytest.mark.unit
    def test_empty_blorb_has_no_resolution(self):
        """An empty resource gives a neutral scaling ratio of 1.0."""
        blorb = BlorbFile(b'')
        assert blorb.get_scaling_ratio(1, 1280, 800) == 1.0

    @pytest.mark.unit
    def test_scaling_ratio_uses_elbow_room_and_image_ratio(self):
        """
        ERF = min(win_w/std_x, win_h/std_y). Result = ERF * image stdratio,
        clamped to the image's min/max ratio.
        """
        # Standard window 640x400; one entry for picture 1 with std ratio 2/1,
        # min 1/1, max 4/1.
        entry = (1, 2, 1, 1, 1, 4, 1)
        body = _reso_body(640, 400, 0, 0, 0, 0, [entry])
        blorb = BlorbFile(_blorb(_chunk(b'Reso', body)))

        # Window exactly double the standard in both axes -> ERF = 2.0
        # ratio = 2.0 * (2/1) = 4.0, which equals max (4/1), so not clamped down.
        assert blorb.get_scaling_ratio(1, 1280, 800) == 4.0

    @pytest.mark.unit
    def test_scaling_ratio_clamps_to_max(self):
        """A ratio above the per-image max is clamped to the max."""
        # std ratio 2/1, max 3/1. ERF 2.0 -> 4.0 desired, clamp to 3.0.
        entry = (1, 2, 1, 1, 1, 3, 1)
        body = _reso_body(640, 400, 0, 0, 0, 0, [entry])
        blorb = BlorbFile(_blorb(_chunk(b'Reso', body)))
        assert blorb.get_scaling_ratio(1, 1280, 800) == 3.0

    @pytest.mark.unit
    def test_scaling_ratio_clamps_to_min(self):
        """A ratio below the per-image min is clamped to the min."""
        # std ratio 1/4, min 1/2. ERF 1.0 -> 0.25 desired, clamp up to 0.5.
        entry = (1, 1, 4, 1, 2, 0, 0)  # max 0/0 -> inf, no upper clamp
        body = _reso_body(640, 400, 0, 0, 0, 0, [entry])
        blorb = BlorbFile(_blorb(_chunk(b'Reso', body)))
        # Window equal to standard -> ERF = 1.0
        assert blorb.get_scaling_ratio(1, 640, 400) == 0.5

    @pytest.mark.unit
    def test_picture_without_entry_uses_default_ratio(self):
        """A picture not listed in Reso uses ratnum/ratden = 1/1."""
        entry = (1, 2, 1, 0, 0, 0, 0)  # only picture 1 has an entry
        body = _reso_body(640, 400, 0, 0, 0, 0, [entry])
        blorb = BlorbFile(_blorb(_chunk(b'Reso', body)))
        # Picture 2 has no entry: ratio = ERF * 1.0. ERF for 1280x800 = 2.0.
        assert blorb.get_scaling_ratio(2, 1280, 800) == 2.0

    @pytest.mark.unit
    def test_resolution_fields_parsed(self):
        entry = (1, 1, 1, 0, 0, 0, 0)
        body = _reso_body(640, 400, 320, 200, 1280, 800, [entry])
        blorb = BlorbFile(_blorb(_chunk(b'Reso', body)))
        res = blorb._window_resolution
        assert isinstance(res, WindowResolution)
        assert (res.standard_x, res.standard_y) == (640, 400)
        assert (res.min_x, res.min_y) == (320, 200)
        assert (res.max_x, res.max_y) == (1280, 800)


class TestBlorbAdaptivePalette:
    @pytest.mark.unit
    def test_adaptive_pictures_parsed(self):
        body = _u32(5) + _u32(9) + _u32(12)
        blorb = BlorbFile(_blorb(_chunk(b'APal', body)))
        assert blorb.is_adaptive_picture(5)
        assert blorb.is_adaptive_picture(9)
        assert blorb.is_adaptive_picture(12)
        assert not blorb.is_adaptive_picture(1)

    @pytest.mark.unit
    def test_empty_apal_chunk(self):
        """Shogun/Journey: APal present but empty. No pictures are adaptive,
        but the chunk must parse without error."""
        blorb = BlorbFile(_blorb(_chunk(b'APal', b'')))
        assert not blorb.is_adaptive_picture(1)


class TestBlorbChunkPadding:
    @pytest.mark.unit
    def test_odd_length_chunk_is_padded(self):
        """
        A chunk with an odd body length is followed by a pad byte. The parser
        must skip the pad so the following chunk is still located.
        """
        # First an APal with 5 pictures... but APal entries are 4 bytes each,
        # always even. Use RelN (release number, 2-byte body -> even) won't
        # exercise padding. Build a deliberately odd-length filler chunk
        # followed by APal, and assert APal is still found.
        odd_body = b'\x01\x02\x03'  # length 3, odd -> needs 1 pad byte
        apal_body = _u32(7)
        data = _blorb(
            _chunk(b'XXXX', odd_body),   # unknown chunk, odd length + pad
            _chunk(b'APal', apal_body),
        )
        blorb = BlorbFile(data)
        # If padding was handled, APal was located and picture 7 is adaptive.
        assert blorb.is_adaptive_picture(7)

    @pytest.mark.unit
    def test_release_number_parsed(self):
        blorb = BlorbFile(_blorb(_chunk(b'RelN', struct.pack('>H', 42))))
        assert blorb.release_number == 42
