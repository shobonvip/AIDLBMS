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
AI_MAX_TRY = 7

def setup_gemini():
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)

async def download_file(download, _log):
	_log(f"ダウンロードを開始します。")
	await download.save_as(f"dl_file/{download.suggested_filename}")
	_log(f"ダウンロードが完了しました。")


async def ai_action(
	title: str,
	file_type: str,
	page,
	logger
):
	
	now_page = [page]
	scrolled_time = 0

	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)
	
	try:
		load_dotenv()
		client = setup_gemini()
	except Exception as e:
		_log(f"エラー: {e}")
		return False

	# 初回のプロンプト
	prompt_first = f"""
	This is a screenshot for BMS file ({file_type}) download page.
	The title of the song is {title}.

	Analyze the image and the find good to click for downloading the target file.
	Return the center coordinates (x,y) where to click within this image.
	
	Output the result as a raw JSON object with keys "x", "y".
	If there is no good way, output null JSON.
	If you want to scroll the browser, output {{"scroll": 1}}.
	Example output: {{"x": 326, "y": 125}}
	"""

	# 二回目以降のプロンプト
	prompt_second = f"""
	This is a screenshot for BMS file ({file_type}) download page.
	The title of the song is {title}.

	The first image is previous one, and the second image is current one.
	You have to navigate the browser on the second image to download target file.

	Analyze the images and the find good to click for downloading the target file.
	Return the center coordinates (x,y) where to click within this image.
	
	Output the result as a raw JSON object with keys "x", "y".
	If there is no good way, output null JSON.
	If you want to scroll the browser, output {{"scroll": 1}}.
	Example output: {{"x": 326, "y": 125}}
	"""
	img_old = None
	for try_num in range(1, AI_MAX_TRY + 1):
		_log(f"{try_num}/{AI_MAX_TRY} 回目のAI試行です")
		try:
			#screenshot_bytes = await now_page[-1].screenshot(path=f"screenshot_{random.randrange(1000)}.png")
			screenshot_bytes = await now_page[-1].screenshot()
			img = Image.open(io.BytesIO(screenshot_bytes))
		
			if img_old == None:
				response = await client.aio.models.generate_content(
					model = "gemini-3.1-flash-lite-preview",
					contents = [prompt_first, img],
					config = types.GenerateContentConfig(
						response_mime_type = "application/json",
						temperature = 0.1
					)
				)
			else:
				response = await client.aio.models.generate_content(
					model = "gemini-3.1-flash-lite-preview",
					contents = [prompt_second, img_old, img],
					config = types.GenerateContentConfig(
						response_mime_type = "application/json",
						temperature = 0.1
					)
				)
			
			img_old = img
			result = json.loads(response.text)
			_log(f"AI解析完了: {result}")

			if "scroll" in result:
				# スクロールをする
				await now_page[-1].evaluate(f"window.scrollBy(0, {YSIZE})")
				await asyncio.sleep(2.0)
				scrolled_time += 1
				continue
			elif not result or "x" not in result or "y" not in result:
				# だめなので False
				return False
			
			# クリック
			targ_x = int(result['x'] / 1000 * XSIZE)
			targ_y = int(result['y'] / 1000 * YSIZE)
			_log(f"{targ_x}, {targ_y} をクリックします")
			
			dl_task = asyncio.create_task(now_page[-1].wait_for_event("download"))
			nav_task = asyncio.create_task(now_page[-1].wait_for_load_state("load"))
			popup_task = asyncio.create_task(now_page[-1].context.wait_for_event("page"))
		
			await now_page[-1].mouse.click(targ_x, targ_y)

			# まずは2秒監視
			await asyncio.sleep(2.0)
	
			if not (dl_task.done() or nav_task.done() or popup_task.done()):
				_log("まだ何も起きていないので、追加で監視を続けます...")
				done, pending = await asyncio.wait(
					[nav_task, dl_task, popup_task],
					return_when=asyncio.FIRST_COMPLETED,
					timeout=8.0
				)

			for task in [dl_task, nav_task, popup_task]:
				if not task.done():
					task.cancel()
					try:
						await task
					except:
						pass

			# ダウンロード
			if dl_task.done() and not dl_task.cancelled():
				download = await dl_task
				await download_file(download, _log)
				return True

			# 新しいタブが開いたとき
			if popup_task.done() and not popup_task.cancelled():
				new_page = await popup_task
				await new_page.wait_for_load_state("load")
				_log(f"新タブが開きました: {new_page.url}")
				now_page.append(new_page)
				await asyncio.sleep(0.5)
				continue

			# 今のページが遷移した（基本ここにくる）
			if nav_task.done():
				_log(f"ページが遷移しました: {now_page[-1].url}")
				continue

			_log(f"遷移を試みましたが、何も起きませんでした")
			return False

		except Exception as e:
			_log(f"エラー: {e}")
			return False




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
			_log(f"自動DLがありませんでした。AI自動DLを試みます")

			result = await ai_action(
				title, file_type, page, logger
			)

			if result:
				_log("AI自動DLに成功しました")
			else:
				_log("AI自動DLに失敗しました")

			return result

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

		await download_file(download, _log)
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
	title = "薄雲"

	#target_url = "https://pupuly.nekokan.dyndns.info/bms/v/60"  # テストしたいURL
	target_url = "https://manbow.nothing.sh/event/event.cgi?action=More_def&num=303&event=123"
	asyncio.run(auto_download(title, target_url, "本体"))