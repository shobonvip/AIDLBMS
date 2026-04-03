from dotenv import load_dotenv
import os
from google import genai

def setup_gemini():
	load_dotenv()
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)
