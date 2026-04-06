VERSION = "V 1.2"

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import table_find_missing_songs
import platform
import logging
from tkinter import scrolledtext
from datetime import datetime
import aidlbms_logic
import threading
import asyncio
import unpack_handler
import table_data_expander
import os
import rarfile
import subprocess
import sys


"""loggingの出力をTkinterのテキストエリアに流し込むハンドラ"""
class TkinterHandler(logging.Handler):
	def __init__(self, text_widget):
		super().__init__()
		self.text_widget = text_widget

	def emit(self, record):
		msg = self.format(record)
		self.text_widget.after(0, self._append_text, msg)

	def _append_text(self, msg):
		self.text_widget.configure(state='normal') # 書き込み許可
		self.text_widget.insert(tk.END, msg + '\n')
		self.text_widget.see(tk.END) # 最下部までスクロール
		self.text_widget.configure(state='disabled') # 読み取り専用に戻す

class TableSelector(tk.Tk):
	def __init__(
		self,
		data_dir: str,
		songdata_db_path: str
	):
		super().__init__()
		self.title(f"AI # BMS # DL {VERSION}")
		self.geometry("1000x800")
		self.table_data = self.load_tables(data_dir)
		self.md5_set = table_find_missing_songs.get_owned_md5_set(songdata_db_path)
		self.item_metadata = {}
		self.current_missing_songs = []
		self.setup_ui()
		self.setup_logging()

	# 難易度表を読み込む
	def load_tables(self,
		directory: str
	):
		tables = {}
		for json_file in Path(directory).glob("*.json"):
			try:
				with open(json_file, 'r', encoding='utf-8') as f:
					data = json.load(f)
					table_name = data.get("name", json_file.stem)
					folders = [(f.get("name"), num) for num, f in enumerate(data.get("folder", []))]
					tables[table_name] = {
						"path": json_file,
						"folder": folders
					}
			except Exception as e:
				print(f"Error loading {json_file}: {e}")
		return tables

	# GUI セットアップ
	def setup_ui(self):

		main_frame = ttk.Frame(self)
		main_frame.pack(fill = "both", expand = True, padx = 10, pady = 5)

		# 左側：難易度表選択画面
		left_frame = ttk.Frame(main_frame)
		left_frame.pack(side = "left", fill = "both", expand = True)

		self.tree = ttk.Treeview(left_frame)
		self.tree.heading("#0", text="難易度表を選択", anchor="w")
		self.tree.pack(fill="both", expand=True, padx=10, pady=10)

		for table_name, data in self.table_data.items():
			parent = self.tree.insert(
				"",
				"end",
				text=table_name,
				open=False
			)
			self.item_metadata[parent] = {
				"path": data["path"]
			}
			for folder_name, index in data["folder"]:
				child = self.tree.insert(parent, "end", text=folder_name)
				self.item_metadata[child] = {
					"path": data["path"],
					"index": index
				}
			
		btn = ttk.Button(
			self,
			text="選択したフォルダを決定",
			command=self.on_table_select
		)
		btn.pack(pady=10)

		# 右側：譜面選択
		right_frame = ttk.LabelFrame(main_frame, text="未所持譜面")
		right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

		self.song_tree = ttk.Treeview(right_frame, columns=("title", "url", "appendurl"), show="headings")
		self.song_tree.heading("title", text="タイトル")
		self.song_tree.heading("url", text="URL")
		self.song_tree.heading("appendurl", text="差分URL")
		self.song_tree.column("title", width=150)
		self.song_tree.column("url", width=100)
		self.song_tree.column("appendurl", width=100)
		
		# スクロールバー
		scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.song_tree.yview)
		self.song_tree.configure(yscroll=scrollbar.set)
		
		self.song_tree.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")

		action_frame = ttk.Frame(right_frame)
		action_frame.pack(fill="x", side="bottom", pady=5)

		ttk.Button(
			action_frame,
			text="選択曲をDL",
			command=self.download_selected
		).pack(side="right", padx=5)
		#ttk.Button(action_frame, text="一括自動DL", command=self.download_all).pack(side="right", padx=5)


		# 下側：ログ
		log_frame = ttk.LabelFrame(self, text="実行ログ")
		log_frame.pack(fill="x", side="bottom", padx=10, pady=10)

		# scrolledtext はスクロールバー付きのテキストエリア
		self.log_widget = scrolledtext.ScrolledText(log_frame, height=10, state='disabled')
		self.log_widget.pack(fill="both", expand=True)

	# ログを起動
	def setup_logging(self):
		# 1. ロガーの作成
		self.logger = logging.getLogger("BMS_Loader")
		self.logger.setLevel(logging.INFO)
		if not os.path.exists("log"):
			os.makedirs("log")
		# 2. フォーマットの設定 (時間 - レベル - メッセージ)
		formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')

		# 3. ファイルへの保存設定 (log_20260329.txt のような名前にする)
		log_filename = datetime.now().strftime("log/log_%Y%m%d.txt")
		file_handler = logging.FileHandler(log_filename, encoding='utf-8')
		file_handler.setFormatter(formatter)

		# 4. GUIへの出力設定 (先ほど作ったハンドラを使用)
		gui_handler = TkinterHandler(self.log_widget)
		gui_handler.setFormatter(formatter)

		# 5. ロガーにハンドラを登録
		self.logger.addHandler(file_handler)
		self.logger.addHandler(gui_handler)

		self.logger.info("プログラムが起動しました。")

	# 譜面選択したとき
	def download_selected(self):
		selected_iids = self.song_tree.selection()
		if not selected_iids:
			self.logger.info("曲が選択されていません。")
			return

		selected_song_data = []
		for iid in selected_iids:
			idx = self.song_tree.index(iid)
			song_data = self.current_missing_songs[idx]
			selected_song_data.append(song_data)

		
		def autodl_sequencer():
			for song_data in selected_song_data:
				file_path_complete = False
				appendfile_path_complete = False

				# 本体DL
				self.logger.info(f"{song_data['title']} のDLを開始します。")
				if song_data['url'].startswith("http"):
					self.logger.info(f"本体URL {song_data['url']} にアクセスします。")
					file_path = asyncio.run(aidlbms_logic.auto_download(song_data['title'], song_data['url'], "本体", song_data['md5'], self.logger))
					if not file_path:
						self.logger.info(f"【重要】本体の DL に失敗しました。URL: {song_data['url']}")
						continue
					else:
						
						file_name = os.path.splitext(
								os.path.basename(file_path)
							)[0]
						file_path_complete = True
				else:
					self.logger.info(f"本体URLが見つかりませんでした。")
					file_path = None
					file_path_complete = True

				# 差分DL.
				if song_data['appendurl'].startswith("http"):
					self.logger.info(f"差分URL {song_data['appendurl']} にアクセスします。")
					appendfile_path = asyncio.run(aidlbms_logic.auto_download(song_data['title'], song_data['appendurl'], "差分", song_data['md5'], self.logger))
					if not appendfile_path:
						self.logger.info(f"【重要】差分の DL に失敗しました。URL: {song_data['appendurl']}")
						continue
					else:
						appendfile_path_complete = True
				else:
					self.logger.info(f"差分URLが見つかりませんでした。")
					appendfile_path = None
					appendfile_path_complete = True
				self.logger.info(f"{song_data['title']} のDLが完了しました")


				if file_path_complete and appendfile_path_complete:
					self.logger.info(f"両者ダウンロードに成功したので解凍します")
					if file_path:
						unpack_main_success = asyncio.run(unpack_handler.smart_unpacker(
							file_path,
							"dl_tmp_file/main_file",
							file_name, song_data['title'],
							self.logger
						))
						if not unpack_main_success:
							self.logger.info("本体の導入に失敗しました")
							continue
					if file_path and appendfile_path:
						unpack_append_success = asyncio.run(unpack_handler.smart_unpacker(
							appendfile_path,
							"dl_tmp_file/append_file",
							file_name,
							song_data['title'],
							self.logger
						))
						if not unpack_append_success:
							self.logger.info("差分の導入に失敗しました")
							continue
				
				self.logger.info(f"{song_data['title']} の導入に成功しました")
				

		thread = threading.Thread(
			target = autodl_sequencer,
			daemon = True
		)
		thread.start()
			
	# 難易度表の未所持譜面一覧を更新する
	def update_song_list(self, missing_songs):
		self.current_missing_songs = missing_songs

		for item in self.song_tree.get_children():
			self.song_tree.delete(item)
		
		for song in self.current_missing_songs:
			self.song_tree.insert(
				"",
				"end",
				values = (
					song.get("title", "-"),
					song.get("url", "-"),
					song.get("appendurl", "-"),
					song.get("md5", "-")
				)
			)

	# 難易度表を選んだ時の処理
	# 未所持譜面を抜き出して表示させる
	def on_table_select(self):
		selected_item = self.tree.selection()
		if selected_item:
			target_item = selected_item[0]
			item_text = self.tree.item(target_item, "text")
			parent_id = self.tree.parent(target_item)
			if parent_id:
				table_name = self.tree.item(parent_id, "text")
				json_path = self.item_metadata[target_item]['path']
				table_index = self.item_metadata[target_item]['index']
				self.logger.info(f"難易度表 {table_name} を選択しました。")
				#print(f"選択確定: {table_name} ({json_path}) -> {item_text} ({table_index})")
				missing_songs = table_find_missing_songs.find_missing_songs(
					json_path, table_index, self.md5_set
				)
				self.logger.info(f"難易度表 {table_name} / {item_text} の未所持譜面は {len(missing_songs)} 個ありました。")
				self.update_song_list(missing_songs)
				#for songs in missing_songs:
				#	print(songs["title"], songs["artist"], songs["url"], songs["appendurl"])
			else:
				#print(f"難易度表全体を選択: {item_text} ({self.item_metadata[target_item]['path']})")
				pass


def ensure_playwright():
	try:
		# chromium があるか適当なコマンドでチェック
		subprocess.run(["playwright", "install", "chromium"], check=True)
		return True
	except Exception:
		print("Playwright のセットアップに失敗しました。")
	return False

if __name__ == "__main__":

	current_os = platform.system()
	print(current_os)
	if current_os == "Windows":
		rarfile.UNRAR_TOOL = "./Unrar/unrar.exe"

	#if not ensure_playwright():
	#	input()
	#	exit()

	table_dir_path, songdata_db_path = table_data_expander.startup_sequence()
	
	app = TableSelector("./table_data", songdata_db_path)
	app.mainloop()