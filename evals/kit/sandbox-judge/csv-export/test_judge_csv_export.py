"""Hidden judge tests for the CR csv-export. Never pushed to the sandbox."""
import csv
import io
from html.parser import HTMLParser

HEADER = "id,title,url,status,added\r\n"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))


def add(client, title, url=""):
    assert client.post("/items", {"title": title, "url": url}).status == 303


def rows(client):
    return list(csv.reader(io.StringIO(client.get("/export.csv").text, newline="")))


def test_an_empty_shelf_is_the_header_alone(client):
    response = client.get("/export.csv")
    assert response.status == 200
    assert response.text == HEADER


def test_a_title_with_a_comma_and_quotes_reads_back_the_same(client):
    add(client, 'Hello, "world"', "https://example.com/hw")
    data = rows(client)
    assert data[0] == ["id", "title", "url", "status", "added"]
    assert data[1][:4] == ["1", 'Hello, "world"', "https://example.com/hw", "to-read"]
    assert len(data[1]) == 5


def test_rows_are_in_id_order_and_a_missing_url_is_empty(client):
    add(client, "Judge csv one", "https://example.com/one")
    add(client, "Judge csv two")
    data = rows(client)
    assert [r[0] for r in data[1:]] == ["1", "2"]
    assert [r[1] for r in data[1:]] == ["Judge csv one", "Judge csv two"]
    assert data[2][2] == ""


def test_the_headers(client):
    response = client.get("/export.csv")
    assert response.headers["content-type"].lower() == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="shelf.csv"'


def test_the_list_page_links_to_the_export(client):
    links = Links()
    links.feed(client.get("/").text)
    assert "/export.csv" in links.hrefs


def test_post_is_405(client):
    assert client.post("/export.csv", {}).status == 405
