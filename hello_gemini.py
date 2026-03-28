from dotenv import load_dotenv
import os
from google import genai


def setup_gemini():
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise ValueError("環境変数 'GEMINI_API_KEY' が設定されていません。")
	
	return genai.Client(api_key=api_key)

load_dotenv()
client = setup_gemini()
response = client.models.generate_content(
	model = "gemini-3.1-flash-lite-preview",
	contents = "Hello World!"
)

print(response.text)