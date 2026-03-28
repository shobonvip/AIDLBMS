import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

async def fetch_and_download(url: str):
	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=True)
		context = await browser.new_context()
		page = await context.new_page()

		print(f"URLを開いています: {url}")
		
		await page.goto(url, wait_until="networkidle")
		html_content = await page.content()
		print("--- HTML Content (First 500 chars) ---")
		print(html_content[:500])
		print("---------------------------------------")

		try:
			print("ダウンロードを待機中... (ボタンを手動で押すか、AIに押させてください)")
			async with page.expect_download(timeout=60000) as download_info:
				pass
			download = await download_info.value
			
			# 保存先の作成
			save_path = Path("dl_file") / download.suggested_filename
			save_path.parent.mkdir(exist_ok=True)
			
			# ファイルを保存
			await download.save_as(save_path)
			print(f"ダウンロード完了: {save_path}")

		except Exception as e:
			print(f"ダウンロードが発生しませんでした、またはタイムアウトしました: {e}")

		await browser.close()

if __name__ == "__main__":
	target_url = "https://example.com"  # テストしたいURL
	asyncio.run(fetch_and_download(target_url))