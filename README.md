# protoc-gen-mcp: A protobuf plugin to auto-generate MCP manifests and MCP proxy servers.

This project demonstrates how to generate MCP (Model Context Protocol) manifests and Python MCP servers from existing protobuf definitions and existing protobuf servers.

**Disclaimer:** This project is in its early stages. It is meant to be a proof-of-concept at this stage, and is not robust at all.
Some feature gaps have been documented here (see TODO below and in code), and I'm sure there are plenty more gaps unnoticed.

*Author's Note*: I created this project in order to:

1. To learn about MCP's workings by distilling its mechanism to its simplest form.
2. Explore whether there is a gap between the gRPC framework and AI tool usage, and whether this generator can fill that gap.

## TODO
- Support MCP server generation based on an existing gRPC endpoint address outside of localhost.
- Support MCP server generation using the gRPC reflection endpoint, allowing the generated server to generate based on a running gRPC server, as opposed to a `proto` definition file.

## Setup

1. Create and activate a virtual environment using Python 3.13.3:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Generate required protobuf dependencies:
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages/grpc_tools/_proto --python_out=venv/lib/python3.13/site-packages google/protobuf/compiler/plugin.proto google/protobuf/descriptor.proto

python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --python_out=venv/lib/python3.13/site-packages google/api/annotations.proto google/api/http.proto

python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages/grpc_tools/_proto --python_out=. google/protobuf/compiler/plugin.proto
```

3. Generate project protobuf files and make the plugin executable:
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. mcpoptions/mcp_options.proto helloworld/hello_messages.proto

chmod +x protoc-gen-mcp
```

## Code Generation

### Generate the MCP server and its manifest:
Creates only an MCP proxy that connects to external gRPC server: `$(PROTO_SERVICE_FILE_NAME)_$(SERVICE_NAME)_mcp_proxy.py`
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--generate-mcp-proxy,--generate-manifest:. helloworld/hello_service.proto
```

## Example Implementation for e2e Testing

### Generate standalone gRPC server only:
Creates a pure testonly gRPC server implementation: `$(PROTO_SERVICE_FILE_NAME)_$(SERVICE_NAME)_grpc_server.py`
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--grpc_port=9527,--generate-grpc-server:. helloworld/hello_service.proto
```

Add this implementation to `helloworld/hello_service_greeter_grpc_server.py` (on line 16):
```python
def SayHello(self, request, context):
    """Handle SayHello requests"""
    names_greeting = request.person.name
        if request.person.names:
            names_greeting += " aka. "
            names_greeting += ", ".join(request.person.names)
        return hello_messages_pb2.HelloReply(message=f"Hello {names_greeting}! TEST_MARKER_SUCCESS")
```

The end to end test can then be run with
```bash
# Run end-to-end integration test (requires Ollama, will download qwen2.5:latest if not downloaded.)
python -m pytest mcp_integration_test.py -v -s

# Run with a different model (e.g., llama3.2:3b)
OLLAMA_MODEL=llama3.2:3b python -m pytest mcp_integration_test.py -v -s
```

## Optional Flags (for Code Generate)

**Configure custom ports (to be run after Dependency Generation):**
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--generate-mcp-proxy,--generate-manifest,--grpc_port=9527:. helloworld/hello_service.proto
```

## Development:

### Starting the legacy combined MCP server:
```bash
PYTHONPATH=. python helloworld/hello_service_greeter_mcp_server.py
```

### Running separated servers:

**Option 1: Run standalone gRPC server and MCP proxy separately**
```bash
# Terminal 1: Start gRPC server
PYTHONPATH=. python helloworld/hello_service_greeter_grpc_server.py

# Terminal 2: Start MCP proxy (connects to gRPC server on localhost)
PYTHONPATH=. python helloworld/hello_service_greeter_mcp_proxy.py
```

### Cleanup
To reset the working directory:
```bash
find . -name "*pb2*.py" -type f -delete
rm -f helloworld/hello_service_greeter_grpc_server.py
rm -f helloworld/hello_service_greeter_mcp_proxy.py
rm -f helloworld/hello_service.proto.mcp.json
```
