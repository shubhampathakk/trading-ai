import subprocess
import json
import sys
import threading
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Subprocess handle and locks
process = None
process_lock = threading.Lock()
stderr_thread = None
current_request_id = 10

def log_stderr(pipe):
    """Reads and logs stderr of the subprocess in a separate thread."""
    for line in iter(pipe.readline, ''):
        if line.strip():
            print(f"[Kite-Server-Stderr] {line.strip()}", file=sys.stderr, flush=True)

def start_mcp_subprocess():
    global process, stderr_thread
    cmd = [
        "npx", 
        "--registry=https://registry.npmjs.org/", 
        "mcp-remote", 
        "https://mcp.kite.trade/mcp"
    ]
    
    print(f"Spawning Kite MCP server process: {' '.join(cmd)}...", flush=True)
    
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
    
    # Wait for startup
    time.sleep(3)
    
    # Initialize session
    print("Performing MCP initialization handshake...", flush=True)
    send_rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "mcp-proxy-client",
            "version": "1.0.0"
        }
    }, rpc_id=1)
    
    init_resp = read_response(expected_id=1)
    if not init_resp:
        print("Failed to initialize Kite MCP server session.", file=sys.stderr)
        sys.exit(1)
        
    print("Initialization successful. Server info:", init_resp.get("result", {}).get("serverInfo", {}), flush=True)
    
    # Send initialized notification
    send_rpc("notifications/initialized", rpc_id=None)
    print("Proxy is fully initialized and connected to remote server.", flush=True)

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
                print(f"[Server-Notification] {json.dumps(msg)}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"JSON Parse Error: {e} for line: {line}", file=sys.stderr, flush=True)

def execute_mcp_tool(tool_name, arguments=None):
    global current_request_id, process_lock
    if arguments is None:
        arguments = {}
        
    with process_lock:
        current_request_id += 1
        req_id = current_request_id
        
        print(f"Calling MCP Tool '{tool_name}' (ID: {req_id}) with args: {arguments}", flush=True)
        send_rpc("tools/call", {
            "name": tool_name,
            "arguments": arguments
        }, rpc_id=req_id)
        
        resp = read_response(expected_id=req_id)
        return resp

class MCPProxyHTTPHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Serve Dashboard Static Files over HTTP (bypasses browser file:// CORS blocks)
        if path.startswith("/dashboard"):
            import os
            rel_path = path.lstrip("/")
            file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
            
            if os.path.isdir(file_path):
                file_path = os.path.join(file_path, "index.html")
                
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"File Not Found")
                return
                
            ext = os.path.splitext(file_path)[1].lower()
            content_type = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml"
            }.get(ext, "application/octet-stream")
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self._set_cors_headers()
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
            return

        # Root status endpoint
        if path == "/" or path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            status_data = {
                "status": "healthy",
                "proxy": "Kite MCP REST Proxy",
                "version": "1.0.0",
                "connection": "active" if process and process.poll() is None else "inactive"
            }
            self.wfile.write(json.dumps(status_data).encode('utf-8'))
            return
        # AI Agent Status Endpoint
        if path == "/bot_status":
            import os
            status_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dashboard/bot_status.json"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            
            try:
                with open(status_path, 'r') as f:
                    content = f.read()
                self.wfile.write(content.encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({"error": f"Failed to read bot status: {e}"}).encode('utf-8'))
            return

        # Standard GET endpoints mapped directly to tools
        tool_mapping = {
            "/login": ("login", {}),
            "/profile": ("get_profile", {}),
            "/holdings": ("get_holdings", {}),
            "/margins": ("get_margins", {}),
            "/positions": ("get_positions", {}),
            "/mf_holdings": ("get_mf_holdings", {}),
            "/gtts": ("get_gtts", {})
        }
        
        if path in tool_mapping:
            tool_name, default_args = tool_mapping[path]
            resp = execute_mcp_tool(tool_name, default_args)
            
            if resp:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Failed to execute tool: {tool_name}"}).encode('utf-8'))
            return
            
        # Endpoint not found
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == "/call":
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body)
                tool_name = data.get("name")
                arguments = data.get("arguments", {})
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode('utf-8'))
                return
                
            if not tool_name:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Field 'name' is required"}).encode('utf-8'))
                return
                
            resp = execute_mcp_tool(tool_name, arguments)
            if resp:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Failed to execute tool: {tool_name}"}).encode('utf-8'))
            return
            
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

def run_http_server(port=5001):
    server_address = ('', port)
    httpd = HTTPServer(server_address, MCPProxyHTTPHandler)
    print(f"\n🚀 Kite MCP REST Proxy listening on http://localhost:{port}/\n", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Shutting down HTTP proxy...", flush=True)
    httpd.server_close()

def main():
    # Start MCP subprocess first
    start_mcp_subprocess()
    
    # Start HTTP Server
    port = 5001
    run_http_server(port)
    
    # Cleanup
    print("Terminating MCP subprocess...", flush=True)
    global process
    if process:
        process.terminate()
        process.wait()
    print("Stopped.", flush=True)

if __name__ == "__main__":
    main()
