"""RAG 知识库系统 — 一键启动脚本"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main():
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║   RAG 知识库系统                 ║")
    print("  ╚══════════════════════════════════╝")
    print()
    print("  启动中... 请稍候")
    print()

    project_root = Path(__file__).resolve().parent

    # 启动 API
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "rag.api:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_root),
    )

    # 等待 API 就绪
    import urllib.request

    for i in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("  [警告] API 启动超时，请检查终端输出")

    print("  ╔══════════════════════════════════╗")
    print("  ║   服务已就绪！                    ║")
    print("  ║   http://localhost:8000           ║")
    print("  ║   关闭此窗口停止服务              ║")
    print("  ╚══════════════════════════════════╝")
    print()

    webbrowser.open("http://localhost:8000")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n  服务已停止。")


if __name__ == "__main__":
    main()
