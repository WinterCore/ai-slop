from abc import abstractmethod
from datetime import datetime
import re
import traceback
from pathlib import Path
import sys
import json
from typing import ClassVar, Dict, Optional
from pydantic import BaseModel, Field, ValidationError

"""
Request (client → your server):
{ "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {} }
(params may carry a cursor for pagination — ignore it for your handful of tools.)

Response (your server → client):
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "search_history",
        "title": "Search History",
        "description": "Search the user's shell command history for past commands...",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": { "type": "string" },
            "limit": { "type": "integer" }
          },
          "required": ["query"]
        }
      }
    ]
  }
}

So a tool object = name, description, inputSchema (+ optional title). That inputSchema is exactly what your Pydantic model_json_schema() spits out — you're just wrapping each one in this envelope.

Since you'll need its partner immediately, tools/call:

// request
{ "jsonrpc":"2.0","id":2,"method":"tools/call",
  "params": { "name":"search_history", "arguments": { "query":"ffmpeg","limit":10 } } }

// response
{ "jsonrpc":"2.0","id":2,
  "result": { "content": [ { "type":"text","text":"<your results>" } ], "isError": false } }


// Error
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "tools/lst is not a recognized method"
  }
}


┌────────┬───────────────────────────────────────────────┐
│  code  │                    meaning                    │
├────────┼───────────────────────────────────────────────┤
│ -32700 │ Parse error (invalid JSON)                    │
├────────┼───────────────────────────────────────────────┤
│ -32600 │ Invalid Request (not a valid JSON-RPC object) │
├────────┼───────────────────────────────────────────────┤
│ -32601 │ Method not found ← your initialize bug        │
├────────┼───────────────────────────────────────────────┤
│ -32602 │ Invalid params (bad/missing arguments)        │
├────────┼───────────────────────────────────────────────┤
│ -32603 │ Internal error                                │
└────────┴───────────────────────────────────────────────┘

"""

class Tool(BaseModel):
    name: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]

    def __init_subclass__(cls, name: str, label: str, description: str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = name
        cls.title = label
        cls.description = description

    @abstractmethod
    def execute(self) -> str: ...

class HistMeta(BaseModel):
    timestamp: int
    elapsed: int

class ZshHistoryCommand(BaseModel):
    command: str
    meta: HistMeta | None = None

    # Extended-history line: ": <start-ts>:<elapsed>;<command>".
    # Anything that doesn't match this exact shape is treated as a plain
    # command, so a plain/mixed/corrupt line can never crash the parse.
    _EXTENDED_RE: ClassVar = re.compile(r"^:\s*(\d+):(\d+);(.*)$", re.DOTALL)

    @classmethod
    def parse(cls, raw_line: str) -> "ZshHistoryCommand":
        line = raw_line.strip()

        match = cls._EXTENDED_RE.match(line)
        if match is None:
            return cls(command=line)

        raw_timestamp, raw_elapsed, command = match.groups()
        return cls(
            command=command,
            meta=HistMeta(
                timestamp=int(raw_timestamp),
                elapsed=int(raw_elapsed),
            ),
        )

history_path = Path.home() / ".zsh_history"

def read_zsh_history():
    with open(history_path, errors="replace") as f:
        contents = f.read()
        commands: list[ZshHistoryCommand] = list(
            map(
                ZshHistoryCommand.parse,
                contents.splitlines(),
            )
        )
        return commands
        

class SearchHistoryTool(Tool, name="search_history", label="Search History", description="Search the user's shell command history for past commands containing a query string. Use when the user is trying to recall or reconstruct a command they ran before (e.g. 'what was that ffmpeg command')."):
    query: str = Field(description="substring to match (or a regex if `regex` is true)")
    limit: int = Field(description="max results", default=20)
    regex: bool = Field(description="Treat `query` as a regular expression", default=False)

    def execute(self) -> str:
        commands = read_zsh_history()
        results: list[ZshHistoryCommand] = []

        pattern = re.compile(self.query) if self.regex else None
        query = self.query if not self.regex else None
        
        for cmd in reversed(commands):
            if pattern is not None:
                if pattern.search(cmd.command):
                    results.append(cmd)
            elif query is not None:
                if query in cmd.command:
                    results.append(cmd)

            if len(results) >= self.limit:
                break

        if len(results) == 0:
            return f"No search results for {self.query} were found!"

        def get_timestamp(cmd: ZshHistoryCommand) -> str:
            if cmd.meta is None:
                return ""

            time = datetime.fromtimestamp(cmd.meta.timestamp).strftime("%Y-%m-%d %H:%M:%S")

            return f"[{time}]"

        # print('Read', len(commands), 'commands!', file=sys.stderr, flush=True)
        return f"""Search results for {self.query} below:
---
{"\n".join(list([f"{(i + 1):>3}. {get_timestamp(cmd)} {cmd.command}" for i, cmd in enumerate(results)]))}
"""

TOOLS: list[type[Tool]] = [
    SearchHistoryTool
]

def tools_list():
    tools = []

    for tool in TOOLS:
        tools.append({
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.model_json_schema(),        
        })

    return tools

class InvalidArgumentsException(Exception):
    pass

def call_tool(name: str, arguments: Dict) -> str:
    for tool in TOOLS:
        if tool.name != name:
            continue

        try:
            instance = tool.model_validate(arguments)
        except ValidationError as e:
            raise InvalidArgumentsException(str(e))

        return instance.execute()

    raise InvalidArgumentsException(f"Unknown tool: {name}")

def invalid_json_error(data: Optional[str] = None):
    return {
        "code": -32700,
        "message": "Parse error (invalid JSON)",
        "data": data
    }

def invalid_params_error(data: Optional[str] = None):
    return {
        "code": -32602,
        "message": "Invalid params (bad/missing arguments)",
        "data": data
    }

def internal_error():
    return {
        "code": -32603,
        "message": "Internal error",
    }

def process_request(data: Dict) -> Dict | None:
    resp = {
        "jsonrpc": "2.0",
        "id": data["id"] if "id" in data else None,
    }

    if not "method" in data or data.get("jsonrpc", None) != "2.0":
        resp["error"] = invalid_json_error()
        return resp

    print("Received: ", data, file=sys.stderr, flush=True)

    if not "id" in data:
        return None

    match data:
        case { "method": "initialize" }:
            clientInfo = data["params"]["clientInfo"]
            print(f"{clientInfo['name']}@{clientInfo['version']} connected!", file=sys.stderr, flush=True)
            resp["result"] = {
                "protocolVersion": "2025-06-18",
                "capabilities": { "tools": {} },
                "serverInfo": { "name": "zsher", "version": "0.1.0" }
            }
            return resp
        case { "method": "tools/list" }:
            resp["result"] = { "tools": tools_list() }
            return resp
        case { "method": "tools/call" }:
            params = data.get("params")

            if not isinstance(params, dict) or not "name" in params:
                resp["error"] = invalid_params_error("Tool name not provided")
                return resp

            try:
                result = call_tool(params["name"], params.get("arguments", {}))

                resp["result"] = {
                    "content": [{ "type": "text", "text": result }],
                }
                return resp
            except InvalidArgumentsException as e:
                resp["error"] = invalid_params_error(str(e))
                return resp
            except Exception as e:
                print("Internal Error: ", e, file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
                resp["error"] = internal_error()
                return resp

    resp["error"] = {
        "code": -32601,
        "message": "Method not found",
        "data": f"{data['method']} is not a recognized method"
    }

    return resp

def main():
    for line in sys.stdin:
        line = line.rstrip("\n")
        data: Optional[Dict] = None
        try: 
            data = json.loads(line)
            assert data is not None
            resp = process_request(data)
            if resp:
                print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid request",
                },
            }
            print(json.dumps(error_resp), flush=True)
        except Exception as e:
            print("Unhandled errro: ", str(e), file=sys.stderr, flush=True)
            traceback.print_exc()
            error_resp = {
                "jsonrpc": "2.0",
                "id": data["id"] if data is not None and "id" in data else None,
                "error": internal_error(),
            }
            print(json.dumps(error_resp), flush=True)
            
        sys.stdout.flush()


main()
