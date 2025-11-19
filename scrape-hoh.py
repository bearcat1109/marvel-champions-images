import os
import re
import asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import hashlib

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


URL = "https://hallofheroeslcg.com/sinister-motives/"

TARGET_SECTIONS = [
    "ghost-spider",
    "gwen stacy",
    "miles morales",
    "spider-man"
]

OUTPUT_DIR = "sinister_motives_fullres"


def clean_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name)
    return name


async def scrape():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0")

        print("Loading page…")
        await page.goto(URL, wait_until="networkidle")

        # Make sure images load
        await page.wait_for_selector("img", timeout=20000)

        print("Scanning DOM for cards…")

        # Extract everything inside the browser for reliability
        cards = await page.evaluate("""
        () => {
            function normalize(t) {
                return t ? t.toLowerCase().trim() : "";
            }

            const targets = %s;

            // Locate section headers first
            const sections = [];
            document.querySelectorAll("h1, h2, h3").forEach(h => {
                const text = normalize(h.innerText);
                if (targets.some(t => text.includes(t))) {
                    sections.push(h);
                }
            });

            const results = [];

            for (const header of sections) {
                const sectionText = header.innerText.trim();

                // Look at all images AFTER this header until the next header
                let current = header.nextElementSibling;

                while (current && !["H1","H2","H3"].includes(current.tagName)) {

                    // <img src="...">
                    current.querySelectorAll("img").forEach(img => {
                        const src = img.getAttribute("src");
                        if (!src) return;

                        results.push({
                            url: src,
                            alt: img.getAttribute("alt") || "",
                            section: sectionText
                        });
                    });

                    // <figure style="background-image:url(...)">
                    current.querySelectorAll("figure").forEach(fig => {
                        const style = fig.getAttribute("style") || "";
                        const match = style.match(/url\\(['"]?(.*?)['"]?\\)/);
                        if (match) {
                            results.push({
                                url: match[1],
                                alt: "",
                                section: sectionText
                            });
                        }
                    });

                    current = current.nextElementSibling;
                }
            }

            return results;
        }
        """ % TARGET_SECTIONS)

        print(f"Found {len(cards)} images in target sections.")

        seen = set()
        
        count = 0

        seen_hashes = set()

        for card in cards:
            raw_url = card["url"]
            alt = card["alt"]
            section = card["section"]

            # Convert relative → absolute
            img_url = urljoin(URL, raw_url)

            ext = os.path.splitext(img_url)[1]
            ext = ext.lower() if ext else ".png"

            # name = alt text or filename fallback
            if alt.strip():
                filename = clean_filename(alt) + ext
            else:
                filename = os.path.basename(img_url)

            if filename in seen:
                print(f"Skipping duplicate: {filename}")
                continue
            seen.add(filename)

            save_path = os.path.join(OUTPUT_DIR, filename)

            print(f"[{section}] → {filename}")

            # Fetch via browser to avoid blocks
            try:
                data_bytes = await page.evaluate("""async (url) => {
                    const response = await fetch(url);
                    const buffer = await response.arrayBuffer();
                    return Array.from(new Uint8Array(buffer));
                }""", img_url)
                data_bytes = bytes(data_bytes)


            # Check for duplicates by content
                h = hash_bytes(data_bytes)
                if h in seen_hashes:
                    print(f"Skipping duplicate IMAGE (same content): {filename}")
                    continue
                seen_hashes.add(h)

            # Write the file
                with open(save_path, "wb") as f:
                    f.write(data_bytes)

                count += 1

            except Exception as e:
                print(f"FAILED: {img_url}\nError: {e}")

        await browser.close()
        print(f"\nDONE — Downloaded {count} total cards into '{OUTPUT_DIR}'")


if __name__ == "__main__":
    asyncio.run(scrape())
