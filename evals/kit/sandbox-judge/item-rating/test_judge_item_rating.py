"""Hidden judge tests for the CR item-rating. Never pushed to the sandbox."""
from html.parser import HTMLParser
from urllib.parse import urlsplit

MESSAGE = "Rating must be a whole number from 1 to 5."


class Select(HTMLParser):
    """The options of <select name="rating">: (value, selected, text)."""

    def __init__(self):
        super().__init__()
        self.options = []
        self._in_select = False
        self._option = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select" and attrs.get("name") == "rating":
            self._in_select = True
        elif tag == "option" and self._in_select:
            self._option = [attrs.get("value"), "selected" in attrs, ""]

    def handle_data(self, data):
        if self._option is not None:
            self._option[2] += data

    def handle_endtag(self, tag):
        if tag == "option" and self._option is not None:
            self.options.append((self._option[0], self._option[1], self._option[2].strip()))
            self._option = None
        elif tag == "select":
            self._in_select = False


def options(html):
    select = Select()
    select.feed(html)
    return select.options


def add(client):
    assert client.post("/items", {"title": "Judge rating item", "url": ""}).status == 303


def test_an_item_has_no_rating_by_default(client):
    add(client)
    assert "Rating: none" in client.get("/items/1").text


def test_a_rating_shows_on_the_item_page_the_list_and_the_select(client):
    add(client)
    response = client.post("/items/1/rating", {"rating": "4"})
    assert response.status == 303
    assert urlsplit(response.headers["location"]).path == "/items/1"
    page = client.get("/items/1").text
    assert "Rating: 4/5" in page
    assert "4/5" in client.get("/").text
    opts = options(page)
    assert [v for v, _, _ in opts] == ["", "1", "2", "3", "4", "5"]
    assert opts[0][2] == "No rating"
    assert [v for v, selected, _ in opts if selected] == ["4"]


def test_an_empty_value_clears_the_rating(client):
    add(client)
    client.post("/items/1/rating", {"rating": "4"})
    assert client.post("/items/1/rating", {"rating": ""}).status == 303
    assert "Rating: none" in client.get("/items/1").text
    assert "4/5" not in client.get("/").text


def test_a_bad_value_is_400_and_changes_nothing(client):
    add(client)
    client.post("/items/1/rating", {"rating": "3"})
    for value in ("0", "6", "x", "2.5"):
        response = client.post("/items/1/rating", {"rating": value})
        assert response.status == 400
        assert MESSAGE in response.text
        assert "Rating: 3/5" in client.get("/items/1").text


def test_an_unknown_item_is_404(client):
    assert client.post("/items/9/rating", {"rating": "3"}).status == 404
