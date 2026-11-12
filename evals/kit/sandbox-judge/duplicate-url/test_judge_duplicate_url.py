"""Hidden judge tests for the CR duplicate-url. Never pushed to the sandbox."""
from html.parser import HTMLParser


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))


def post(client, title, url=""):
    return client.post("/items", {"title": title, "url": url})


def test_the_same_url_is_refused_with_a_link_to_the_existing_item(client):
    assert post(client, "Judge dup first", "https://example.com/a").status == 303
    response = post(client, "Judge dup second", "https://example.com/a")
    assert response.status == 400
    assert "Already on the shelf:" in response.text
    links = Links()
    links.feed(response.text)
    assert "/items/1" in links.hrefs
    page = client.get("/").text
    assert "Judge dup first" in page
    assert "Judge dup second" not in page


def test_the_host_case_and_a_trailing_slash_do_not_matter(client):
    assert post(client, "Judge dup first", "https://example.com/a").status == 303
    response = post(client, "Judge dup second", "  https://Example.COM/a/ ")
    assert response.status == 400
    assert "Already on the shelf:" in response.text
    assert "Judge dup second" not in client.get("/").text


def test_an_upper_case_scheme_is_refused_whatever_the_reason(client):
    # The base validation only accepts a lower-case scheme, so this is a 400 either way.
    assert post(client, "Judge dup first", "https://example.com/a").status == 303
    assert post(client, "Judge dup second", "HTTPS://Example.com/a/").status == 400
    assert "Judge dup second" not in client.get("/").text


def test_the_path_is_case_sensitive(client):
    assert post(client, "Judge dup first", "https://example.com/a").status == 303
    assert post(client, "Judge dup second", "https://example.com/A").status == 303
    assert "Judge dup second" in client.get("/").text


def test_items_with_no_url_never_clash(client):
    assert post(client, "Judge dup first").status == 303
    assert post(client, "Judge dup second").status == 303
    page = client.get("/").text
    assert "Judge dup first" in page and "Judge dup second" in page


def test_a_different_url_is_added(client):
    assert post(client, "Judge dup first", "https://example.com/a").status == 303
    assert post(client, "Judge dup second", "https://example.com/b").status == 303
    assert "Judge dup second" in client.get("/").text
