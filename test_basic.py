import os
from dotenv import load_dotenv

# 👉 打印当前路径（确认运行目录）
print("当前路径:", os.getcwd())

# 👉 强制指定路径加载（关键）
load_dotenv(dotenv_path="./.env")

print("ENV:", os.getenv("EMAIL_SENDER"))

def test_env():
    assert os.getenv("EMAIL_SENDER") is not None, "缺少 EMAIL_SENDER"
    assert os.getenv("DEEPSEEK_API_KEY") is not None, "缺少 API KEY"

def test_import():
    import fetch_and_send
    print("import ok")

if __name__ == "__main__":
    test_env()
    test_import()
    print("✅ 测试通过")