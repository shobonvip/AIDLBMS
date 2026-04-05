import gzip
import shutil
from pathlib import Path

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox

"""
beatoraja の難易度表は ./table の中の bmt ファイルとして含まれている
bmt ファイルは実質的に gzip 形式であり、中にあるファイルは json 形式である
"""

def extract_all_bmt(
	target_dir_path: str,
	output_dir_name: str = "table_data"
):
	base_path = Path(target_dir_path)
	output_path = Path(output_dir_name)
	output_path.mkdir(parents=True, exist_ok=True)
	for bmt_file in base_path.glob("*.bmt"):
		output_file = output_path / bmt_file.with_suffix(".json").name
		print(f"解凍中: {bmt_file.name} -> {output_file.name}")
		try:
			# gzip として解凍
			with gzip.open(bmt_file, 'rb') as f_in:
				# 中にあるファイルを取り出す
				with open(output_file, 'wb') as f_out:
					shutil.copyfileobj(f_in, f_out)
		
		except Exception as e:
			print(f"エラー発生 ({bmt_file.name}): {e}")

SETTINGS_FILE = "settings.json"

def save_settings(target_dir_path, songdata_db_path):
	"""パスをJSONファイルに保存する"""
	with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
		json.dump({
			"target_dir_path": target_dir_path,
			"songdata_db_path": songdata_db_path
		}, f, indent=4, ensure_ascii=False)

def startup_sequence():
	dialog = InitialSetupDialog()
	target_dir_path, songdata_db_path = dialog.run()

	# パスが確定したら保存
	if target_dir_path:
		save_settings(target_dir_path, songdata_db_path)
	else:
		return None # キャンセル時

	# 3. 確定したパスで BMT 抽出
	extract_all_bmt(target_dir_path=target_dir_path, output_dir_name="./table_data")
	return target_dir_path, songdata_db_path

class InitialSetupDialog:
	def __init__(self):
		self.root = tk.Tk()
		self.root.title("初期設定 - BMS Table フォルダ選択")
		self.root.geometry("500x250")
		self.result_target_dir_path = None
		self.result_songdata_db_path = None

		tk.Label(self.root, text="table フォルダのパスを指定してください:").pack(anchor="w", padx=10, pady=(15, 0))
		self.frame_target_dir_path = tk.Frame(self.root)
		self.frame_target_dir_path.pack(fill="x", padx=10, pady=5)		
		self.entry_target_dir_path = tk.Entry(self.frame_target_dir_path)
		self.entry_target_dir_path.pack(side="left", fill="x", expand=True, padx=(0, 5))
		tk.Button(self.frame_target_dir_path, text="Browse", command=self.browse_folder).pack(side="right")

		tk.Label(self.root, text="songdata.db のパスを指定してください:").pack(anchor="w", padx=10, pady=(15, 0))
		self.frame_songdata_db_path = tk.Frame(self.root)
		self.frame_songdata_db_path.pack(fill="x", padx=10, pady=5)		
		self.entry_songdata_db_path = tk.Entry(self.frame_songdata_db_path)
		self.entry_songdata_db_path.pack(side="left", fill="x", expand=True, padx=(0, 5))
		tk.Button(self.frame_songdata_db_path, text="Browse", command=self.browse_db).pack(side="right")


		# 3. 決定ボタン
		tk.Button(self.root, text="OK / 起動", command=self.confirm_and_close, width=15, bg="#e1e1e1").pack(pady=10)

		# ウィンドウを閉じた時の処理
		self.root.protocol("WM_DELETE_WINDOW", self.on_close)
		self.load_settings()

	def load_settings(self):
		if os.path.exists(SETTINGS_FILE):
			try:
				with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
					settings = json.load(f)
					target_dir_path = settings.get("target_dir_path", "")
					songdata_db_path = settings.get("songdata_db_path", "")
					if target_dir_path: self.entry_target_dir_path.insert(0, target_dir_path)
					if songdata_db_path: self.entry_songdata_db_path.insert(0, songdata_db_path)
					return

			except Exception:
				return {}
		return {}

	def browse_folder(self):
		folder = filedialog.askdirectory(title="table を選択")
		if folder:
			self.entry_target_dir_path.delete(0, tk.END)
			self.entry_target_dir_path.insert(0, folder)
	
	def browse_db(self):
		filename = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
		if filename:
			self.entry_songdata_db_path.delete(0, tk.END)
			self.entry_songdata_db_path.insert(0, filename)

	def confirm_and_close(self):
		target_dir_path = self.entry_target_dir_path.get().strip()
		if os.path.isdir(target_dir_path):
			self.result_target_dir_path = target_dir_path
		else:
			messagebox.showerror("エラー", "table: 有効なディレクトリを選択してください。")
			return
		
		songdata_db_path = self.entry_songdata_db_path.get().strip()
		if os.path.isfile(songdata_db_path):
			self.result_songdata_db_path = songdata_db_path
		else:
			messagebox.showerror("エラー", "songdata.db: 有効なファイルを選択してください。")
			return

		self.root.destroy()
		

	def on_close(self):
		self.result_target_dir_path = None
		self.result_songdata_db_path = None
		self.root.destroy()

	def run(self):
		self.root.mainloop()
		return self.result_target_dir_path, self.result_songdata_db_path

if __name__ == "__main__":
	startup_sequence()