import json
import time
from pathlib import Path
from threading import Lock
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from src.tools.tools_registry import get_tools_registry

_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_playwright = None
_lock = Lock()

HOME = str(Path.home())
DEFAULT_SCREENSHOT_DIR = Path(HOME) / "图片" / "screenshots"


def _ensure_browser() -> Page:
    global _browser, _context, _page, _playwright
    if _page is None or _page.is_closed():
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
        _context = _browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="zh-CN",
        )
        def _intercept_popup(new_page):
            try:
                cur = _page
                target_url = new_page.url
                if not target_url or target_url == "about:blank":
                    new_page.wait_for_load_state("domcontentloaded", timeout=5000)
                    target_url = new_page.url
                new_page.close()
                if target_url and target_url != "about:blank" and cur and not cur.is_closed():
                    cur.goto(target_url, wait_until="domcontentloaded")
            except Exception:
                pass  # popup may already be closed, best-effort intercept
        _page = _context.new_page()
        _context.on("page", _intercept_popup)
    return _page


def _close_browser():
    global _browser, _context, _page, _playwright
    if _page:
        _page.close()
        _page = None
    if _context:
        _context.close()
        _context = None
    if _browser:
        _browser.close()
        _browser = None
    if _playwright:
        _playwright.stop()
        _playwright = None


def _ok(**kwargs):
    return json.dumps(
        {
            "success": True,
            **kwargs
        },
        ensure_ascii=False
    )


def _err(msg):
    return json.dumps(
        {
            "success": False,
            "summary": msg
        },
        ensure_ascii=False
    )


def browser_launch(url: str = "") -> str:
    try:
        with _lock:
            page = _ensure_browser()
            if url:
                page.goto(url, wait_until="domcontentloaded")
                title = page.title()
                return _ok(title=title, url=page.url)
            return _ok(title="about:blank", url="about:blank")
    except Exception as e:
        return _err(f"启动浏览器失败: {e}")


def browser_info() -> str:
    try:
        with _lock:
            page = _ensure_browser()
            return _ok(url=page.url, title=page.title())
    except Exception as e:
        return _err(f"获取页面信息失败: {e}")


def browser_navigate(url: str, timeout: int = 30000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            resp = page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            title = page.title()
            return _ok(url=page.url, title=title, status=resp.status if resp else None)
    except Exception as e:
        return _err(f"导航失败: {e}")


def browser_click(selector: str, timeout: int = 10000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            before = page.url
            page.locator(selector).first.click(timeout=timeout)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=timeout)
            except Exception:
                pass
            cur = page.url
            return _ok(selector=selector, url=cur, title=page.title(), url_changed=(cur != before))
    except Exception as e:
        return _err(f"点击失败: {e}")


def browser_fill(selector: str, text: str, timeout: int = 10000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            el = page.locator(selector).first
            el.fill("", timeout=timeout)
            el.fill(text, timeout=timeout)
            return _ok(selector=selector, filled=text)
    except Exception as e:
        return _err(f"填写失败: {e}")


def browser_screenshot(name: str = "screenshot", full_page: bool = False, save_dir: str = "", timeout: int = 15000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            if not save_dir:
                save_dir = str(DEFAULT_SCREENSHOT_DIR)
            target_dir = Path(save_dir).expanduser().resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            filepath = target_dir / f"{name}.png"
            page.screenshot(path=str(filepath), full_page=full_page, timeout=timeout)
            vp = page.viewport_size or {"width": 0, "height": 0}
            return _ok(filepath=str(filepath), dimensions=f"{vp['width']}x{vp['height']}")
    except Exception as e:
        return _err(f"截图失败: {e}")


def browser_scroll(direction: str = "down", amount: int = 500, selector: str = "", timeout: int = 10000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            deltas = {"down": (0, amount), "up": (0, -amount), "right": (amount, 0), "left": (-amount, 0)}
            dx, dy = deltas.get(direction, (0, amount))
            target = page.locator(selector).first if selector else page
            target.evaluate(f"window.scrollBy({dx}, {dy})")
            time.sleep(0.5)
            return _ok(direction=direction, amount=amount)
    except Exception as e:
        return _err(f"滚动失败: {e}")


def browser_wait(target: str, timeout: int = 15000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            if target == "load":
                page.wait_for_load_state("networkidle", timeout=timeout)
                return _ok(waited="page load complete")
            elif target.isdigit():
                time.sleep(int(target) / 1000)
                return _ok(waited=f"{target}ms")
            else:
                page.wait_for_selector(target, state="visible", timeout=timeout)
                return _ok(waited=f"selector '{target}' visible")
    except Exception as e:
        return _err(f"等待失败: {e}")


def browser_js(code: str, timeout: int = 10000) -> str:
    try:
        with _lock:
            page = _ensure_browser()
            result = page.evaluate("(code) => eval(code)", code)
            return _ok(result=result)
    except Exception as e:
        return _err(f"JS执行失败: {e}")


def browser_get_cookies(url_filter: str = "") -> str:
    try:
        with _lock:
            _ensure_browser()
            if url_filter:
                cookies = _context.cookies(url_filter) if _context else []
            else:
                cookies = _context.cookies() if _context else []
            return _ok(cookies=cookies, count=len(cookies))
    except Exception as e:
        return _err(f"获取Cookie失败: {e}")


def browser_set_cookies(cookies_json: str) -> str:
    try:
        with _lock:
            _ensure_browser()
            if not _context:
                return _err("浏览器未初始化")
            cookies = json.loads(cookies_json)
            _context.add_cookies(cookies)
            return _ok(set_count=len(cookies))
    except json.JSONDecodeError as e:
        return _err(f"Cookie JSON解析失败: {e}")
    except Exception as e:
        return _err(f"设置Cookie失败: {e}")


def browser_close() -> str:
    try:
        with _lock:
            _close_browser()
            return _ok(summary="浏览器已关闭")
    except Exception as e:
        return _err(f"关闭浏览器失败: {e}")


# ── Schemas ──
def _browser_schema(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {
            "type": "object",
            "properties": {
                **props,
            },
            "required": required,
        },
    }}

BROWSER_LAUNCH_SCHEMA = _browser_schema("browser_launch", "启动浏览器窗口，可选加载初始URL", {"url": {"type": "string"}}, ["url"])
BROWSER_INFO_SCHEMA = _browser_schema("browser_info", "获取当前标签页的URL和标题", {}, [])
BROWSER_NAVIGATE_SCHEMA = _browser_schema("browser_navigate", "导航到指定URL", {"url": {"type": "string"}, "timeout": {"type": "integer"}}, ["url"])
BROWSER_CLICK_SCHEMA = _browser_schema("browser_click", "点击页面元素", {"selector": {"type": "string"}, "timeout": {"type": "integer"}}, ["selector"])
BROWSER_FILL_SCHEMA = _browser_schema("browser_fill", "填写输入框内容", {"selector": {"type": "string"}, "text": {"type": "string"}, "timeout": {"type": "integer"}}, ["selector", "text"])
BROWSER_SCREENSHOT_SCHEMA = _browser_schema("browser_screenshot", "截取页面截图保存到本地", {"name": {"type": "string"}, "full_page": {"type": "boolean"}, "save_dir": {"type": "string"}, "timeout": {"type": "integer"}}, ["name"])
BROWSER_SCROLL_SCHEMA = _browser_schema("browser_scroll", "滚动页面", {"direction": {"type": "string"}, "amount": {"type": "integer"}, "selector": {"type": "string"}, "timeout": {"type": "integer"}}, ["direction"])
BROWSER_WAIT_SCHEMA = _browser_schema("browser_wait", "等待元素/加载/延时", {"target": {"type": "string"}, "timeout": {"type": "integer"}}, ["target"])
BROWSER_JS_SCHEMA = _browser_schema("browser_js", "在页面执行JS代码", {"code": {"type": "string"}, "timeout": {"type": "integer"}}, ["code"])
BROWSER_GET_COOKIES_SCHEMA = _browser_schema("browser_get_cookies", "获取浏览器Cookie", {"url_filter": {"type": "string"}}, ["url_filter"])
BROWSER_SET_COOKIES_SCHEMA = _browser_schema("browser_set_cookies", "设置浏览器Cookie", {"cookies_json": {"type": "string"}}, ["cookies_json"])
BROWSER_CLOSE_SCHEMA = _browser_schema("browser_close", "关闭浏览器", {}, [])

get_tools_registry().register_tool("browser_launch", browser_launch, BROWSER_LAUNCH_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_info", browser_info, BROWSER_INFO_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_navigate", browser_navigate, BROWSER_NAVIGATE_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_click", browser_click, BROWSER_CLICK_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_fill", browser_fill, BROWSER_FILL_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_screenshot", browser_screenshot, BROWSER_SCREENSHOT_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_scroll", browser_scroll, BROWSER_SCROLL_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_wait", browser_wait, BROWSER_WAIT_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_js", browser_js, BROWSER_JS_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_get_cookies", browser_get_cookies, BROWSER_GET_COOKIES_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_set_cookies", browser_set_cookies, BROWSER_SET_COOKIES_SCHEMA, for_agent="Web_Agent")
get_tools_registry().register_tool("browser_close", browser_close, BROWSER_CLOSE_SCHEMA, for_agent="Web_Agent")
