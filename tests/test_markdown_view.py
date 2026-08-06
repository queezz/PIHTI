from pihti_dedup.markdown_view import is_safe_url, plain_text, render


def test_prose_markdown_becomes_html() -> None:
    html = str(render("# Head\n\nA **bold** claim and `code`.\n"))

    assert "<h1>Head</h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<code>code</code>" in html


def test_the_three_mkdocs_extensions_are_enabled() -> None:
    table = str(render("| a | b |\n|---|---|\n| 1 | 2 |\n"))
    fenced = str(render("```python\nx = 1\n```\n"))
    # sane_lists: a bare line under a bullet is a paragraph, not a nested list
    sane = str(render("1. one\n\n* not item two\n"))

    assert "<table>" in table and "<th>a</th>" in table
    assert '<code class="language-python">' in fenced
    assert "<ol>" in sane and "<ul>" in sane


def test_raw_html_is_shown_as_text_rather_than_executed() -> None:
    html = str(render('Before <script>alert(1)</script> after.\n\n<div onclick="x">block</div>\n'))

    assert "<script>" not in html
    assert "<div" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;div onclick=" in html


def test_an_html_comment_stays_invisible_instead_of_becoming_visible_text() -> None:
    html = str(render("<!-- a note to self -->\n\nThe prose.\n"))

    assert "a note to self" not in html
    assert "The prose." in html


def test_unsafe_link_schemes_lose_their_target_but_keep_their_text() -> None:
    html = str(render("[click](javascript:alert(1)) and [ok](https://example.com/a)\n"))

    assert "javascript:" not in html
    assert ">click</a>" in html
    assert 'href="https://example.com/a"' in html
    assert is_safe_url("../sibling/README.md") is True
    assert is_safe_url("#anchor") is True
    assert is_safe_url("mailto:queezz@example.com") is True
    assert is_safe_url("java\nscript:alert(1)") is False
    assert is_safe_url("  JavaScript:alert(1)") is False


def test_plain_text_reduces_markdown_to_one_line_of_prose() -> None:
    assert plain_text("A **bold** [link](https://x.test) and `code`.") == "A bold link and code."
    assert plain_text("") == ""
    assert plain_text("   \n  ") == ""


def test_empty_input_renders_to_nothing_at_all() -> None:
    assert str(render("")) == ""
    assert str(render(None)) == ""
    assert str(render("\n \n")) == ""
