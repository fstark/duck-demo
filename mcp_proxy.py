#!/usr/bin/env python3
"""
MCP stdio proxy that logs all JSON-RPC messages between VS Code and the server.
Usage: python mcp_proxy.py <log_file> <python_script> [args...]

Logs every message in both directions to the log file.
"""
import sys
import os
import json
import subprocess
import threading
import time

def main():
    if len(sys.argv) < 3:
        print("Usage: python mcp_proxy.py <log_file> <python_script> [args...]", file=sys.stderr)
        sys.exit(1)

    log_file = sys.argv[1]
    script = sys.argv[2]
    extra_args = sys.argv[3:]

    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")

    proc = subprocess.Popen(
        [venv_python, script] + extra_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # Pass server stderr through
        bufsize=0,
    )

    def log(direction, data):
        timestamp = time.strftime("%H:%M:%S.") + f"{time.time() % 1:.3f}"[2:]
        try:
            parsed = json.loads(data)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pretty = repr(data)
        
        with open(log_file, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] {direction}\n")
            f.write(f"{'='*60}\n")
            f.write(pretty + "\n")

    # Clear log file
    with open(log_file, "w") as f:
        f.write(f"MCP Proxy Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Server: {script} {' '.join(extra_args)}\n")

    def forward_stdin():
        """Read from VS Code (our stdin) and forward to server."""
        try:
            while True:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                log("CLIENT → SERVER", line.decode("utf-8", errors="replace").strip())
                proc.stdin.write(line)
                proc.stdin.flush()
        except Exception as e:
            log("ERROR", f"stdin forward error: {e}")
        finally:
            try:
                proc.stdin.close()
            except:
                pass

    def forward_stdout():
        """Read from server stdout and forward to VS Code (our stdout)."""
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                log("SERVER → CLIENT", line.decode("utf-8", errors="replace").strip())
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        except Exception as e:
            log("ERROR", f"stdout forward error: {e}")

    stdin_thread = threading.Thread(target=forward_stdin, daemon=True)
    stdout_thread = threading.Thread(target=forward_stdout, daemon=True)

    stdin_thread.start()
    stdout_thread.start()

    proc.wait()
    stdout_thread.join(timeout=2)

if __name__ == "__main__":
    main()
