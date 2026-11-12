"""Hidden judge tests for the CR status-filter. Never pushed to the sandbox."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit


class Nav(HTMLParser):
    """The links of the first <nav class="filters">: (text, attributes)."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._in_nav = False
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and "filters" in (attrs.get("class") or "").split():
            self._in_nav = True
        elif tag == "a" and self._in_nav:
            self._link = [attrs, ""]

    def handle_data(self, data):
        if self._link is not None:
            self._link[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append((self._link[1].strip(), self._link[0]))
            self._link = None
        elif tag == "nav":
            self._in_nav = False


def filters(html):
    nav = Nav()
    nav.feed(html)
    return nav.links


def seed(client):
    for title in ("Judge filter alpha", "Judge filter beta", "Judge filter gamma"):
        assert client.post("/items", {"title": title, "url": ""}).status == 303
    assert client.post("/items/2/status", {"status": "reading"}).status == 303
    assert client.post("/items/3/status", {"status": "done"}).status == 303


def test_a_status_shows_only_its_items(client):
    seed(client)
    page = client.get("/?status=reading").text
    assert "Judge filter beta" in page
    assert "Judge filter alpha" not in page
    assert "Judge filter gamma" not in page


def test_an_empty_status_shows_everything(client):
    seed(client)
    page = client.get("/?status=").text
    for title in ("Judge filter alpha", "Judge filter beta", "Judge filter gamma"):
        assert title in page


def test_an_unknown_status_is_400_and_escaped(client):
    seed(client)
    response = client.get("/?status=lost")
    assert response.status == 400
    assert "Unknown status: lost" in response.text
    response = client.get("/?status=<b>")
    assert response.status == 400
    assert "Unknown status: &lt;b&gt;" in response.text
    assert "<b>" not in response.text


def test_the_four_links_in_order(client):
    seed(client)
    links = filters(client.get("/").text)
    assert [text for text, _ in links] == ["All", "To read", "Reading", "Done"]
    wanted = [None, "to-read", "reading", "done"]
    for (_, attrs), status in zip(links, wanted):
        parts = urlsplit(attrs["href"])
        assert parts.path == "/"
        assert parse_qs(parts.query).get("status", [None]) == [status]


def current(html):
    return [text for text, attrs in filters(html) if attrs.get("aria-current") == "page"]


def test_aria_current_marks_the_current_filter_only(client):
    seed(client)
    assert current(client.get("/").text) == ["All"]
    assert current(client.get("/?status=done").text) == ["Done"]
    assert current(client.get("/?status=reading").text) == ["Reading"]


def test_a_filter_with_no_match_says_so(client):
    assert client.post("/items", {"title": "Judge filter alpha", "url": ""}).status == 303
    response = client.get("/?status=done")
    assert response.status == 200
    assert "No items with this status." in response.text
    assert "Judge filter alpha" not in response.text
