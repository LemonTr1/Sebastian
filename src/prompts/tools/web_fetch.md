## Web Fetch

Extract the main text of a web page as plain text or markdown.

- Tries DDGS extraction first, then falls back to requests + BeautifulSoup.
- `timeout` defaults to 20 seconds; the fallback gets 5 extra seconds.
- Returns `content` with the page text; scripts, styles, navigation, and footers are stripped.
- The result is raw page text — read and summarize it yourself.
