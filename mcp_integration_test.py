#!/usr/bin/env python3
"""
Integration test for MCP manifest and MCP server.

This test:
1. Spins up Ollama server on one thread
2. Runs the MCP server with stdio transport
3. Has the LLM read the MCP manifest to understand the MCP server
4. Tests that the LLM can correctly interact with the server using MCP protocol

Author's note: I'm not gonna lie, this was mostly AI generated. I did comb
through to ensure that it looks right, but I'm no expert so ¯\\_(ツ)_/¯.
"""

import json
import time
import subprocess
import sys
import os
import requests
import shutil
import pytest
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


class OllamaManager:
    """Manages Ollama server process"""
    
    def __init__(self, model: str = "llama3.2:3b", port: int = 11434):
        self.model = model
        self.port = port
        self.process = None
        self.server_ready = False
        
    def start(self):
        """Start Ollama server process"""
        # Check if ollama is installed
        if not shutil.which("ollama"):
            raise RuntimeError("Ollama is not installed. Please install it first.")
        
        print(f"Starting Ollama server on port {self.port}...")
        
        # Start Ollama server
        env = os.environ.copy()
        env['OLLAMA_HOST'] = f"127.0.0.1:{self.port}"
        
        self.process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        # Wait for server to be ready
        self._wait_for_ollama()
        
        # Pull model if needed
        print(f"Ensuring model {self.model} is available...")
        self._ensure_model()
        
        print("Ollama server started successfully!")
        
    def _wait_for_ollama(self, timeout: int = 30):
        """Wait for Ollama to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{self.port}/api/version", timeout=1)
                if response.status_code == 200:
                    self.server_ready = True
                    return
            except:
                pass
            time.sleep(0.5)
        
        raise TimeoutError(f"Ollama did not start within {timeout} seconds")
    
    def _ensure_model(self):
        """Ensure the model is pulled and available"""
        try:
            # Check if model exists
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if self.model not in result.stdout:
                print(f"Pulling model {self.model}...")
                subprocess.run(
                    ["ollama", "pull", self.model],
                    check=True,
                    timeout=300  # 5 minutes timeout for model pull
                )
            else:
                print(f"Model {self.model} already available")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Model pull timed out for {self.model}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to pull model {self.model}: {e}")
    
    def stop(self):
        """Stop Ollama server process"""
        if self.process:
            print("Stopping Ollama server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("Force killing Ollama server...")
                self.process.kill()
                self.process.wait()
            self.process = None
    
    def is_running(self) -> bool:
        """Check if Ollama server is running"""
        return self.server_ready


class OllamaLLM:
    """Simple Ollama LLM client"""
    
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.session = requests.Session()
        
    def chat(self, prompt: str, system_prompt: str = "") -> str:
        """Send a chat message to Ollama"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60  # Longer timeout for LLM responses
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"


class MCPServerManager:
    """Manages the MCP server process"""
    
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.server_ready = False
        
    def start(self):
        """Start the MCP server process"""
        print(f"MCP server configured: {self.script_path}")
        # MCP servers are started on-demand by the client, not as persistent processes
        self.server_ready = True
        print("MCP server manager ready!")
        
    def stop(self):
        """Stop the MCP server process"""
        print("MCP server manager stopped")
        self.server_ready = False
    
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.server_ready
    
    def get_server_command(self) -> tuple[str, list[str], dict[str, str]]:
        """Get MCP server command for client connection"""
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(os.path.dirname(__file__))
        
        return (sys.executable, [self.script_path], env)


# Pytest fixtures
@pytest.fixture(scope="session")
def model_name(request):
    """Get model name from environment variable"""
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    return model


@pytest.fixture(scope="session")
def ollama_manager(model_name):
    """Session-scoped Ollama server"""
    manager = OllamaManager(model=model_name)
    manager.start()
    yield manager
    manager.stop()


@pytest.fixture(scope="session")
def server_manager():
    """Session-scoped MCP server"""
    manager = MCPServerManager("helloworld/hello_service_greeter_mcp_server.py")
    manager.start()
    yield manager
    manager.stop()


@pytest.fixture
def llm_client(ollama_manager, model_name):
    """LLM client instance"""
    return OllamaLLM(model=model_name)


@pytest.fixture
def manifest_path():
    """Path to the MCP manifest file"""
    return "helloworld/hello_service.proto.mcp.json"


@pytest.fixture
def manifest_data(manifest_path):
    """Load MCP manifest data"""
    try:
        with open(manifest_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        pytest.skip(f"MCP manifest not found at {manifest_path}")
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON in manifest: {e}")


# Test classes
class TestMCPIntegration:
    """MCP integration test suite"""
    
    def test_manifest_parsing(self, llm_client, manifest_data):
        """Test that the LLM can parse the MCP manifest correctly"""
        system_prompt = """You are a test assistant. You will be given an MCP manifest in JSON format. 
        Your job is to understand what tools are available and how to use them.
        
        Be precise and factual. Format your response clearly."""
        
        manifest_json = json.dumps(manifest_data, indent=2)
        
        prompt = f"""
        Here is an MCP manifest:
        
        {manifest_json}
        
        Please analyze this manifest and tell me:
        1. What is the server transport type?
        2. What tools are available and what do they do?
        3. For each tool, what input parameters are required?
        4. What is the expected output format?
        
        Please be specific and structured in your response.
        """
        
        response = llm_client.chat(prompt, system_prompt)
        
        # Basic validation
        response_lower = response.lower()
        assert "stdio" in response_lower, "LLM didn't identify stdio transport"
        assert "say_hello" in response_lower, "LLM didn't identify say_hello tool"
        assert "name" in response_lower, "LLM didn't identify name parameter"
        
        print(f"LLM Analysis:\n{response}")
    
    @pytest.mark.asyncio
    async def test_mcp_server_endpoint(self, manifest_data):
        """Test that the MCP server endpoint works correctly"""
        # Verify transport is stdio
        assert manifest_data["server"]["transport"]["type"] == "stdio"
        
        # Set up server command directly
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(os.path.dirname(__file__))
        
        # Create FastMCP client with stdio transport
        transport = StdioTransport(
            command=sys.executable, 
            args=["helloworld/hello_service_greeter_mcp_server.py"], 
            env=env
        )
        client = Client(transport=transport)
        
        # Test MCP server connection
        async with client:
            # List tools
            tools_result = await client.list_tools()
            assert len(tools_result) > 0
            
            # Find the say_hello tool
            say_hello_tool = None
            for tool in tools_result:
                if tool.name == "say_hello":
                    say_hello_tool = tool
                    break
            
            assert say_hello_tool is not None, "say_hello tool not found"
            
            # Call the tool
            result = await client.call_tool("say_hello", {"name": "TestUser"})
            
            # Check result
            assert result is not None
            
            # Check for success marker in the response
            response_text = str(result)
            assert "TEST_MARKER_SUCCESS" in response_text
            print(f"MCP Server Response: {response_text}")
    
    @pytest.mark.asyncio
    async def test_llm_tool_calling(self, llm_client, manifest_data, server_manager):
        """Test LLM making actual tool calls through MCP"""
        # Extract tools from manifest
        tools = manifest_data.get("tools", [])
        assert tools, "No tools found in manifest"
        
        # Format tools for function calling
        function_definitions = []
        for tool in tools:
            func_def = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": tool["inputSchema"].get("properties", {}),
                    "required": tool["inputSchema"].get("required", [])
                }
            }
            function_definitions.append(func_def)
        
        # Create a prompt that asks the LLM to use the tools
        system_prompt = f"""You are an AI assistant with access to tools. You have the following tools available:

{json.dumps(function_definitions, indent=2)}

These tools use the MCP (Model Context Protocol) for communication. 
When you want to use a tool, respond with a JSON object in this format:
{{
    "tool_call": {{
        "name": "tool_name",
        "arguments": {{"param": "value"}}
    }}
}}

Be sure to use the exact tool names and parameter names as defined.
"""
        
        user_prompt = "I want to say hello to someone named \"MCPUser\". " + \
            "Please use the available tools to do this. Respond only with the JSON payload."
        
        llm_response = llm_client.chat(user_prompt, system_prompt)
        print(f"LLM Response: {llm_response}")
        
        # Try to parse tool call from LLM response
        tool_call_expected = {
            "tool_call": {
                "name": "say_hello",
                "arguments": {
                    "name": "MCPUser"
                }
            }
        }
        assert tool_call_expected == json.loads(llm_response), "LLM didn't return valid JSON tool call"
        
        tool_call = tool_call_expected["tool_call"]
        tool_name = tool_call["name"]
        tool_args = tool_call["arguments"]
        
        print(f"LLM wants to call tool: {tool_name} with args: {tool_args}")
        
        # Make the actual MCP tool call. This is done manually as LLMs cannot make external network calls.
        command, args, env = server_manager.get_server_command()
        
        # Create FastMCP client with stdio transport
        transport = StdioTransport(command=command, args=args, env=env)
        client = Client(transport=transport)
        
        async with client:
            # Call the tool
            mcp_result = await client.call_tool(tool_name, tool_args)
            
            # Extract the result text
            result_text = str(mcp_result)
            
            # Parse the JSON result from the MCP response
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                result = {"message": result_text}
        
        print(f"Tool result: {result}")
        
        # Feed the response back to the LLM
        follow_up_prompt = f"""
        You previously made a tool call to "{tool_name}" with arguments {tool_args}.
        
        The tool returned the following result:
        {json.dumps(result, indent=2)}
        
        Please analyze this response and tell me:
        1. What did the tool return?
        2. Does this result make sense for the task you were trying to accomplish?
        
        Please provide a brief, clear summary of what happened.
        """
        
        llm_analysis = llm_client.chat(follow_up_prompt)
        print(f"\nLLM Analysis of Tool Result:\n{'-' * 40}")
        print(llm_analysis)
        print('-' * 40)
        
        # Check for success marker
        response_message = result.get("message", "")
        assert "TEST_MARKER_SUCCESS" in response_message, "Tool call didn't get expected response"


class TestManifestValidation:
    """Test manifest structure and content"""
    
    def test_manifest_structure(self, manifest_data):
        """Test that manifest has required fields"""
        required_fields = ['mcpVersion', 'name', 'server', 'tools']
        for field in required_fields:
            assert field in manifest_data, f"Missing required field: {field}"
    
    def test_server_config(self, manifest_data):
        """Test server configuration"""
        server = manifest_data["server"]
        assert "transport" in server
        assert server["transport"]["type"] == "stdio"
    
    def test_tools_structure(self, manifest_data):
        """Test tools structure"""
        tools = manifest_data.get("tools", [])
        assert len(tools) > 0, "No tools found in manifest"
        
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "outputSchema" in tool


if __name__ == "__main__":
    pytest.main([__file__])