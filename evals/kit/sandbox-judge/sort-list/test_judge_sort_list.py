"""Hidden judge tests for the CR sort-list. Never pushed to the sandbox."""
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit


class Page(HTMLParser):
    """The item links in page order, and the links of the first <nav class="sort">."""

    def __init__(self):
        super().__init__()
        self.titles = []
        self.sort_links = []
        self._in_nav = False
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and "sort" in (attrs.get("class") or "").split():
            self._in_nav = True
        elif tag == "a":
            self._link = [attrs, ""]

    def handle_data(self, data):
        if self._link is not None:
            self._link[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            attrs, text = self._link
            self._link = None
            if self._in_nav:
                self.sort_links.append((text.strip(), attrs))
            elif re.fullmatch(r"/items/\d+", attrs.get("href") or ""):
                self.titles.append(text.strip())
        elif tag == "nav":
            self._in_nav = False


def parse(html):
    page = Page()
    page.feed(html)
    return page


def seed(client):
    for title in ("banana", "Apple", "cherry"):
        assert client.post("/items", {"title": title, "url": ""}).status == 303


def test_the_orders(client):
    seed(client)
    for path in ("/", "/?sort=", "/?sort=oldest"):
        assert parse(client.get(path).text).titles == ["banana", "Apple", "cherry"]
    assert parse(client.get("/?sort=newest").text).titles == ["cherry", "Apple", "banana"]
    assert parse(client.get("/?sort=title").text).titles == ["Apple", "banana", "cherry"]


def test_an_unknown_order_is_400(client):
    seed(client)
    response = client.get("/?sort=size")
    assert response.status == 400
    assert "Unknown sort: size" in response.text


def test_the_three_links(client):
    seed(client)
    links = parse(client.get("/").text).sort_links
    assert [text for text, _ in links] == ["Oldest", "Newest", "Title"]
    for (_, attrs), order in zip(links, ("oldest", "newest", "title")):
        parts = urlsplit(attrs["href"])
        assert parts.path == "/"
        assert parse_qs(parts.query).get("sort") == [order]


def current(html):
    return [text for text, attrs in parse(html).sort_links if attrs.get("aria-current") == "page"]


def test_aria_current_marks_the_current_order_only(client):
    seed(client)
    assert current(client.get("/").text) == ["Oldest"]
    assert current(client.get("/?sort=oldest").text) == ["Oldest"]
    assert current(client.get("/?sort=newest").text) == ["Newest"]
    assert current(client.get("/?sort=title").text) == ["Title"]
