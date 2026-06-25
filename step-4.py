from typing import Annotated
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import traceback
import json
import os
from pydantic import BaseModel, Field

from anthropic_api import (
    ContentBlock,
    Message,
    MessagesRequest,
    MessagesResponse,
    TextBlock,
    Tool,
    ToolChoiceAuto,
    ToolResultBlock,
    ToolUseBlock,
)

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")

MAX_TOKENS = 1_000
TOKEN_LIMIT = 5_000
MARGIN_TOKENS = 1_000
CONTEXT_REDUCTION_MESSAGE_KEEP_COUNT = 3
window = TOKEN_LIMIT - MAX_TOKENS - MARGIN_TOKENS

def call_llm(messages: list[Message]) -> MessagesResponse:
    body = MessagesRequest(
        model="claude-haiku-4-5",
        max_tokens=MAX_TOKENS,
        messages=messages,
        tool_choice=ToolChoiceAuto(),
        stop_sequences=["HALT"],
        system=SYSTEM,
        tools=TOOLS,
    )

    req = Request(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        # exclude_none drops unset optionals so we never send e.g. temperature: null
        data=json.dumps(body.model_dump(exclude_none=True)).encode(),
        headers={
            "X-Api-Key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
    )

    resp = urlopen(req)
    return MessagesResponse.model_validate(json.loads(resp.read()))

def count_tokens(messages: list[Message]) -> int:
    body = {
        "model": "claude-haiku-4-5",
        "messages": [m.model_dump(exclude_none=True) for m in messages],
        "system": [s.model_dump() for s in SYSTEM],
        "tools": [t.model_dump(exclude_none=True) for t in TOOLS],
    }

    req = Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "X-Api-Key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )

    resp = urlopen(req)
    data = json.loads(resp.read())
    return data["input_tokens"]

def summarize_history(messages: list[Message]) -> str:
    history = json.dumps([m.model_dump(exclude_none=True) for m in messages])

    body = MessagesRequest(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=[TextBlock(text="Summarize the following conversation history in a few short paragraphs and STAY UNDER 35 WORDS. Preserve names, decisions, tool calls and their results, and any open tasks")],
        messages=[Message(role="user", content=history)],
    )

    req = Request(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        data=json.dumps(body.model_dump(exclude_none=True)).encode(),
        headers={
            "X-Api-Key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )

    resp = urlopen(req)
    data = MessagesResponse.model_validate(json.loads(resp.read()))
    return "".join(b.text for b in data.content if isinstance(b, TextBlock))

def print_content(content: list[ContentBlock]):
    for item in content:
        match item:
            case TextBlock(text=t):
                print('Assistant: ', t)
            case _:
                pass

class ChickenLocationTool(BaseModel):
    def execute(self):
        return "Across the street"

class WeatherTool(BaseModel):
    city: Annotated[str, Field(min_length=1)]

    def execute(self):
        return "99°C, ARMAGEDDON"

class AddTool(BaseModel):
    a: int | float
    b: int | float

    def execute(self):
        return self.a + self.b

class GetUserCityTool(BaseModel):
    pass

    def execute(self):
        return "The sun"

tools = [
    GetUserCityTool,
    WeatherTool,
    AddTool,
    ChickenLocationTool
]

SYSTEM = [TextBlock(text="When a tool use returns an error, surface the error directly to the user, don't try to guess what went wrong and tell the user something else. Literally display the error string literal as returned by the service. Always give long descriptions and long responses in every answer to my questions, I'm an avid reader and like to read long walls of text")]

TOOLS = [
    Tool(name=ChickenLocationTool.__name__, description="Get the location of the chicken", input_schema=ChickenLocationTool.model_json_schema()),
    Tool(name=WeatherTool.__name__, description="Get the current weather for a city", input_schema=WeatherTool.model_json_schema()),
    Tool(name=AddTool.__name__, description="Adds two numbers", input_schema=AddTool.model_json_schema()),
    Tool(name=GetUserCityTool.__name__, description="Get the current city (location) of the user", input_schema=GetUserCityTool.model_json_schema()),
]

def process_tool_use(content: list[ContentBlock]):
    num_processed = 0

    tool_use_content: list[ContentBlock] = []
    for item in content:
        if not isinstance(item, ToolUseBlock):
            continue

        try:
            tool = next((x for x in tools if x.__name__ == item.name), None)

            if tool is None:
                raise Exception(f"Tool {item.name} doesn't exist")

            tool_instance = tool.model_validate(item.input)
            num_processed += 1

            print(f"Assistant(tool_use): {item.name}({item.input})")
            tool_use_content.append(ToolResultBlock(
                tool_use_id=item.id,
                content=str(tool_instance.execute()),
            ))

        except Exception as err:
            traceback.print_exc()
            tool_use_content.append(ToolResultBlock(
                tool_use_id=item.id,
                content=str(err),
                is_error=True,
            ))

    messages.append(Message(role="user", content=tool_use_content))

    return num_processed

def reduce_context(messages: list[Message]) -> list[Message]:
    if len(messages) <= CONTEXT_REDUCTION_MESSAGE_KEEP_COUNT:
         return [Message(role='user', content=summarize_history(messages))]

    messages_count = len(messages)
    split_index = messages_count - CONTEXT_REDUCTION_MESSAGE_KEEP_COUNT - 1

    while split_index < messages_count and (any(not isinstance(x, str) and x.type == 'tool_result' for x in messages[split_index].content)):
        split_index += 1

    summarized_message = Message(role='user', content=[
        TextBlock(text=summarize_history(messages[:split_index]))
    ])
    
    if split_index < messages_count and messages[split_index].role == 'user':
        content = messages[split_index].content
        blocks: list[ContentBlock] = [TextBlock(text=content)] if isinstance(content, str) else content

        assert not isinstance(summarized_message.content, str)

        summarized_message.content.extend(blocks)
        split_index += 1
        
    new_messages = [
        summarized_message,
        *messages[split_index:]
    ]

    new_tokens = count_tokens(new_messages)
    print('summarized tokens', new_tokens, window)
    if new_tokens >= window:
        new_messages = [Message(role='user', content=summarize_history(new_messages))]

    return new_messages;
    

def send_message(message: str):
    global messages

    depth = 0

    try:
        print('User: ', message)
        messages.append(Message(role="user", content=[TextBlock(text=message)]))

        # Loop until end_turn
        while True:
            if depth > 10:
                print('Maximum depth exceeded!')
                break

            data = call_llm(messages)

            tokens = data.usage.input_tokens + data.usage.output_tokens
            print('Tokens: ', data.usage.input_tokens + data.usage.output_tokens, '\nWindow:', window)

            if tokens >= window:
                print('compacting...')
                messages = reduce_context(messages)

            messages.append(Message(role="assistant", content=data.content))

            depth += 1

            match data.stop_reason:
                case "tool_use":
                    process_tool_use(data.content)
                case "end_turn":
                    print_content(data.content)
                    break
                case "stop_sequence":
                    break
                case "refusal":
                    print('We could not process your previous request due to safety rules.')
                    break
                case "max_tokens":
                    # Abort if there's an incomplete tool_use
                    if any(isinstance(x, ToolUseBlock) for x in data.content):
                        print('Incomplete tool_use returned by model, aborting...')
                        break

                    print('Hit max tokens, trying to continue...')
                case "pause_turn":
                    pass
                case _:
                    print('Unknown stop_reason')
                    break

            # Halt if there's no content
            if len(data.content) == 0:
                print('Received empty content from model, stopping...')
                break


    except HTTPError as e:
        body = e.read()
        print(e.code, body.decode())
        print('MESSAGES------------------------')
        print(messages)

    print('\n')

messages: list[Message] = []

send_message("Hello, what's the weather like here? can you add 3 degrees to whatever you get")

send_message("To pee or not to pee?")

send_message("Can you give me a lorem ipsum snippet that's 2000 characters long (soft limit)")

send_message("Why did the chicken cross the street?")

send_message("Where does the chicken live?")

send_message("Why would she live there?")

# print('MESSAGES------------------------')
# print(messages)
