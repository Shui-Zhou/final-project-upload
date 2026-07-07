"""Capture dashboard screenshots for the final-report figures directory.

Usage (RUNBOOK pattern):
    flask --app src.api.app:create_app run --port 5057   # in one shell
    .venv/bin/python tests/evaluation/capture_dashboard_figures.py

Outputs 2x-scale PNGs under
`report/Final Report Latex Template (Data Science)/figures/dashboard/`.
Captures only states the first-iteration dashboard actually supports
(no footprint-scenario UI, per the deferred UI-toggle decision).
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5057/dashboard"
OUT_DIR = (
    Path(__file__).resolve().parents[2]
    / "report"
    / "Final Report Latex Template (Data Science)"
    / "figures"
    / "dashboard"
)

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def wait_ready(page):
    page.wait_for_selector("#borough-map path", timeout=15_000)
    page.wait_for_selector("#ranking-body tr", timeout=15_000)
    page.wait_for_timeout(600)  # let D3 transitions settle


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Viewport-only captures: full_page stretches the map panel and
        # bottom-anchors the choropleth, which misrepresents what a user sees.
        # 1. Desktop overview, default state.
        ctx = browser.new_context(viewport=DESKTOP, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(BASE_URL)
        wait_ready(page)
        page.locator("#borough-map").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=OUT_DIR / "fig_dashboard_overview_desktop.png")

        # 2. Linked selection: specific borough + month + incident group.
        page.select_option("#borough-select", label="Bromley")
        page.select_option("#month-select", "2025-06")
        page.select_option("#group-select", "False Alarm")
        page.wait_for_timeout(600)
        page.screenshot(path=OUT_DIR / "fig_dashboard_linked_selection.png")

        # 2b. Component-level trend capture at legible print scale.
        page.locator(".timeline-panel").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator(".timeline-panel").screenshot(
            path=OUT_DIR / "fig_dashboard_trend_panel.png"
        )

        # 2c. Component-level ranking table capture with the
        #     precise-coordinate-coverage column (the SQ4 data-quality cue).
        page.add_style_tag(
            content="""
            .table-panel { max-height: none !important; }
            .table-scroll { max-height: none !important; overflow: visible !important; }
            """
        )
        page.locator(".table-panel").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator(".table-panel").screenshot(
            path=OUT_DIR / "fig_dashboard_ranking_table.png"
        )
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(300)

        # 3. Empty-state banner (E4 fix): force an unpopulated combination the
        #    same way the Strand-1 live verification did.
        page.evaluate(
            """() => {
                const sel = document.querySelector('#borough-select');
                const opt = document.createElement('option');
                opt.value = '__no_such_borough__';
                opt.textContent = '__no_such_borough__';
                sel.appendChild(opt);
                sel.value = '__no_such_borough__';
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            }"""
        )
        page.wait_for_selector("#empty-state:not([hidden])", timeout=5_000)
        page.locator("#empty-state").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=OUT_DIR / "fig_dashboard_empty_state.png")
        ctx.close()

        # 4. Mobile viewport (F5 verification state).
        ctx = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True)
        page = ctx.new_page()
        page.goto(BASE_URL)
        wait_ready(page)
        page.screenshot(path=OUT_DIR / "fig_dashboard_mobile_390.png")
        ctx.close()

        browser.close()

    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"{f.name}: {f.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
