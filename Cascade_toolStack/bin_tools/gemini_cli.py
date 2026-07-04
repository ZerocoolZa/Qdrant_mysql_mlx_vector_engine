"""
gemini_cli.py — Chat with Gemini via browser automation (no API key needed)

Usage:
    python3 gemini_cli.py "your prompt here"
    python3 gemini_cli.py --interactive    # multi-turn chat mode
    python3 gemini_cli.py --headed "prompt"  # show browser window

Uses your existing Chrome profile so you're already logged in.
First run: browser opens, you log into Google once, it stays logged in.
"""

import sys
import time
import argparse
import os
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

GEMINI_URL = "https://gemini.google.com/app"
CHROME_PROFILE = str(Path.home() / "Library/Application Support/Google/Chrome")
USER_DATA_DIR = str(Path.home() / ".gemini_cli_profile")
RESPONSE_TIMEOUT = 90000  # 90 seconds max for response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("gemini_cli")


def cleanup_stale_locks():
    """Remove stale Chrome SingletonLock files that prevent browser launch."""
    profile = Path(USER_DATA_DIR)
    if not profile.exists():
        return
    for lockfile in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = profile / lockfile
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def create_browser(playwright, headed=False):
    """Launch Chromium with persistent context for login persistence."""
    cleanup_stale_locks()
    browser = playwright.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=not headed,
        channel="chrome",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        viewport={"width": 1280, "height": 900},
    )
    return browser


INPUT_SELECTORS = [
    'rich-textarea [contenteditable="true"]',
    'div[contenteditable="true"]',
    'textarea',
    'rich-textarea div[role="textbox"]',
    '.ql-editor[contenteditable="true"]',
]


def wait_for_login(page):
    """Check if we're logged in by looking for the Gemini input box."""
    page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=15000)

    # If we got redirected to Google login, we're not logged in
    if "accounts.google.com" in page.url:
        return False

    # Wait for input box with short timeout — if it appears, we're logged in
    for sel in INPUT_SELECTORS:
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            if el and el.is_visible():
                return True
        except (PlaywrightTimeout, Exception):
            continue

    return False


RESPONSE_SELECTORS = [
    'model-response .markdown-main-panel',
    '.model-response-text',
    'model-response .message-content',
    'div[data-message-author="model"]',
    '.conversation-container > div:last-child',
]


def get_latest_response(page, old_text=""):
    """Try to read latest Gemini response. Returns text or empty string."""
    for i, sel in enumerate(RESPONSE_SELECTORS):
        try:
            els = page.query_selector_all(sel)
            if els:
                text = els[-1].inner_text()
                if text and text != old_text:
                    log.debug(f"Response found via selector {i}: {sel} ({len(text)} chars)")
                    return text
        except Exception as e:
            log.debug(f"Selector {sel} failed: {e}")
            continue
    return ""


def send_prompt(page, prompt):
    """Type prompt into Gemini's input box and submit."""
    input_el = None
    for sel in INPUT_SELECTORS:
        try:
            input_el = page.wait_for_selector(sel, timeout=5000)
            if input_el:
                log.debug(f"Input found via: {sel}")
                break
        except PlaywrightTimeout:
            continue
        except Exception as e:
            log.warning(f"Input selector {sel} error: {e}")
            continue

    if not input_el:
        raise RuntimeError("Could not find Gemini input box. The UI may have changed.")

    input_el.click()
    time.sleep(0.1)
    input_el.type(prompt, delay=0)
    time.sleep(0.2)
    page.keyboard.press("Enter")
    log.info(f"Prompt sent ({len(prompt)} chars)")


def extract_response(page, old_text=""):
    """Poll for response — check first, sleep only if no value yet."""
    current_text = ""
    last_text = ""
    stable_count = 0
    max_iterations = 120  # 60s max
    start_time = time.time()

    for i in range(max_iterations):
        elapsed = time.time() - start_time
        current_text = get_latest_response(page, old_text)

        if not current_text:
            if elapsed > 10 and i % 20 == 0:
                log.warning(f"No response after {elapsed:.0f}s (iteration {i})")
            time.sleep(0.5)
            continue

        # Got a value — check if stable (same as last check)
        if current_text == last_text:
            stable_count += 1
            if stable_count >= 2:  # Stable for 2 checks = done
                log.info(f"Response stable after {elapsed:.1f}s ({len(current_text)} chars)")
                return current_text
        else:
            # Still changing (Gemini still typing)
            stable_count = 0
            last_text = current_text
            if i % 10 == 0:
                log.debug(f"Still typing... {len(current_text)} chars at {elapsed:.1f}s")

        time.sleep(0.3)

    if current_text:
        log.warning(f"Response not fully stable after {time.time() - start_time:.1f}s, returning best effort")
        return current_text
    log.error(f"No response detected after {time.time() - start_time:.1f}s")
    return "[No response detected — UI may have changed]"


def run_single(prompt, headed=False):
    """Send one prompt to Gemini and return the response."""
    with sync_playwright() as p:
        browser = create_browser(p, headed=headed)
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            logged_in = wait_for_login(page)
            if not logged_in:
                if not headed:
                    log.error("Not logged in. Run with --headed first to log in:")
                    log.error("  python3 gemini_cli.py --headed 'test'")
                    browser.close()
                    return None
                else:
                    log.info("Please log into your Google account in the browser window...")
                    log.info("Waiting for login (up to 5 minutes)...")
                    try:
                        page.wait_for_url("**/gemini.google.com/**", timeout=300000)
                        time.sleep(3)
                    except PlaywrightTimeout:
                        log.error("Login timeout.")
                        browser.close()
                        return None

            old_text = get_latest_response(page)
            log.debug(f"Old text baseline: {len(old_text)} chars")

            send_prompt(page, prompt)
            response = extract_response(page, old_text)
            browser.close()
            return response
        except Exception as e:
            log.error(f"run_single failed: {e}", exc_info=True)
            browser.close()
            return None



def run_interactive(headed=False):
    """Multi-turn chat mode."""
    print("=== Gemini CLI Interactive Mode ===")
    print("Type your message and press Enter. Type 'quit' or 'exit' to leave.\n")

    with sync_playwright() as p:
        browser = create_browser(p, headed=headed)
        page = browser.pages[0] if browser.pages else browser.new_page()

        logged_in = wait_for_login(page)
        if not logged_in:
            if not headed:
                print("[ERROR] Not logged in. Run with --headed first to log in:")
                print("  python3 gemini_cli.py --headed 'test'")
                browser.close()
                return
            else:
                print("[INFO] Please log into your Google account in the browser window...")
                try:
                    page.wait_for_url("**/gemini.google.com/**", timeout=300000)
                    time.sleep(3)
                except PlaywrightTimeout:
                    print("[ERROR] Login timeout.")
                    browser.close()
                    return

        print("[OK] Connected to Gemini. Start chatting!\n")

        while True:
            try:
                user_input = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[BYE]")
                break

            if user_input.lower() in ("quit", "exit", ":q"):
                print("[BYE]")
                break
            if not user_input:
                continue

            # Get old text for comparison
            old_text = get_latest_response(page)

            print("gemini> ...", end="\r", flush=True)
            send_prompt(page, user_input)
            response = extract_response(page, old_text)

            if response:
                print(f"gemini> {response}\n")
            else:
                print("gemini> [No response detected]\n")

        browser.close()


def main():
    parser = argparse.ArgumentParser(description="Chat with Gemini via browser automation")
    parser.add_argument("prompt", nargs="*", help="Your prompt to Gemini")
    parser.add_argument("--interactive", "-i", action="store_true", help="Multi-turn chat mode")
    parser.add_argument("--headed", action="store_true", help="Show browser window (needed for first login)")
    args = parser.parse_args()

    if args.interactive:
        run_interactive(headed=args.headed)
    elif args.prompt:
        prompt = " ".join(args.prompt)
        response = run_single(prompt, headed=args.headed)
        if response:
            print(response)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
