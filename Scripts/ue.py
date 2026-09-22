#!/usr/bin/env python3
"""Build, launch and control this project with Unreal's bundled Python transport."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "RPGPrototype.uproject"
ENGINE = Path(os.environ.get("UE_ROOT", "/Users/Shared/Epic Games/UE_5.8"))
EDITOR = ENGINE / "Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
TRANSPORT = ENGINE / "Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py"


def run_remote(code, timeout=30, discover=False):
    spec = importlib.util.spec_from_file_location("ue_remote_execution", TRANSPORT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.RemoteExecutionConfig()
    config.multicast_bind_address = "127.0.0.1"
    config.multicast_ttl = 0
    config.command_endpoint = ("127.0.0.1", 6777)

    # Multicast discovery is unreliable on macOS when a VPN installs the
    # default route. The editor is deliberately bound to loopback, so send the
    # protocol's open/close datagrams straight to that listener instead.
    node_id = str(uuid.uuid4())

    class DirectBroadcast:
        def __init__(self):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        def send(self, type_, data=None):
            message = module._RemoteExecutionMessage(type_, node_id, None, data)
            self.sock.sendto(message.to_json_bytes(), ("127.0.0.1", 6776))

        def broadcast_open_connection(self, _remote_node_id):
            self.send(module._TYPE_OPEN_CONNECTION, {
                "command_ip": config.command_endpoint[0],
                "command_port": config.command_endpoint[1],
            })

        def broadcast_close_connection(self, _remote_node_id):
            self.send(module._TYPE_CLOSE_CONNECTION)

        def close(self):
            self.sock.close()

    direct = DirectBroadcast()
    connection = module._RemoteExecutionCommandConnection(config, node_id, None)

    def expired(*_):
        raise TimeoutError("Unreal command timed out. Check the editor for modal dialogs; execution may still be running. Do not retry mutations blindly.")

    previous_handler = signal.signal(signal.SIGALRM, expired)
    signal.alarm(timeout)
    try:
        connection.open(direct)
        # Recheck the project on the established connection before executing any code.
        guard = "import unreal; from pathlib import Path; assert Path(unreal.Paths.project_dir()).resolve() == Path(" + repr(str(ROOT)) + "), 'Wrong Unreal project'"
        checked = connection.run_command(guard, True, module.MODE_EXEC_FILE)
        if not checked.get("success"):
            return checked
        if discover:
            return {"success": True, "editor": {
                "project_root": str(ROOT),
                "project_name": PROJECT.stem,
                "transport": "loopback-direct",
            }}
        return connection.run_command(code, True, module.MODE_EXEC_FILE)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
        connection.close(direct)
        direct.close()


def script_code(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return "import runpy; runpy.run_path(" + repr(str(path)) + ", run_name='__main__')"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("doctor", "build", "generate", "open", "status", "bootstrap", "smoke"):
        sub.add_parser(action)
    execute = sub.add_parser("exec", help="Execute Python in the open editor")
    execute.add_argument("code")
    execute.add_argument("--timeout", type=int, default=30)
    script = sub.add_parser("script", help="Run a Python file in the open editor")
    script.add_argument("file")
    script.add_argument("--timeout", type=int, default=60)
    headless = sub.add_parser("headless", help="Run a Python commandlet with the editor closed")
    headless.add_argument("file")
    args = parser.parse_args()
    if not EDITOR.is_file() or not TRANSPORT.is_file():
        parser.error("Unreal Engine not found. Set UE_ROOT to the engine installation directory.")
    if args.action == "doctor":
        version = json.loads((ENGINE / "Engine/Build/Build.version").read_text())
        print(json.dumps({"engine": str(ENGINE), "version": version,
                          "project": str(PROJECT), "python_transport": str(TRANSPORT)}, indent=2))
        subprocess.run(["xcodebuild", "-version"], check=True)
        # `--find` succeeds even when Xcode's separately downloaded Metal
        # toolchain is missing, so execute both tools to catch that state.
        # Xcode 26 keeps Metal in a separate cryptex toolchain. Supplying the
        # SDK makes xcrun resolve that toolchain instead of the legacy stub.
        subprocess.run(["xcrun", "--sdk", "macosx", "metal", "--version"], check=True)
        subprocess.run(["xcrun", "--sdk", "macosx", "metallib", "--version"], check=True)
        return 0
    if args.action == "build":
        processes = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
        active = [line.strip() for line in processes.splitlines()
                  if "/UnrealEditor.app/Contents/MacOS/UnrealEditor " in line and str(PROJECT) in line]
        if active:
            raise RuntimeError("Close this project's Unreal Editor before building (including a process stuck on exit).")
        return subprocess.call([str(ENGINE / "Engine/Build/BatchFiles/Mac/Build.sh"),
                                "RPGPrototypeEditor", "Mac", "Development", str(PROJECT),
                                "-WaitMutex", "-NoHotReloadFromIDE", "-architecture=arm64"])
    if args.action == "generate":
        return subprocess.call([str(ENGINE / "Engine/Build/BatchFiles/Mac/GenerateProjectFiles.sh"),
                                "-project=" + str(PROJECT), "-game"])
    if args.action == "open":
        return subprocess.call(["open", "-a", str(EDITOR.parents[2]), "--args", str(PROJECT), "-log"])
    if args.action == "headless":
        script_path = Path(args.file).resolve()
        if not script_path.is_file():
            raise FileNotFoundError(script_path)
        return subprocess.call([str(EDITOR), str(PROJECT), "-run=pythonscript",
                                "-script=" + str(script_path), "-unattended", "-nullrhi", "-nosplash"])
    timeout = getattr(args, "timeout", 60)
    if timeout < 1:
        parser.error("timeout must be positive")
    if args.action == "status":
        result = run_remote("", timeout, discover=True)
    else:
        if args.action in ("bootstrap", "smoke"):
            code = script_code(ROOT / "Content/Python" / ("biome_smoke.py" if args.action == "smoke" else "bootstrap.py"))
        elif args.action == "script":
            code = script_code(args.file)
        else:
            code = args.code
        result = run_remote(code, timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
