import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import table_find_missing_songs
import logging
from tkinter import scrolledtext
from datetime import datetime


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
		self.title("AI # BMS # DL")
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

		# 2. フォーマットの設定 (時間 - レベル - メッセージ)
		formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S')

		# 3. ファイルへの保存設定 (log_20260329.txt のような名前にする)
		log_filename = datetime.now().strftime("log_%Y%m%d.txt")
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
		
		for iid in selected_iids:
			idx = self.song_tree.index(iid)
			song_data = self.current_missing_songs[idx]
			self.logger.info(f"{song_data['title']} が選択されました。DLを開始します。")
			if song_data['url'].startswith("http"):
				self.logger.info(f"本体URL {song_data['url']} にアクセスします。")
			else:
				self.logger.info(f"本体URLが見つかりませんでした。")
			if song_data['appendurl'].startswith("http"):
				self.logger.info(f"差分URL {song_data['appendurl']} にアクセスします。")
			else:
				self.logger.info(f"差分URLが見つかりませんでした。")

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
					song.get("appendurl", "-")
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
				self.logger.info(f"難易度表 {table_name} の未所持譜面は {len(missing_songs)} 個ありました。")
				self.update_song_list(missing_songs)
				#for songs in missing_songs:
				#	print(songs["title"], songs["artist"], songs["url"], songs["appendurl"])
			else:
				#print(f"難易度表全体を選択: {item_text} ({self.item_metadata[target_item]['path']})")
				pass

if __name__ == "__main__":
	app = TableSelector("./table_data", "./songdata.db")
	app.mainloop()