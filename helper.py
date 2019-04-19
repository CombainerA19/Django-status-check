def is_processing_row(bs4, page_content, css_selector, index):
    soup = bs4.BeautifulSoup(page_content, features="html.parser")
    positive = ["True"]
    is_processing = soup.select(css_selector)[index].get("alt")
    return is_processing in positive