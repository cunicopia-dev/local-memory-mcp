# FastMCP Framework

## Overview

FastMCP is a high-level, Pythonic framework designed to simplify the creation of Model Context Protocol (MCP) servers and clients. It abstracts away the complexities of the MCP protocol, allowing developers to focus on building functionality rather than handling protocol details.

## Key Features

- **Simplicity**: Minimal boilerplate code required to create MCP servers
- **Pythonic Design**: Leverages Python decorators and type hints for intuitive development
- **Comprehensive**: Implements the full MCP specification
- **Extensible**: Supports both synchronous and asynchronous functions
- **Client Support**: Includes tools for both server and client implementations
- **Development Tools**: Built-in debugging and testing capabilities

## Installation

```bash
pip install fastmcp
```

## Core Components

### FastMCP Server

The main class representing your MCP application:

```python
from fastmcp import FastMCP

# Create a server instance
mcp = FastMCP(name="MyServer")

# Run the server
if __name__ == "__main__":
    mcp.run()
```

### Tools

Functions that can be called by LLMs to perform actions:

```python
@mcp.tool
def calculate_sum(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b
```

### Resources

Data sources that can be accessed by LLMs:

```python
@mcp.resource("data://config")
def get_config() -> dict:
    """Provides the application configuration."""
    return {"theme": "dark", "version": "1.0"}
```

Resources with parameters:

```python
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: int) -> dict:
    """Retrieves a user's profile by ID."""
    return {"id": user_id, "name": f"User {user_id}", "status": "active"}
```

### Prompts

Templates that guide LLMs in using tools and resources:

```python
@mcp.prompt
def analyze_data(data_points: list[float]) -> str:
    """Creates a prompt asking for analysis of numerical data."""
    formatted_data = ", ".join(str(point) for point in data_points)
    return f"Please analyze these data points: {formatted_data}"
```

## Advanced Features

### Client Implementation

```python
from fastmcp import Client

# MCP configuration with multiple servers
config = {
    "mcpServers": {
        "weather": {"url": "https://weather-api.example.com/mcp"},
        "assistant": {"command": "python", "args": ["./assistant_server.py"]}
    }
}

# Create a client connecting to all servers
client = Client(config)

async def main():
    async with client:
        # Access tools and resources with server prefixes
        forecast = await client.call_tool("weather_get_forecast", {"city": "London"})
```

### Server Proxying

Create a FastMCP server that acts as an intermediary for another MCP server:

```python
from fastmcp import FastMCP

# Create a proxy for a remote MCP server
proxy = FastMCP.as_proxy("https://example.com/mcp")

# Run the proxy server
if __name__ == "__main__":
    proxy.run()
```

### Debugging

FastMCP includes a built-in MCP Inspector for testing your server:

```bash
mcp dev server.py
```

This opens a web interface at http://127.0.0.1:6274 for exploring and testing your server's tools, resources, and prompts.

## Best Practices

1. **Descriptive Metadata**: Always provide clear descriptions for your tools and resources
2. **Type Hints**: Use Python type hints to ensure proper data validation
3. **Error Handling**: Implement robust error handling in your functions
4. **Resource Naming**: Use consistent URI patterns for resources
5. **Security**: Be mindful of authentication and authorization requirements

## Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [FastMCP GitHub Repository](https://github.com/jlowin/fastmcp)
- [PyPI Package](https://pypi.org/project/fastmcp/)