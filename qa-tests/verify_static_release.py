"""Static release safety checks for the ParentWise website (manual Telegram checkout).

Usage: python qa-tests/verify_static_release.py HOME.html CHECKOUT.html ROBOTS.txt

These replace the old checks that pinned one exact homepage file fingerprint and expected the old
non-payable walkthrough. They keep what matters for the CURRENT approved launch model:
  * the order system is closed and the page contains no backend address,
  * no payment processor, external script or form posts anywhere,
  * only the approved manual recipients are present (any change fails on purpose, so a recipient can
    never change without someone updating this file),
  * only the approved price is shown, and forbidden wording is absent,
  * the order-submission gate and the three-step navigation still exist.
Preview-only rules (noindex, robots Disallow) are listed separately: REMOVE THEM AT LAUNCH.
"""
import re
import sys
from pathlib import Path

APPROVED_RECIPIENTS = {"0912910693", "1000220596536"}   # Telebirr, CBE (manual payment)
APPROVED_PRICES = {"1,500"}
TELEGRAM = "https://t.me/ParentWiseEthiopia"

home = Path(sys.argv[1]).read_text(encoding="utf-8")
checkout = Path(sys.argv[2]).read_text(encoding="utf-8")
robots = Path(sys.argv[3]).read_text(encoding="utf-8")
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def recipients(text):
    return set(re.findall(r"(?<![0-9])(?:0[97][0-9]{8}|1000[0-9]{9})(?![0-9])", text))


for name, page in (("homepage", home), ("checkout", checkout)):
    check(not re.search(r"<script[^>]+src=[\"']https?:", page, re.I), f"{name}: external script found")
    check(not re.search(r"<form[^>]+action=", page, re.I), f"{name}: a form posts somewhere")
    check(not re.search(r"subscription", page, re.I), f"{name}: forbidden word 'subscription'")
    prices = {m.group(1) for m in re.finditer(r"([0-9][0-9,]*)\s?ብር", page)}
    check(prices <= APPROVED_PRICES, f"{name}: unapproved price(s) {sorted(prices - APPROVED_PRICES)}")
    check(prices, f"{name}: approved price {sorted(APPROVED_PRICES)} not shown")

# homepage
check(len(home) > 100_000, "homepage looks incomplete (too small)")
check('href="order.html"' in home, "homepage: call-to-action to order.html missing")
check(not recipients(home), "homepage must not contain payment recipient numbers")

# checkout: order system closed, no backend address, approved recipients only
check("CHECKOUT_OPEN = false" in checkout, "checkout: order system must stay closed (CHECKOUT_OPEN = false)")
check("ORDER_API_ORIGIN = ''" in checkout, "checkout: page must contain no backend address (ORDER_API_ORIGIN = '')")
found = recipients(checkout)
check(found == APPROVED_RECIPIENTS, f"checkout: recipients {sorted(found)} differ from approved {sorted(APPROVED_RECIPIENTS)}")
check(TELEGRAM in checkout, "checkout: Telegram destination missing")
check("QA-TELEBIRR-ONLY" not in checkout and "QA-CBE-ONLY" not in checkout, "checkout: QA placeholder accounts present")
check("if((!enabled&&!previewOnly)||busy)" in checkout, "checkout: order-submission gate missing")
for element in ("continue-payment", "paid-action", "change-method", "back-payment", "back-telegram", "telegram-handoff"):
    check(f'id="{element}"' in checkout, f"checkout: #{element} missing")

# PREVIEW-ONLY rules. REMOVE AT LAUNCH (when the site is meant to be found in search).
check("noindex" in home and "noindex" in checkout, "preview: noindex missing (remove this rule at launch)")
check("Disallow: /" in robots, "preview: robots Disallow missing (remove this rule at launch)")

if failures:
    print("RELEASE CHECK FAILED:")
    for item in failures:
        print(" -", item)
    sys.exit(1)
print("PASS: closed order system, no backend address, approved recipients and price only, no external scripts, gates present")
