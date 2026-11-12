# Answers

- Two read-only routes: the list and one item; nothing to write through the API.
- Titles are given as entered, not HTML-escaped: JSON is not HTML.
- An unknown id answers 404 with a small JSON error body, not the HTML page.
- The list page links to the API.
