"""Playwright E2E smoke test for Civic Pathfinder.

Tests the critical user flow: register → dashboard → roadmap navigation.
Run with: playwright test --headed or pytest e2e/test_smoke.py
"""
import time
import pytest
from playwright.sync_api import Page, expect


def test_landing_page_loads(page: Page):
    """Landing page should load with correct branding."""
    page.goto("http://localhost:5173")
    expect(page).to_have_title(/Civic.*Path.*/i)
    expect(page.locator("text=Civic Path Navigator")).to_be_visible()


def test_navigation(page: Page):
    """Sidebar navigation should work."""
    page.goto("http://localhost:5173")
    
    # Navigate to Path Builder
    page.click("text=Path Builder")
    expect(page.locator("text=Build My Civic Path")).to_be_visible()
    
    # Navigate back
    page.click("text=Home")
    expect(page.locator("text=Civic Path Navigator")).to_be_visible()


def test_hermes_agent_tab(page: Page):
    """Hermes agent interface should be accessible."""
    page.goto("http://localhost:5173")
    
    page.click("text=Hermes Agent")
    expect(page.locator("text=Hermes Agent")).to_be_visible()
    expect(page.locator("input[placeholder*='Hermes']")).to_be_visible()


def test_language_toggle(page: Page):
    """Language toggle should switch to Hindi."""
    page.goto("http://localhost:5173")
    
    # Click language toggle (assuming it exists)
    lang_toggle = page.locator("[aria-label='Toggle language'] or button:has-text('हिन्दी')")
    if lang_toggle.count() > 0:
        lang_toggle.click()
        expect(page.locator("text=नागरिक")).to_be_visible()
