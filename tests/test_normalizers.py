import pytest

from app.extraction.normalizers import find_grade, find_lengths_mm, to_mm


@pytest.mark.parametrize("value,unit,expected", [
    (200, "mm", 200), (20, "cm", 200), (0.2, "m", 200), (9, "in", 228.6), (150, None, 150),
])
def test_to_mm(value, unit, expected):
    assert to_mm(value, unit) == pytest.approx(expected)


def test_find_lengths():
    assert find_lengths_mm("wall 0.23 m thick")[0][0] == 230
    assert find_lengths_mm("200mm THK")[0][0] == 200


@pytest.mark.parametrize("text,key,expected", [
    ("Use m 25 concrete", "concrete.grade", "M25"),
    ("Grade C25/30 to EN 206", "concrete.grade", "C25/30"),
    ("Steel fe500d bars", "rebar.grade", "Fe500D"),
    ("no grade here", "concrete.grade", None),
])
def test_find_grade(text, key, expected):
    assert find_grade(text, key) == expected
