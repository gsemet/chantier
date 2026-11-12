"""Hidden judge tests for the CR item-notes. Never pushed to the sandbox."""
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit


class Page(HTMLParser):
    """The <textarea> tags and their text."""

    def __init__(self):
        super().__init__()
        self.textareas = []
        self._open = None

    def handle_starttag(self, tag, attrs):
        if tag == "textarea":
            self._open = [dict(attrs), ""]

    def handle_data(self, data):
        if self._open is not None:
            self._open[1] += data

    def handle_endtag(self, tag):
        if tag == "textarea" and self._open is not None:
            self.textareas.append((self._open[0], unescape(self._open[1])))
            self._open = None


def textareas(html):
    page = Page()
    page.feed(html)
    return page.textareas


def add(client, title="Judge notes item"):
    assert client.post("/items", {"title": title, "url": ""}).status == 303


def test_notes_are_saved_escaped_with_their_line_breaks(client):
    add(client)
    response = client.post("/items/1/notes", {"notes": "line one\nline <two>"})
    assert response.status == 303
    assert urlsplit(response.headers["location"]).path == "/items/1"
    page = client.get("/items/1").text
    assert "line one\nline &lt;two&gt;" in page
    assert "line <two>" not in page


def test_the_textarea_holds_the_current_notes(client):
    add(client)
    client.post("/items/1/notes", {"notes": "line one\nline <two>"})
    areas = [text for attrs, text in textareas(client.get("/items/1").text) if attrs.get("name") == "notes"]
    assert len(areas) == 1
    assert areas[0].strip("\r\n") == "line one\nline <two>"


def test_a_textarea_named_notes_exists_on_a_new_item(client):
    add(client)
    assert any(attrs.get("name") == "notes" for attrs, _ in textareas(client.get("/items/1").text))


def test_2000_characters_save_after_trimming_and_2001_are_refused(client):
    add(client)
    assert client.post("/items/1/notes", {"notes": "  " + "y" * 2000 + "  "}).status == 303
    assert "y" * 2000 in client.get("/items/1").text
    assert client.post("/items/1/notes", {"notes": "keep me judge"}).status == 303
    response = client.post("/items/1/notes", {"notes": "z" * 2001})
    assert response.status == 400
    assert "Notes are limited to 2000 characters." in response.text
    page = client.get("/items/1").text
    assert "keep me judge" in page
    assert "z" * 2001 not in page


def test_an_unknown_item_is_404(client):
    assert client.post("/items/9/notes", {"notes": "x"}).status == 404


def test_the_stylesheet_keeps_line_breaks(client):
    assert "pre-wrap" in client.get("/static/style.css").text
