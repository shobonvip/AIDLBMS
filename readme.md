このツールは生成 AI を用いながら BMS の DL を自動化するものです。

起動時には beatoraja*/table, beatoraja*/songdata.db を指定します。また, .env ファイルを作成し、GEMINI_API_KEY='YOUR API KEY' を付け加えてください。

使用するモデルは Gemini 3.1 Flash Lite, 使用料金は satellite を 1 曲入れるのに平均 0.25 円前後だと思います。

### 導入手段

Windows の場合

Python3 の導入が必要です。バージョンは Python 3.10-3.12 では動くと思います

1. install.bat を実行してください
2. startup.bat で起動します
3. .env ファイルを作成し, GEMINI_API_KEY='YOUR API KEY' を付け加えます

Linux の場合

まだ起動手段がありませんが、bat の中身に沿って実行することで起動できます。開発時に Linux で実行確認してるのでいけるはず

### Version 1.0

精度半分くらい