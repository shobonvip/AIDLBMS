import gzip
import shutil
from pathlib import Path

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

if __name__ == "__main__":
	extract_all_bmt("./table")