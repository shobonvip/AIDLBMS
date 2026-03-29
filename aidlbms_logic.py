import asyncio
from playwright.async_api import async_playwright, Error, TimeoutError as PWTimeoutError
from pathlib import Path
from PIL import Image
import io
from dotenv import load_dotenv
import os
from google import genai

def setup_gemini():
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)

async def auto_download_inner(url, page, logger = None):
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	complete = False
	page_loaded = False
	download_task = asyncio.create_task(page.wait_for_event("download"))

	try:
		try:
			_log(f"{url} にアクセスします")		
			await page.goto(url, timeout=10000)
			_log(f"ページを読み込みました")
			page_loaded = True
			download = await asyncio.wait_for(download_task, timeout=2.0)
		except asyncio.TimeoutError:
			_log(f"自動DLがありませんでした。")
			await page.screenshot(path="screenshot.png")
			return False
		except PWTimeoutError:
			_log(f"ページ読み込みに失敗しました")
			return False
		except Error as e:
			if "Download is starting" in str(e):
				_log(f"ページを読み込みました（直リンク）")
				page_loaded = True
				download = await download_task
			else:
				raise e
	
		assert download != None
		_log(f"ダウンロードを開始します。")
		await download.save_as(f"dl_file/{download.suggested_filename}")
		_log(f"ダウンロードが完了しました。")
		complete = True
		return complete
	except Error as e:
		_log(f"自動DL 失敗! {e}")
		pass
	finally:
		pass


async def auto_download(url: str, logger = None) -> bool:
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	save_dir = Path("dl_file")
	save_dir.mkdir(exist_ok = True)

	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=True)
		context = await browser.new_context(viewport={"width":720, "height":1280})
		page = await context.new_page()

		try:
			return await auto_download_inner(url, page, logger)
		except Exception as e:
			_log(f"接続に失敗しました")
			print(f"接続失敗: {e}")
			return False
		finally:
			await browser.close()

if __name__ == "__main__":
	target_url = "https://bms.hexlataia.xyz/mirror/gnqg-upload/05466.zip"  # テストしたいURL
	asyncio.run(auto_download(target_url))