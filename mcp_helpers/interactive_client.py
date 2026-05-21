import subprocess
import json
import sys
import threading
import time

# Global process handle
process = None

def log_stderr(pipe):
    """Reads and logs stderr of the subprocess in a separate thread."""
    for line in iter(pipe.readline, ''):
        if line.strip():
            print(f"[Server-Stderr] {line.strip()}", file=sys.stderr, flush=True)

def send_rpc(method, params=None, rpc_id=1):
    global process
    req = {
        "jsonrpc": "2.0",
        "method": method
    }
    if rpc_id is not None:
        req["id"] = rpc_id
    if params is not None:
        req["params"] = params
        
    process.stdin.write(json.dumps(req) + "\n")
    process.stdin.flush()

def read_response(expected_id):
    global process
    while True:
        line = process.stdout.readline()
        if not line:
            return None
        try:
            msg = json.loads(line)
            if msg.get("id") == expected_id:
                return msg
            else:
                # Log notifications or unrelated messages to stderr so they don't clutter stdout
                print(f"[Server-Notification] {json.dumps(msg)}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"JSON Parse Error: {e} for line: {line}", file=sys.stderr, flush=True)

def main():
    global process
    cmd = [
        "npx", 
        "--registry=https://registry.npmjs.org/", 
        "mcp-remote", 
        "https://mcp.kite.trade/mcp"
    ]
    
    print("Starting Kite MCP Interactive Session...", flush=True)
    
    try:
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
        
    stderr_thread = threading.Thread(target=log_stderr, args=(process.stderr,), daemon=True)
    stderr_thread.start()
    
    # Wait for server startup
    time.sleep(3)
    
    # Step 1: Initialize (Request ID: 1)
    send_rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "interactive-mcp-client",
            "version": "1.0.0"
        }
    }, rpc_id=1)
    
    init_resp = read_response(expected_id=1)
    if not init_resp:
        print("Failed to initialize session.", file=sys.stderr)
        process.terminate()
        sys.exit(1)
        
    # Send initialized notification (No ID)
    send_rpc("notifications/initialized", rpc_id=None)
    
    # Step 2: Call 'login' (Request ID: 2)
    print("\nGenerating secure login URL...", flush=True)
    send_rpc("tools/call", {
        "name": "login",
        "arguments": {}
    }, rpc_id=2)
    
    login_resp = read_response(expected_id=2)
    if not login_resp or "result" not in login_resp:
        print("Failed to obtain login details.", file=sys.stderr)
        process.terminate()
        sys.exit(1)
        
    login_text = login_resp["result"]["content"][0]["text"]
    print("\n====================================================", flush=True)
    print(login_text, flush=True)
    print("====================================================\n", flush=True)
    
    print("[PROMPT] Please log in via the link above in your browser.", flush=True)
    print("[PROMPT] Once authorized successfully, type 'done' and press Enter below:", flush=True)
    sys.stdout.flush()
    
    # Wait for user confirmation on stdin
    user_input = sys.stdin.readline().strip().lower()
    print(f"\nUser entered: '{user_input}'. Checking authentication...", flush=True)
    
    # Step 3: Get Profile to verify login (Request ID: 3)
    send_rpc("tools/call", {
        "name": "get_profile",
        "arguments": {}
    }, rpc_id=3)
    
    profile_resp = read_response(expected_id=3)
    print("\n--- PROFILE RESPONSE ---", flush=True)
    print(json.dumps(profile_resp, indent=2), flush=True)
    
    # Step 4: Get Margins (Request ID: 4)
    send_rpc("tools/call", {
        "name": "get_margins",
        "arguments": {}
    }, rpc_id=4)
    
    margins_resp = read_response(expected_id=4)
    print("\n--- MARGINS RESPONSE ---", flush=True)
    print(json.dumps(margins_resp, indent=2), flush=True)
    
    # Step 5: Get Holdings (Request ID: 5)
    send_rpc("tools/call", {
        "name": "get_holdings",
        "arguments": {}
    }, rpc_id=5)
    
    holdings_resp = read_response(expected_id=5)
    print("\n--- HOLDINGS RESPONSE ---", flush=True)
    print(json.dumps(holdings_resp, indent=2), flush=True)
    
    # Keep alive or close
    print("\nInteractive session finished. Shutting down...", flush=True)
    process.terminate()
    process.wait()
    print("Session closed.", flush=True)

if __name__ == "__main__":
    main()
