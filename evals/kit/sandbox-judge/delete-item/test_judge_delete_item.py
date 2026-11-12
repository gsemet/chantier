"""Hidden judge tests for the CR delete-item. Never pushed to the sandbox."""
from html.parser import HTMLParser
from urllib.parse import urlsplit


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms.append(dict(attrs))


def add(client, title):
    assert client.post("/items", {"title": title, "url": ""}).status == 303


def test_delete_redirects_to_the_list_and_removes_the_item(client):
    add(client, "Judge delete alpha")
    add(client, "Judge delete beta")
    response = client.post("/items/1/delete", {})
    assert response.status == 303
    assert urlsplit(response.headers["location"]).path == "/"
    page = client.get("/").text
    assert "Judge delete alpha" not in page
    assert "Judge delete beta" in page
    assert client.get("/items/1").status == 404
    assert client.get("/items/2").status == 200


def test_deleting_an_unknown_id_is_404(client):
    add(client, "Judge delete alpha")
    assert client.post("/items/9/delete", {}).status == 404
    assert client.get("/items/1").status == 200


def test_get_on_the_delete_path_is_405(client):
    add(client, "Judge delete alpha")
    assert client.get("/items/1/delete").status == 405
    assert client.get("/items/1").status == 200


def test_an_id_is_never_given_twice(client):
    add(client, "Judge delete first")
    add(client, "Judge delete second")
    assert client.post("/items/2/delete", {}).status == 303
    add(client, "Judge delete third")
    assert "Judge delete third" in client.get("/items/3").text
    assert client.get("/items/2").status == 404


def test_the_item_page_has_a_post_form_to_the_delete_path(client):
    add(client, "Judge delete alpha")
    parser = Forms()
    parser.feed(client.get("/items/1").text)
    assert any(
        form.get("method", "").lower() == "post" and form.get("action") == "/items/1/delete"
        for form in parser.forms
    )
