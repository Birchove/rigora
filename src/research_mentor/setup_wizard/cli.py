"""`rigora-setup`: guided onboarding that writes the local `.env`."""

from __future__ import annotations

import argparse
import threading
import webbrowser

from research_mentor.setup_wizard.env_file import env_path
from research_mentor.setup_wizard.server import build_server, new_state


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rigora-setup",
        description="在浏览器里完成 Rigora 的产品介绍与模型配置，写入本机 .env。",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="面板端口，默认由系统分配一个空闲端口。",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="不自动打开浏览器，只打印地址。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state = new_state(env_file=env_path())
    server = build_server(state, port=args.port)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/?t={state.token}"

    print("Rigora 配置引导")
    print(f"  目标文件: {env_path()}")
    print(f"  面板地址: {url}")
    print("  地址包含一次性 token，只在本机有效，不要分享。")
    print("  完成写入后本进程会自动退出；中途放弃按 Ctrl+C。")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if not args.no_browser:
        webbrowser.open(url)

    try:
        state.finished.wait()
    except KeyboardInterrupt:
        print("\n已取消，.env 未被修改。")
        return 130
    finally:
        server.shutdown()
        server.server_close()

    print(f"已写入 {state.written_to}")
    print("重启 API 服务后生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
