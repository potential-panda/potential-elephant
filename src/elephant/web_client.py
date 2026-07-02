import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

DEFAULT_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]


@dataclass
class WebPageSession:
    playwright: object
    browser: Browser
    context: BrowserContext
    page: Page

    async def close(self) -> None:
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()


@asynccontextmanager
async def open_web_page(
    *,
    user_agent: str | None = None,
    locale: str = "ja-JP",
    timezone_id: str = "Asia/Tokyo",
    viewport: dict | None = None,
    color_scheme: str = "light",
    extra_http_headers: dict | None = None,
    browser_args: list[str] | None = None,
) -> Page:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=list(browser_args or DEFAULT_BROWSER_ARGS),
    )
    context = await browser.new_context(
        user_agent=user_agent or random.choice(USER_AGENTS),
        locale=locale,
        timezone_id=timezone_id,
        viewport=viewport or {"width": 1365, "height": 900},
        device_scale_factor=1,
        color_scheme=color_scheme,
        extra_http_headers=extra_http_headers
        or {
            "Accept-Language": f"{locale},ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    session = WebPageSession(playwright=playwright, browser=browser, context=context, page=page)
    try:
        yield page
    finally:
        await session.close()


async def visit_page(
    page: Page,
    url: str,
    *,
    wait_until: str = "domcontentloaded",
    timeout: int = 60000,
    jitter: tuple[float, float] | None = None,
    label: str | None = None,
):
    if jitter:
        low, high = jitter
        delay = random.uniform(low, high)
        if delay > 0:
            if label:
                print(f"[{label}] Waiting {delay:.2f}s before loading {url}...")
            else:
                print(f"Waiting {delay:.2f}s before loading {url}...")
            await asyncio.sleep(delay)
    return await page.goto(url, wait_until=wait_until, timeout=timeout)


async def page_has_selector(page: Page, url: str, selector: str, *, timeout: int = 20000, jitter: tuple[float, float] | None = None):
    try:
        response = await visit_page(page, url, timeout=60000, wait_until="domcontentloaded", jitter=jitter)
        if response and response.status >= 400:
            return False, f"HTTP {response.status}"
        await page.wait_for_selector(selector, timeout=timeout)
        return True, None
    except Exception as exc:
        return False, str(exc)
