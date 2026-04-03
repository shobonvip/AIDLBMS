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
from bs4 import BeautifulSoup
from bs4 import Comment
import re
import os

XSIZE = 1536
YSIZE = 2304
AI_MAX_TRY = 9

def setup_gemini():
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)

async def download_file(download, _log):
	_log(f"ダウンロードを開始します。")
	_log(f"{download.suggested_filename}")
	file_path = f"dl_tmp_file/{download.suggested_filename}"
	await download.save_as(file_path)
	_log(f"ダウンロードが完了しました。")
	return file_path


def clean_html_for_ai(raw_html):
	soup = BeautifulSoup(raw_html, 'lxml')
	irrelevant_tags = [
		'script', 'style', 'svg', 'canvas', 'iframe', 'noscript', 'head', 'meta', 'link',
		'header', 'footer', 'nav', 'aside', 'picture', 'figure', 'video', 'audio',
		'amp-ad', 'ins'
	]
	for tag in soup(irrelevant_tags):
		tag.decompose()
	for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
		comment.extract()
	
	important_tags = soup.find_all(['a', 'button', 'input'])
	minimal_soup = BeautifulSoup("<html><body></body></html>", 'lxml')
	body = minimal_soup.body

	for tag in important_tags:
		href = tag.get('href', '')
		if "event.cgi" in href: continue

		parent_clone = tag.find_parent('div')
		if parent_clone:
			allowed_attrs = ['id', 'class']
			parent_clone.attrs = {n: v for n, v in parent_clone.attrs.items() if n in allowed_attrs}
			body.append(parent_clone)
		else:
			body.append(tag)
	
	cleaned_html = re.sub(r'\s+', ' ', minimal_soup.decode()).strip()

	matches = []
	
	vocab = ["download", "ダウンロード"]
	for keyword in vocab:
		matches += list(
			re.finditer(re.escape(keyword), cleaned_html, re.IGNORECASE)
		)

	for match in matches:
		start_idx = max(0, match.start() - 200)
		end_idx = min(len(cleaned_html), match.end() + 800)
		return cleaned_html[start_idx:end_idx]

	return None


async def ai_action(
	title: str,
	file_type: str,
	page,
	song_md5,
	_log
):
	
	now_page = [page]
	scrolled_time = 0
	url_history = {page.url}
	LR2IR_used = False

	try:
		load_dotenv()
		client = setup_gemini()
	except Exception as e:
		_log(f"エラー: {e}")
		return None

	def prompt_html(url):
		return f"""
		This is a HTML snippet for 発狂BMS file ({file_type}) download page
		The title of the song is {title}
		URL for this webpage is "{url}"
		identify the SINGLE most likely URL for the main file download

		Rules
		- Prioritize direct links (.zip, .rar, .lzh, .7z).
		- If no direct link, pick external uploaders (uploader.jp, drive.google.com, dropbox.com, mega.nz, etc.).
		- Ignore navigation links, ads, or social media.
		- Ignore same url as shown.
		- Output as absolute path. 
		- If URL is not ended, return null.

		If there is no good URL (or only same url as shown), output null JSON.
		Output JSON: {{"target_url": "string"}}
		"""

	# 初回のプロンプト
	prompt_first = f"""
	This is a screenshot for 発狂BMS file ({file_type}) download page.
	The title of the song is {title}.

	Analyze the image and the find good to click for downloading the target file.
	Return the center coordinates (x,y) where to click within this image.
	If there is no DL url but have Difficulty Table, prefer Table.
	Prefer {file_type} or "通常版" button.
	
	Output the result as a raw JSON object with keys "x", "y".
	If there is no good way, output null JSON.
	If you want to scroll the browser, output {{"scroll": 1}}.
	Example output: {{"x": 326, "y": 125}}
	"""

	# 二回目以降のプロンプト
	prompt_second = f"""
	This is a screenshot for 発狂BMS file ({file_type}) download page.
	The title of the song is {title}.

	The first image is previous one, and the second image is current one.
	You have to navigate the browser on the second image to download target file.

	Analyze the images and the find good to click for downloading the target file.
	Return the center coordinates (x,y) where to click within this image.
	If there is no DL url but have Difficulty Table, prefer Table.
	Prefer "{file_type}" or "通常版" button.

	Output the result as a raw JSON object with keys "x", "y".
	If there is no good way, output null JSON.
	If you want to scroll the browser, output {{"scroll": 1}}.
	Example output: {{"x": 326, "y": 125}}
	"""
	
	img_old = None
	for try_num in range(1, AI_MAX_TRY + 1):
		_log(f"{try_num}/{AI_MAX_TRY} 回目のAI試行です")

		try:
			url_history.add(now_page[-1].url)
			goto_query = False
			click_query = False
			complete_query = False

			if not complete_query:
				#スクリーンショットを取り、AIに投げる
				#screenshot_bytes = await now_page[-1].screenshot(path=f"screenshot_{random.randrange(1000)}.png")
				screenshot_bytes = await now_page[-1].screenshot()
				img = Image.open(io.BytesIO(screenshot_bytes))

				try:		
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
				except Exception as e:
					print(f"エラー: {e}")
					return None

				img_old = img
				result = json.loads(response.text)
				_log(f"AI解析完了: {result}")
				
				if not result:
					pass
				elif "scroll" in result:
					# スクロールをする
					await now_page[-1].evaluate(f"window.scrollBy(0, {YSIZE})")
					await asyncio.sleep(2.0)
					scrolled_time += 1
					complete_query = True
					continue
				elif not result or "x" not in result or "y" not in result or not result['x'] or not result['y']:
					pass
				else:
					targ_x = int(result['x'] / 1000 * XSIZE)
					targ_y = int(result['y'] / 1000 * YSIZE)
					click_query = True
					complete_query = True
			
			if not complete_query:
				# HTML を解析
				html_content = await now_page[-1].content()
				html_likely_dl_url = clean_html_for_ai(html_content)
				
				if html_likely_dl_url != None:
					print(html_likely_dl_url)
					try:
						response = await client.aio.models.generate_content(
							model = "gemini-3.1-flash-lite-preview",
							contents = [prompt_html(now_page[-1].url), html_likely_dl_url],
							config = types.GenerateContentConfig(
								response_mime_type = "application/json",
								temperature = 0.0
							)
						)
					except Exception as e:
						print(f"エラー: {e}")
						return None


					result = json.loads(response.text)
					_log(f"テキストAI解析完了: {result}")

					if result and "target_url" in result and result.get("target_url") != None:	
						goto_target_url = result.get("target_url")
						if goto_target_url not in url_history:
							_log(f"AIが次のURLを特定: {goto_target_url}")
							goto_query = True
							complete_query = True
							url_history.add(goto_target_url)
						else:
							_log(f"テキストデータからは次の遷移先が見つけられませんでした")
					else:
						_log(f"テキストデータからはDLリンクが見つけられませんでした")

			
			dl_task = asyncio.create_task(now_page[-1].wait_for_event("download"))
			nav_task = asyncio.create_task(now_page[-1].wait_for_load_state("load"))
			popup_task = asyncio.create_task(now_page[-1].context.wait_for_event("page"))
		
			# 何もできない（主にリンク切れ）の処理
			if not complete_query:
				if not LR2IR_used:
					goto_target_url = f"http://www.dream-pro.info/~lavalse/LR2IR/search.cgi?mode=ranking&bmsmd5={song_md5}"
					goto_query = True
					complete_query = True
					_log("LR2IR を検索します。")
					LR2IR_used = True
				else:
					_log("だめだったので諦めます。")
					return None

			# クリックの処理
			if click_query:
				_log(f"{targ_x}, {targ_y} をクリックします")
				await now_page[-1].mouse.click(targ_x, targ_y)
			elif goto_query:
				try:
					await now_page[-1].goto(goto_target_url, timeout=12000)
				except PWTimeoutError:
					# ページ読み込み失敗！
					_log(f"ページ読み込みに失敗しました")
					return None
				except Error as e:
					# 直リンクなので、甘えてダウンロードをする
					if "Download is starting" in str(e):
						_log(f"ページを読み込みました（直リンク）")
					else:
						raise e


			# まずは2秒監視
			await asyncio.sleep(2.0)
	
			if not (dl_task.done() or nav_task.done() or popup_task.done()):
				_log("まだ何も起きていないので、追加で監視を続けます...")
				done, pending = await asyncio.wait(
					[nav_task, dl_task, popup_task],
					return_when=asyncio.FIRST_COMPLETED,
					timeout=8.0
				)

			# タスクの中断
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
				ret_file = await download_file(download, _log)
				return ret_file

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
			return None

		except Exception as e:
			_log(f"エラー: {e}")
			return None

async def auto_download_inner(title: str, url: str, file_type: str, page, song_md5: str, _log):
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
				title, file_type, page, song_md5, _log
			)

			if result:
				_log("AI自動DLに成功しました")
			else:
				_log("AI自動DLに失敗しました")

			return result

		except PWTimeoutError:
			# ページ読み込み失敗！
			_log(f"ページ読み込みに失敗しました")
			return None
		except Error as e:
			# 直リンクなので、甘えてダウンロードをする
			if "Download is starting" in str(e):
				_log(f"ページを読み込みました（直リンク）")
				page_loaded = True
				download = await download_task
			else:
				raise e
	
		assert download != None

		ret_file = await download_file(download, _log)
		return ret_file
	except Error as e:
		_log(f"自動DL 失敗! {e}")
		return None
	finally:
		pass


async def auto_download(title: str, url: str, file_type: str, song_md5: str, logger = None) -> bool:
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	save_dir = Path("dl_tmp_file")
	save_dir.mkdir(exist_ok = True)

	async with async_playwright() as p:
		browser = await p.chromium.launch(headless=True)
		context = await browser.new_context(viewport={"width":XSIZE, "height":YSIZE})
		page = await context.new_page()

		try:
			return await auto_download_inner(
				title, url, file_type, page, song_md5, _log
				)
		except Exception as e:
			_log(f"接続に失敗しました")
			print(f"接続失敗: {e}")
			return None
		finally:
			await browser.close()

if __name__ == "__main__":
	title = "薄雲"

	#target_url = "https://pupuly.nekokan.dyndns.info/bms/v/60"  # テストしたいURL
	target_url = "https://manbow.nothing.sh/event/event.cgi?action=More_def&num=303&event=123"
	asyncio.run(auto_download(title, target_url, "本体"))