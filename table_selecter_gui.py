import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import table_find_missing_songs

"""
難易度表を指定する GUI
"""

class TableSelector(tk.Tk):
	def __init__(self, data_dir, songdata_db_path):
		super().__init__()
		self.title("BMS難易度表セレクター")
		self.geometry("500x400")
		self.table_data = self.load_tables(data_dir)
		self.md5_set = table_find_missing_songs.get_owned_md5_set(songdata_db_path)
		self.item_metadata = {}
		self.setup_ui()

	def load_tables(self, directory):
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

	def setup_ui(self):
		self.tree = ttk.Treeview(self)
		self.tree.heading("#0", text="難易度表を選択", anchor="w")
		self.tree.pack(fill="both", expand=True, padx=10, pady=10)

		for table_name, data in self.table_data.items():
			parent = self.tree.insert("", "end", text=table_name, open=False)
			self.item_metadata[parent] = {
				"path": data["path"]
			}
			for folder_name, index in data["folder"]:
				child = self.tree.insert(parent, "end", text=folder_name)
				self.item_metadata[child] = {
					"path": data["path"],
					"index": index
				}
			
		btn = ttk.Button(self, text="選択したフォルダを決定", command=self.on_select)
		btn.pack(pady=10)

	def on_select(self):
		selected_item = self.tree.selection()
		if selected_item:
			target_item = selected_item[0]
			item_text = self.tree.item(target_item, "text")
			parent_id = self.tree.parent(target_item)
			if parent_id:
				table_name = self.tree.item(parent_id, "text")
				json_path = self.item_metadata[target_item]['path']
				table_index = self.item_metadata[target_item]['index']
				print(f"選択確定: {table_name} ({json_path}) -> {item_text} ({table_index})")
				missing_songs = table_find_missing_songs.find_missing_songs(json_path, table_index, self.md5_set)
				for songs in missing_songs:
					print(songs["title"], songs["artist"], songs["url"], songs["appendurl"])
			else:
				print(f"難易度表全体を選択: {item_text} ({self.item_metadata[target_item]['path']})")

if __name__ == "__main__":
	app = TableSelector("./table_data", "./songdata.db")
	app.mainloop()