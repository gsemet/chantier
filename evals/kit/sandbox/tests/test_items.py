import pytest

from shelf.models import validate_new


def test_a_valid_item_is_trimmed():
    clean, error = validate_new("  A book  ", " https://example.com ")
    assert error is None
    assert clean == {"title": "A book", "url": "https://example.com"}


def test_the_link_is_optional():
    assert validate_new("A book", "")[1] is None


@pytest.mark.parametrize("title", ["", "   "])
def test_the_title_is_required(title):
    assert "required" in validate_new(title, "")[1]


def test_the_title_has_at_most_200_characters():
    assert validate_new("x" * 200, "")[1] is None
    assert "200" in validate_new("x" * 201, "")[1]


@pytest.mark.parametrize("url", ["example.com", "ftp://example.com", "javascript:alert(1)"])
def test_the_link_starts_with_http_or_https(url):
    assert "http" in validate_new("A book", url)[1]
