import os
import shutil
import zipfile
import py7zr
import rarfile
from pathlib import Path
import hello_gemini
import json
from google.genai import types

async def smart_unpacker(file_path, extract_dir, file_name, title, logger = None):
	def _log(m):
		if logger:
			logger.info(m)
		else:
			print(m)

	if not os.path.exists(extract_dir):
		os.makedirs(extract_dir)

	# 拡張子を抜き出す
	ext = os.path.splitext(file_path)[1].lower()

	try:
		# extract_dir に解凍 (もしくはコピー)
		if ext.startswith(".bm"):
			dest_file_path = os.path.join(extract_dir, os.path.basename(file_path))
			shutil.copy2(file_path, dest_file_path)
		elif ext == ".zip":
			with zipfile.ZipFile(file_path, 'r') as f:
				f.extractall(extract_dir)
		elif ext == ".7z":
			with py7zr.SevenZipFile(file_path, mode = 'r') as f:
				f.extractall(extract_dir)
		elif ext == ".rar":
			with rarfile.RarFile(file_path) as f:
				f.extractall(extract_dir)
		else:
			shutil.unpack_archive(file_path, extract_dir)

		_log(f"解凍成功: {os.path.basename(file_path)}")
		_log(f"フォルダに抜き出します。")
		result = await extract_bms(extract_dir, f"download_song/{file_name}", file_name, title, _log)
		if not result:
			_log(f"フォルダ抜き出しに失敗しました。")
			return False
		else:
			_log(f"フォルダ抜き出しが完了しました。")

		return True
	except Exception as e:
		_log(f"解凍失敗 ({ext}): {e}")
		return False
	finally:
		try:
			if os.path.exists(file_path):
				os.remove(file_path)
			if os.path.exists(extract_dir):
				shutil.rmtree(extract_dir)
		except Exception as e:
			print(f"ファイル削除失敗: {e}")
			return False

def move_folder_contents(src_dir, dst_dir):
	for item in src_dir.iterdir():
		dest_item = dst_dir / item.name
		# 既に同名のファイルがある場合は上書き（またはスキップ）
		if dest_item.exists():
			if dest_item.is_dir(): shutil.rmtree(dest_item)
			else: dest_item.unlink()
		shutil.move(str(item), str(dst_dir))

async def extract_bms(extract_dir, final_dest_dir, file_name, title, _log):
	temp_path = Path(extract_dir)
	dest_path = Path(final_dest_dir)
	dest_path.mkdir(parents=True, exist_ok=True)

	direct_bms_files = list(temp_path.glob("*.bm*"))
	if direct_bms_files:
		_log("CASE A: 直下にBMSファイル検知。内容をすべて移動します")
		move_folder_contents(temp_path, dest_path)
		return True
	
	bms_dirs = set(f.parent for f in temp_path.rglob("*.bm*"))
	bms_dirs = sorted(list(bms_dirs))
	if not bms_dirs:
		_log("BMS ファイルがありませんでした。")
		return False
	
	if len(bms_dirs) == 1:
		target_dir = bms_dirs[0]
		_log("CASE B: BMSフォルダをちょうど1つ検知。内容をすべて移動します")
		move_folder_contents(target_dir, dest_path)
		return True
	
	_log(f"CASE C: 複数のBMSフォルダを検知（{len(bms_dirs)}個）。AIに判定を依頼します。")

	folder_names = [d.name for d in bms_dirs]
	client = hello_gemini.setup_gemini()
	
	prompt = f"""
    Candidate Folders: {folder_names}

    From the candidate folders above, identify the most likely folder that contains the matching data.
    Title: {title}
    FileName: {file_name}

	If there is not suitable one, return null JSON.
    Output JSON format: {{"best_folder": "folder_name_string"}}
    """

	try:
		response = await client.aio.models.generate_content(
			model = "gemini-3.1-flash-lite-preview",
			contents = [prompt],
			config = types.GenerateContentConfig(
				response_mime_type = "application/json",
				temperature = 0.1
			)
		)

		result = json.loads(response.text)
		if not result or (not result["best_folder"]):
			_log("AIが適切なファイルを見つけられませんでした。")
			return False

		target_dir = next((d for d in bms_dirs if d.name == result["best_folder"]), bms_dirs[0])
		_log(f"AIがフォルダを選択しました: {target_dir.name}")
		move_folder_contents(target_dir, dest_path)

		return True
	except Exception as e:
		print(f"エラー: {e}")
		return False


	return False

if __name__ == "__main__":
	import asyncio
	title = "20年以上のソナタ"
	in_file = "./dl_tmp_file/main_file/"
	out_file = "./dl_tmp_file/go_file/"
	file_name = "20年以上のソナタ [wav]"

	asyncio.run(extract_bms(in_file, out_file, file_name, title,
		lambda x:print(x)
	))
