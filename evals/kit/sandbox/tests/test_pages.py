import json

from shelf import __version__, store


def test_the_index_shows_an_empty_shelf_and_the_form(client):
    response = client.get("/")
    assert response.status == 200
    assert "Nothing on the shelf yet." in response.text
    assert '<form method="post" action="/items">' in response.text
    assert __version__ in response.text  # the footer


def test_adding_an_item_redirects_and_the_list_shows_it(client):
    response = client.post("/items", {"title": "Dune", "url": "https://example.com/dune"})
    assert (response.status, response.headers["location"]) == (303, "/")
    page = client.get("/").text
    assert 'href="/items/1"' in page and "Dune" in page and "to-read" in page


def test_an_invalid_item_gets_400_with_the_message_and_the_values(client):
    response = client.post("/items", {"title": "", "url": "https://kept.example"})
    assert response.status == 400
    assert "The title is required." in response.text
    assert 'value="https://kept.example"' in response.text
    assert store.load() == []


def test_a_bad_link_gets_400(client):
    assert client.post("/items", {"title": "Dune", "url": "nope"}).status == 400


def test_the_item_page(client):
    client.post("/items", {"title": "Dune", "url": "https://example.com/dune"})
    response = client.get("/items/1")
    assert response.status == 200
    assert "Dune" in response.text and 'href="https://example.com/dune"' in response.text


def test_an_unknown_item_gets_the_404_page(client):
    response = client.get("/items/99")
    assert response.status == 404
    assert "Not Found" in response.text


def test_setting_the_status(client):
    client.post("/items", {"title": "Dune"})
    response = client.post("/items/1/status", {"status": "reading"})
    assert (response.status, response.headers["location"]) == (303, "/items/1")
    assert store.get(1)["status"] == "reading"


def test_a_status_must_be_known_and_the_item_must_exist(client):
    client.post("/items", {"title": "Dune"})
    assert client.post("/items/1/status", {"status": "lost"}).status == 400
    assert client.post("/items/9/status", {"status": "done"}).status == 404
    assert store.get(1)["status"] == "to-read"


def test_user_text_is_escaped(client):
    client.post("/items", {"title": "<script>alert(1)</script>", "url": 'https://x.example/"><b>'})
    for page in (client.get("/").text, client.get("/items/1").text):
        assert "<script>" not in page and "<b>" not in page
        assert "&lt;script&gt;" in page


def test_the_error_message_and_values_are_escaped(client):
    page = client.post("/items", {"title": "", "url": '"><i>'}).text
    assert "<i>" not in page


def test_unknown_paths_get_404_and_wrong_methods_get_405(client):
    assert client.get("/nope").status == 404
    assert client.get("/items").status == 405
    assert client.post("/", {}).status == 405
    assert client.get("/items/1/status").status == 405
    assert client.post("/healthz", {}).status == 405


def test_a_query_string_is_not_part_of_the_path(client):
    assert client.get("/?status=done").status == 200


def test_the_stylesheet(client):
    response = client.get("/static/style.css")
    assert response.status == 200
    assert response.headers["content-type"].startswith("text/css")


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status == 200
    assert json.loads(response.text) == {"status": "ok", "version": __version__}
