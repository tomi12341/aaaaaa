FROM python:3.9

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y build-essential git

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコピー
COPY . /app

# 必要なPythonパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# コマンドを指定
CMD ["python", "your_bot_script.py"]
