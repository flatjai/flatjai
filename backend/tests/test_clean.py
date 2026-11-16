from conftest import LIST_HTML, LISTING_HTML

from flatjai.tools.clean import html_to_text, page_links, page_title


def test_drops_scripts_nav_and_footer():
    text = html_to_text(LISTING_HTML)
    assert "99,999" not in text  # inside <script>
    assert "Someone" not in text  # footer
    assert "Test Court・Block 1" in text


def test_glues_split_dollar_figures():
    lines = html_to_text(LISTING_HTML).split("\n")
    assert "$12,800" in lines
    assert lines[lines.index("$12,800") - 1] == "Rent"


def test_collapses_repeated_lines_and_whitespace():
    assert html_to_text("<body><p>a</p><p>a</p><p>b    c</p></body>") == "a\nb c"


def test_truncates_to_budget():
    assert len(html_to_text(LISTING_HTML, max_chars=20)) == 20


def test_links_are_absolute_and_unique():
    links = page_links(LIST_HTML, "https://hk.centanet.com/findproperty/en/list/rent")
    assert links[0] == "https://hk.centanet.com/findproperty/en/detail/Test-Court-Block-1_ABC123?theme=rent"
    assert len(links) == 3


def test_title():
    assert page_title(LISTING_HTML).startswith("Hang Hau｜TEST COURT")
