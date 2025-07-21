# protoc-gen-mcp: A protobuf plugin to auto-generate MCP manifests and MCP proxy servers.

This project demonstrates how to generate MCP (Model Context Protocol) manifests and Python MCP servers from existing protobuf definitions and existing protobuf servers.

**Disclaimer:** This project is in its early stages. It is meant to be a proof-of-concept at this stage, and is not robust at all.
Some feature gaps have been documented here (see TODO below and in code), and I'm sure there are plenty more gaps unnoticed.

*Author's Note*: I created this project in order to:

1. To learn about MCP's workings by distilling its mechanism to its simplest form.
2. Explore whether there is a gap between the gRPC framework and AI tool usage, and whether this generator can fill that gap.

## TODO
- Support standalone MCP server generation, allowing the generated server to point to an existing gRPC server implementation.
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

### Generate both grpc stub, MCP proxy and MCP manifest (default):
Note: In this stage of the project, the gRPC stub and MCP proxy will be in the same file: `$(PROTO_SERVICE_FILE_NAME)_$(SERVICE_NAME)_mcp_server.py`
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=. helloworld/hello_service.proto
```

## Example Implementation for e2e Testing

Add this implementation to `helloworld/hello_service_greeter_mcp_server.py` (on line 26):
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

## Optional Flags

**Generate gRPC server stub and MCP proxy file only:**
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--generate-server-only:. helloworld/hello_service.proto
```

**Generate MCP manifest only:**
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--generate-manifest-only:. helloworld/hello_service.proto
```

**Configure custom ports:**
```bash
python -m grpc_tools.protoc --proto_path=venv/lib/python3.13/site-packages --proto_path=. --python_out=. --grpc_python_out=. --plugin=protoc-gen-mcp=protoc-gen-mcp --mcp_out=--mcp_port=7788,--grpc_port=9527:. helloworld/hello_service.proto
```

## Development:

### Starting the MCP server:
```bash
PYTHONPATH=. python helloworld/hello_service_greeter_mcp_server.py
```

### Cleanup
To reset the working directory:
```bash
find . -name "*pb2*.py" -type f -delete
rm -f helloworld/hello_service_greeter_mcp_server.py
rm -f helloworld/hello_service.proto.mcp.json
```
