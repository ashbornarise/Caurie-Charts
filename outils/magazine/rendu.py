import sys
from playwright.sync_api import sync_playwright
src, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1588, "height": 1123}, device_scale_factor=1.4)
    pg.goto("file:///" + src.replace("\\", "/"), wait_until="networkidle", timeout=180000); pg.wait_for_timeout(1500)
    casses = pg.evaluate("[...document.images].filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)")
    print("images cassées:", len(casses), casses[:5])
    pg.pdf(path=out, width="420mm", height="297mm", print_background=True, prefer_css_page_size=True)
    for i, el in enumerate(pg.query_selector_all("section.page")):
        el.screenshot(path=f"m{i+1}.png")
    b.close()
print("ok")
