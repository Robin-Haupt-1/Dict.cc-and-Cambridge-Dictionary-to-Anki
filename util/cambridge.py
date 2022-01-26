def has_results(html: str) -> bool:
    """:param html: html of the page

    check if there are any results for the word
    """
    return "Die beliebtesten Suchbegriffe" not in html
