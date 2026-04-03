import os
import shutil
import zipfile
import py7zr
import rarfile
from pathlib import Path

def smart_unpacker(file_path, extract_dir, file_name, logger = None):
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
		if ext == ".zip":
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
		if not extract_bms(extract_dir, f"download_song/{file_name}", file_name, _log):
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

def extract_bms(extract_dir, final_dest_dir, file_name, _log):
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
	
	_log(f"【Case C】複数のBMSフォルダを検知（{len(bms_dirs)}個）。AIに判定を依頼します。（未実装）")
	return False