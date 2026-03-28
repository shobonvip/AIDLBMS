import sqlite3
import json
from typing import List, Set

# songdata.db を読み取り md5 の set を返す.
def get_owned_md5_set(songdata_db_path: str) -> Set[str]:
	conn = sqlite3.connect(songdata_db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT md5 FROM song")
	owned_md5s = {row[0] for row in cursor.fetchall() if row[0]}
	conn.close()
	return owned_md5s

# 難易度表から持っていない曲一覧の情報を返す
def find_missing_songs(json_path: str, index: int, owned_md5s: List[str]):
	missing_songs = []	
	with open(json_path, 'r', encoding='utf-8') as f:
		data = json.load(f)
	try:
		folder = data.get("folder", [])[index]
	
	except (IndexError, TypeError):
		print(f"Error: Index {index} not found in {json_path}")
		return []
	
	for song in data.get("folder", [])[index].get("songs", []):
		md5 = song.get("md5")
		if not md5: continue
		data_class = song.get("class")
		if data_class != "bms.player.beatoraja.song.SongData":
			continue

		if md5 not in owned_md5s:
			missing_songs.append({
				"title": song.get("title"),
				"artist": song.get("artist"),
				"url": song.get("url"),
				"appendurl": song.get("appendurl"),
				"md5": md5
			})
	
	return missing_songs

