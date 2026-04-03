import re

def convert_to_drive_direct_link(url):
    """
    Google Driveの各種URLからファイルIDを抜き出し、
    直接アクセス用URL（uc?id=）に変換する。
    """
    # IDを抽出するための正規表現パターン
    # 1. /file/d/([ID])/... 形式
    # 2. id=([ID]) 形式
    # の両方をキャプチャする
    pattern = r'(?:/file/d/|id=)([a-zA-Z0-9_-]{25,})'
    
    match = re.search(pattern, url)
    
    if match:
        file_id = match.group(1)
        # 直リンクURLを構築
        direct_url = f"https://drive.google.com/uc?id={file_id}"
        return direct_url
    
    return None

# --- テスト ---
urls = [
    "https://drive.google.com/file/d/1d01WX7O3S4t5mgHJIQVy3EFEFuJkVOiA/view?afiojioaskd",
    "https://drive.usercontent.google.com/download?id=1d01WX7O3S4t5mgHJIQVy3EFEFuJkVOiA&export=download&authuser=0"
]

for url in urls:
    result = convert_to_drive_direct_link(url)
    print(f"変換前: {url}")
    print(f"変換後: {result}\n")