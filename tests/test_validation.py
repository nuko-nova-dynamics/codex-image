from __future__ import annotations

import pytest
from validation import (
    SizeError,
    validate_compression,
    validate_size,
)


def test_validate_size_accepts_official_presets():
    for s in ["1024x1024", "1536x1024", "1024x1536", "2048x2048",
              "2048x1152", "3840x2160", "2160x3840", "auto"]:
        assert validate_size(s) == s


def test_validate_size_accepts_custom_when_constraints_met():
    assert validate_size("1280x720") == "1280x720"   # 16-multiples, ratio 1.78
    assert validate_size("3824x2144") == "3824x2144"  # ≤3840, ratio 1.78


def test_validate_size_rejects_non_multiple_of_16():
    with pytest.raises(SizeError, match="multiple of 16"):
        validate_size("1280x721")


def test_validate_size_rejects_too_large_edge():
    with pytest.raises(SizeError, match="3840"):
        validate_size("3856x2160")  # 3856 > 3840


def test_validate_size_rejects_extreme_ratio():
    # 3:1 exactly is allowed; > would fail
    assert validate_size("3072x1024") == "3072x1024"
    with pytest.raises(SizeError, match="3:1"):
        validate_size("3088x1024")  # > 3:1


def test_validate_size_rejects_garbage():
    with pytest.raises(SizeError, match="format"):
        validate_size("big")
    with pytest.raises(SizeError, match="format"):
        validate_size("1024")
    with pytest.raises(SizeError, match="format"):
        validate_size("1024x1024x1")


def test_validate_compression_in_range():
    assert validate_compression(0, "--quality-jpeg") == 0
    assert validate_compression(50, "--quality-jpeg") == 50
    assert validate_compression(100, "--quality-jpeg") == 100


def test_validate_compression_rejects_out_of_range():
    with pytest.raises(ValueError, match="0-100"):
        validate_compression(-1, "--quality-jpeg")
    with pytest.raises(ValueError, match="0-100"):
        validate_compression(101, "--quality-jpeg")
