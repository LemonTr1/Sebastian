## Web Search

Search the web by keyword. Uses DuckDuckGo first and automatically falls back to Baidu on failure.

- Returns a result list with title, abstract, URL, and rank.
- `max_results` defaults to 10; `timeout` defaults to 20 seconds.
- Use specific queries; follow up with `web_fetch` on the most relevant URLs.
- Treat snippets as leads, not verified facts — confirm critical details from the page.
