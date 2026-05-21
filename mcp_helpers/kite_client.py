import subprocess
import json
import sys
import threading
import time

def log_stderr(pipe):
    """Reads and logs stderr of the subprocess in a separate thread."""
    for line in iter(pipe.readline, ''):
        if line.strip():
            print(f"[Server-Stderr] {line.strip()}", file=sys.stderr, flush=True)

def main():
    cmd = [
        "npx", 
        "--registry=https://registry.npmjs.org/", 
        "mcp-remote", 
        "https://mcp.kite.trade/mcp"
    ]
    
    print(f"Spawning MCP server process: {' '.join(cmd)}...", flush=True)
    
    try:
        # Spawn the process with line-buffered output (bufsize=1)
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"Failed to spawn subprocess: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Start thread to read stderr
    stderr_thread = threading.Thread(target=log_stderr, args=(process.stderr,), daemon=True)
    stderr_thread.start()
    
    # Give the process a moment to start up and establish connection
    print("Waiting for server connection...", flush=True)
    time.sleep(3)
    
    # Step 1: Send 'initialize' request
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "python-mcp-client",
                "version": "1.0.0"
            }
        }
    }
    
    print("\n---> Sending 'initialize' request to stdout", flush=True)
    process.stdin.write(json.dumps(init_req) + "\n")
    process.stdin.flush()
    
    # Read initialize response from stdout
    print("Waiting for 'initialize' response...", flush=True)
    init_resp_line = process.stdout.readline()
    if not init_resp_line:
        print("Server closed connection on initialize.", file=sys.stderr)
        process.terminate()
        sys.exit(1)
        
    try:
        init_resp = json.loads(init_resp_line)
        print("<--- Received Response:", flush=True)
        print(json.dumps(init_resp, indent=2), flush=True)
    except Exception as e:
        print(f"Failed to parse response line: {init_resp_line}\nError: {e}", file=sys.stderr)
        process.terminate()
        sys.exit(1)
        
    # Step 2: Send 'initialized' notification
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    print("\n---> Sending 'notifications/initialized'", flush=True)
    process.stdin.write(json.dumps(initialized_notification) + "\n")
    process.stdin.flush()
    
    # Step 3: Call 'login' tool
    tool_call_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "login",
            "arguments": {}
        }
    }
    
    print("\n---> Calling 'login' tool", flush=True)
    process.stdin.write(json.dumps(tool_call_req) + "\n")
    process.stdin.flush()
    
    # Read tool call response from stdout
    print("Waiting for tool response...", flush=True)
    tool_resp_line = process.stdout.readline()
    if not tool_resp_line:
        print("Server closed connection on tool call.", file=sys.stderr)
        process.terminate()
        sys.exit(1)
        
    try:
        tool_resp = json.loads(tool_resp_line)
        print("\n--- TOOL RESPONSE RECEIVED ---", flush=True)
        print(json.dumps(tool_resp, indent=2), flush=True)
    except Exception as e:
        print(f"Failed to parse tool response: {tool_resp_line}\nError: {e}", file=sys.stderr)
        
    # Clean shutdown
    print("\nTerminating server process...", flush=True)
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
    print("Finished.", flush=True)

if __name__ == "__main__":
    main()
