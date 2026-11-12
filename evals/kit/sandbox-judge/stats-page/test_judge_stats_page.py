"""Hidden judge tests for the CR stats-page. Never pushed to the sandbox."""
from html.parser import HTMLParser

from shelf import __version__


class Stats(HTMLParser):
    """The rows of the first <table class="stats">: (th text, td text)."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.hrefs = []
        self._in_table = False
        self._cell = None
        self._row = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.hrefs.append(attrs.get("href"))
        if tag == "table" and "stats" in (attrs.get("class") or "").split():
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._row = []
        elif self._in_table and tag in ("th", "td"):
            self._cell = ""

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(tuple(self._row))
            self._row = None
        elif tag == "table":
            self._in_table = False


def parse(html):
    stats = Stats()
    stats.feed(html)
    return stats


def test_an_empty_shelf_shows_four_zeros(client):
    response = client.get("/stats")
    assert response.status == 200
    assert parse(response.text).rows == [("To read", "0"), ("Reading", "0"), ("Done", "0"), ("Total", "0")]


def test_the_counts_follow_the_statuses(client):
    for title in ("Judge stats one", "Judge stats two", "Judge stats three"):
        assert client.post("/items", {"title": title, "url": ""}).status == 303
    assert client.post("/items/2/status", {"status": "reading"}).status == 303
    assert client.post("/items/3/status", {"status": "done"}).status == 303
    assert parse(client.get("/stats").text).rows == [
        ("To read", "1"), ("Reading", "1"), ("Done", "1"), ("Total", "3"),
    ]


def test_every_page_links_to_the_stats_page(client):
    assert client.post("/items", {"title": "Judge stats one", "url": ""}).status == 303
    assert "/stats" in parse(client.get("/").text).hrefs
    assert "/stats" in parse(client.get("/items/1").text).hrefs


def test_post_is_405_and_the_footer_has_the_version(client):
    assert client.post("/stats", {}).status == 405
    page = client.get("/stats")
    assert page.status == 200
    assert __version__ in page.text
