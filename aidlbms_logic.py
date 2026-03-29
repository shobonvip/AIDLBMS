import asyncio
from playwright.async_api import async_playwright, Error, TimeoutError as PWTimeoutError
from pathlib import Path
from PIL import Image
import io
from dotenv import load_dotenv
import os
from google import genai
from google.genai import types
import json
import random

XSIZE = 720
YSIZE = 1280

def setup_gemini():
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)

async def ask_ai_for_screenshot(title: str, file_type: str, screenshot_bytes, logger):
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)
		
	img = Image.open(io.BytesIO(screenshot_bytes))
	
	prompt = f"""
	This is a screenshot for BMS file ({file_type}) download page.
	The title of the song is {title}.
	Analyze the image and the find the main download button, or good to click for downloading the target file.
	Return the center coordinates (x,y) of the button within this image.
	Output the result as a raw JSON object with keys "x", "y".
	If there is no good way, output null JSON.
	Example output: {{"x": 326, "y": 125}}
	"""

	try:
		load_dotenv()
		client = setup_gemini()
		response = await client.aio.models.generate_content(
			model = "gemini-3.1-flash-lite-preview",
			contents = [prompt, img],
			config = types.GenerateContentConfig(
				response_mime_type = "application/json",
				temperature = 0.1
			)
		)

		result = json.loads(response.text)
		_log(f"AI解析完了: {result}")
		if not result or "x" not in result or "y" not in result:
			_log(f"ありませんでした！")
			return None
		return (
			int(result['x'] / 1000 * XSIZE),
			int(result['y'] / 1000 * YSIZE)
		)
	except Exception as e:
		_log(f"エラー: {e}")
		return None




async def auto_download_inner(title: str, url: str, file_type: str, page, logger = None):
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	complete = False
	page_loaded = False
	download_task = asyncio.create_task(page.wait_for_event("download"))

	try:
		
		# ページアクセス
		try:
			_log(f"{url} にアクセスします")		
			await page.goto(url, timeout=10000)
			_log(f"ページを読み込みました")
			page_loaded = True
			# ダウンロード待ち (2秒)
			download = await asyncio.wait_for(download_task, timeout=2.0)
		except asyncio.TimeoutError:
			# ページを読み込んだが、自動DLがない
			_log(f"自動DLがありませんでした。")
			screenshot_bytes = await page.screenshot(path=f"screenshot_{random.randrange(1000)}.png")
			result = await ask_ai_for_screenshot(
				title, file_type, screenshot_bytes, logger
			)
			if result == None:
				_log("NONE RESULT")
			else:
				_log(f"{result[0]} {result[1]}")
			return False
		except PWTimeoutError:
			# ページ読み込み失敗！
			_log(f"ページ読み込みに失敗しました")
			return False
		except Error as e:
			# 直リンクなので、甘えてダウンロードをする
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


async def auto_download(title: str, url: str, file_type: str, logger = None) -> bool:
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	save_dir = Path("dl_file")
	save_dir.mkdir(exist_ok = True)

	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=True)
		context = await browser.new_context(viewport={"width":XSIZE, "height":YSIZE})
		page = await context.new_page()

		try:
			return await auto_download_inner(title, url, file_type, page, logger)
		except Exception as e:
			_log(f"接続に失敗しました")
			print(f"接続失敗: {e}")
			return False
		finally:
			await browser.close()

if __name__ == "__main__":
	title = "CHERRY DOLL"

	target_url = "https://pupuly.nekokan.dyndns.info/bms/v/60"  # テストしたいURL
	asyncio.run(auto_download(title, target_url, "本体"))