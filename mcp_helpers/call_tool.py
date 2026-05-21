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

def call_mcp_tool(tool_name, arguments=None):
    if arguments is None:
        arguments = {}
        
    cmd = [
        "npx", 
        "--registry=https://registry.npmjs.org/", 
        "mcp-remote", 
        "https://mcp.kite.trade/mcp"
    ]
    
    print(f"Spawning MCP server process: {' '.join(cmd)}...", flush=True)
    
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
        return None
        
    stderr_thread = threading.Thread(target=log_stderr, args=(process.stderr,), daemon=True)
    stderr_thread.start()
    
    # Give the process a moment to start up and establish connection
    time.sleep(2)
    
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
    
    process.stdin.write(json.dumps(init_req) + "\n")
    process.stdin.flush()
    
    # Read initialize response
    init_resp_line = process.stdout.readline()
    if not init_resp_line:
        print("Server closed connection on initialize.", file=sys.stderr)
        process.terminate()
        return None
        
    # Step 2: Send 'initialized' notification
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    process.stdin.write(json.dumps(initialized_notification) + "\n")
    process.stdin.flush()
    
    # Step 3: Call target tool
    tool_call_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    print(f"\n---> Calling tool '{tool_name}' with arguments: {arguments}", flush=True)
    process.stdin.write(json.dumps(tool_call_req) + "\n")
    process.stdin.flush()
    
    # Read tool call response
    tool_resp_line = process.stdout.readline()
    
    # Clean shutdown
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        
    if not tool_resp_line:
        print("Server closed connection before returning tool response.", file=sys.stderr)
        return None
        
    try:
        return json.loads(tool_resp_line)
    except Exception as e:
        print(f"Failed to parse tool response: {tool_resp_line}\nError: {e}", file=sys.stderr)
        return None

def main():
    # Default to calling 'get_profile' if no arguments provided
    tool_name = "get_profile"
    arguments = {}
    
    if len(sys.argv) > 1:
        tool_name = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            arguments = json.loads(sys.argv[2])
        except Exception as e:
            print(f"Failed to parse arguments JSON: {e}", file=sys.stderr)
            sys.exit(1)
            
    response = call_mcp_tool(tool_name, arguments)
    if response:
        print("\n--- TOOL RESPONSE RECEIVED ---", flush=True)
        print(json.dumps(response, indent=2), flush=True)
    else:
        print("\nNo response received or error occurred.", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
