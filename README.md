# Readwise Chat 📚💬 MCP server

Chat with your [Reader](https://readwise.io/read) library using Claude Desktop. Made possible with Anthropic's [Model Context Protocol](https://www.anthropic.com/news/model-context-protocol?__readwiseLocation=).

> [!NOTE]
> 🚨 🚧 🏗️ Readwise Chat is under active development, as is the MCP specification itself. Core features are working but some advanced capabilities are still in progress.

## Components

### Resources

> [!NOTE]
> 🚨 🚧 🏗️ Under development

### Prompts

> [!NOTE]
> 🚨 🚧 🏗️ Under development

### Tools

The server implements two tools:
- add-document: Adds a new document to your Reader library
  - Takes "url" as required string arguments
  - Updates server state and notifies clients of resource changes
- list-documents: List documents in your Reader library
  - Takes "location" as a required string argument
  - Optional "category" or "updated after" string arguments

## Configuration

[TODO: Add configuration details specific to your implementation]

## Quickstart

### Install

#### Claude Desktop

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  ```
  "mcpServers": {
    "readwise-chat": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/scott_carvalho/projects/readwise-projects/readwise-chat",
        "run",
        "readwise-chat"
      ]
    }
  }
  ```
</details>

<details>
  <summary>Published Servers Configuration</summary>
  ```
  "mcpServers": {
    "readwise-chat": {
      "command": "uvx",
      "args": [
        "readwise-chat"
      ]
    }
  }
  ```
</details>

## Development

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/scott_carvalho/projects/readwise-projects/readwise-chat run readwise-chat
```


Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.