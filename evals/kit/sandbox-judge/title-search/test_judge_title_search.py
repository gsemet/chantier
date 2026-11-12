"""Hidden judge tests for the CR title-search. Never pushed to the sandbox."""
from html.parser import HTMLParser


class Forms(HTMLParser):
    """Each <form>: its attributes and the names of the inputs inside."""

    def __init__(self):
        super().__init__()
        self.forms = []
        self.inputs = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._form = {"attrs": attrs, "inputs": []}
            self.forms.append(self._form)
        elif tag == "input":
            self.inputs.append(attrs)
            if self._form is not None:
                self._form["inputs"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None


def parse(html):
    forms = Forms()
    forms.feed(html)
    return forms


def seed(client):
    for title in ("Dune Messiah", "Foundation"):
        assert client.post("/items", {"title": title, "url": ""}).status == 303


def test_the_search_ignores_case(client):
    seed(client)
    page = client.get("/?q=DUNE").text
    assert "Dune Messiah" in page
    assert "Foundation" not in page


def test_a_blank_query_shows_everything(client):
    seed(client)
    for path in ("/", "/?q=", "/?q=%20%20"):
        page = client.get(path).text
        assert "Dune Messiah" in page and "Foundation" in page


def test_the_query_is_escaped_in_the_input_and_in_the_message(client):
    seed(client)
    response = client.get("/?q=<i>")
    assert response.status == 200
    assert 'value="&lt;i&gt;"' in response.text
    inputs = {i.get("name"): i for i in parse(response.text).inputs}
    assert inputs["q"].get("value") == "<i>"
    assert 'No items match "&lt;i&gt;".' in response.text
    assert "<i>" not in response.text


def test_the_form_is_a_get_form_to_the_list(client):
    forms = parse(client.get("/").text).forms
    assert any(
        f["attrs"].get("method", "").lower() == "get"
        and f["attrs"].get("action") == "/"
        and any(i.get("name") == "q" for i in f["inputs"])
        for f in forms
    )
