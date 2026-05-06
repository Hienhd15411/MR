"""Run the pipeline using the bundled RSS fixture so the markdown sink can be
previewed without external network access.

Useful when:
  - sandbox / CI cannot reach upstream sites
  - reviewing the Markdown output format

Real run (when network is available):
    python -m src.main --markdown output/raw_data.md
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from src.crawlers.news.vnexpress import VnExpressSoHoa
from src.storage.markdown_sink import write_markdown
from src.utils.logger import setup_logger


FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vnexpress_rss.xml"
OUTPUT = Path(__file__).resolve().parents[1] / "output" / "raw_data.md"


async def main() -> None:
    setup_logger()
    crawler = VnExpressSoHoa()
    crawler.window_days = 365 * 10  # disable window so all 3 fixture items pass

    fixture_xml = FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(self, client, url):
        return fixture_xml

    # Bypass network: feed the RSS fixture directly.
    VnExpressSoHoa.fetch = fake_fetch  # type: ignore[assignment]

    articles = await crawler.run(client=None)
    n = write_markdown(OUTPUT, articles)
    print(f"Wrote {n} articles to {OUTPUT.relative_to(Path.cwd())}")


if __name__ == "__main__":
    asyncio.run(main())
