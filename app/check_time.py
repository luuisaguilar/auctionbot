import asyncio, json
from datetime import datetime, timezone
from playwright.async_api import async_playwright

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(timezone_id='America/Phoenix')
        page = await context.new_page()

        async def on_resp(r):
            if 'getitems' in r.url:
                try:
                    data = json.loads(await r.body())
                    items = data.get('data', {}).get('items', [])
                    if items:
                        item = items[0]
                        end_time  = item.get('end_time')
                        display   = item.get('display_end_time')
                        now_utc   = datetime.now(timezone.utc).timestamp()
                        now_local = datetime.now().timestamp()
                        print(f"end_time raw : {end_time}")
                        print(f"display_end  : {display}")
                        print(f"now UTC ts   : {now_utc:.0f}")
                        print(f"now local ts : {now_local:.0f}")
                        print(f"diff UTC     : {float(end_time) - now_utc:.0f} seg")
                        print(f"diff local   : {float(end_time) - now_local:.0f} seg")
                except Exception as e:
                    print(f"Error: {e}")

        page.on('response', on_resp)
        await page.goto(
            'https://online.auctionnation.com//auction/81826/bidgallery/',
            wait_until='domcontentloaded'
        )
        await page.wait_for_timeout(8000)
        await browser.close()

asyncio.run(check())
