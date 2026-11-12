"""Hidden judge tests for the CR edit-item. Never pushed to the sandbox."""
from html.parser import HTMLParser
from urllib.parse import urlsplit


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))
        if tag == "a":
            self.links.append(dict(attrs))


def parse(html):
    page = Page()
    page.feed(html)
    return page


def add(client, title, url=""):
    assert client.post("/items", {"title": title, "url": url}).status == 303


def test_the_edit_page_holds_the_current_values_escaped(client):
    add(client, "Tom & Jerry <3>", "https://example.com/tj")
    response = client.get("/items/1/edit")
    assert response.status == 200
    assert "Tom &amp; Jerry &lt;3&gt;" in response.text
    inputs = {i.get("name"): i for i in parse(response.text).inputs}
    assert inputs["title"].get("value") == "Tom & Jerry <3>"
    assert inputs["url"].get("value") == "https://example.com/tj"


def test_a_valid_edit_redirects_and_shows_the_new_title(client):
    add(client, "Judge edit old title", "https://example.com/old")
    response = client.post("/items/1/edit", {"title": "  Judge edit new title ", "url": "https://example.com/new"})
    assert response.status == 303
    assert urlsplit(response.headers["location"]).path == "/items/1"
    page = client.get("/items/1").text
    assert "Judge edit new title" in page
    assert "Judge edit old title" not in page
    assert "https://example.com/new" in page


def test_an_invalid_edit_is_400_and_changes_nothing(client):
    add(client, "Judge edit old title", "https://example.com/old")
    for data in (
        {"title": "", "url": "https://example.com/old"},
        {"title": "x" * 201, "url": "https://example.com/old"},
        {"title": "Judge edit bad link", "url": "ftp://x"},
    ):
        assert client.post("/items/1/edit", data).status == 400
        page = client.get("/items/1").text
        assert "Judge edit old title" in page
        assert "Judge edit bad link" not in page
        assert "x" * 201 not in page


def test_an_unknown_id_is_404_on_get_and_post(client):
    assert client.get("/items/9/edit").status == 404
    assert client.post("/items/9/edit", {"title": "Judge edit x", "url": ""}).status == 404


def test_the_item_page_links_to_the_edit_page(client):
    add(client, "Judge edit old title")
    assert any(link.get("href") == "/items/1/edit" for link in parse(client.get("/items/1").text).links)
