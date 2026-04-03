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

def save_settings(target_dir_path):
	"""パスをJSONファイルに保存する"""
	with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
		json.dump({"target_dir_path": target_dir_path}, f, indent=4, ensure_ascii=False)

def startup_sequence():
	target_path = None
	dialog = InitialSetupDialog()
	target_path = dialog.run()

	# パスが確定したら保存
	if target_path:
		save_settings(target_path)
	else:
		return None # キャンセル時

	# 3. 確定したパスで BMT 抽出
	extract_all_bmt(target_dir_path=target_path, output_dir_name="./table_data")
	return target_path

class InitialSetupDialog:
	def __init__(self):
		self.root = tk.Tk()
		self.root.title("初期設定 - BMS Table フォルダ選択")
		self.root.geometry("500x150")
		self.result_path = None
		# 1. ラベル
		tk.Label(self.root, text="BMS Table のパスを指定してください:").pack(anchor="w", padx=10, pady=(15, 0))

		# 2. Entry と Browse ボタンのフレーム
		self.frame_path = tk.Frame(self.root)
		self.frame_path.pack(fill="x", padx=10, pady=5)
		
		self.entry_path = tk.Entry(self.frame_path)
		self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 5))
		
		tk.Button(self.frame_path, text="Browse", command=self.browse_folder).pack(side="right")

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
					if target_dir_path: self.entry_path.insert(0, target_dir_path)
					return

			except Exception:
				return {}
		return {}

	def browse_folder(self):
		"""フォルダ選択ダイアログを開き、Entryに反映する"""
		folder = filedialog.askdirectory(title="table を選択")
		if folder:
			self.entry_path.delete(0, tk.END)
			self.entry_path.insert(0, folder)

	def confirm_and_close(self):
		"""入力されたパスを検証して保存し、終了する"""
		path = self.entry_path.get().strip()
		if os.path.isdir(path):
			self.result_path = path
			self.root.destroy()
		else:
			messagebox.showerror("エラー", "有効なディレクトリを選択してください。")

	def on_close(self):
		"""×ボタンで閉じられた場合"""
		self.result_path = None
		self.root.destroy()

	def run(self):
		self.root.mainloop()
		return self.result_path

if __name__ == "__main__":
	startup_sequence()