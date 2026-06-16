from typing import Annotated, List
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import traceback
import json
import os
from pydantic import BaseModel, Field, ValidationError
from numbers import Number

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")


def call_llm(messages: List):
    reqbody = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1000,
        "messages": messages,
        "tool_choice": { "type": "auto" },
        "stop_sequences": ["HALT"],
        "system": [{
            "type": "text",
            "text": "When a tool use returns an error, surface the error directly to the user, don't try to guess what went wrong and tell the user something else. Literally display the error string literal as returned by the service"
        }],
        "tools":  [{
            "name": WeatherTool.__name__,
            "description": "Get the current weather for a city",
            "input_schema": WeatherTool.model_json_schema(),
        },
        {
            "name": AddTool.__name__,
            "description": "Adds two numbers",
            "input_schema": AddTool.model_json_schema(),
        },
        {
            "name": GetUserCityTool.__name__,
            "description": "Get the current city (location) of the user",
            "input_schema": GetUserCityTool.model_json_schema(),
        }]
    }

    req = Request(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        data=json.dumps(reqbody).encode(),
        headers={
            "X-Api-Key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
    )

    resp = urlopen(req)
    data = json.loads(resp.read())

    return data

def print_content(content):
    for item in content:
        match item:
            case {"type": "text", "text": t}:
                print('Assistant: ', t)
            case _:
                pass

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
    AddTool
]

def process_tool_use(content):
    num_processed = 0

    tool_use_content = []
    for item in content:
        if item["type"] != "tool_use":
            continue
    
        try:
            tool = next((x for x in tools if x.__name__ == item["name"]), None)

            if tool is None:
                raise Exception(f"Tool {item["name"]} doesn't exist")

            tool_instance = tool.model_validate(item["input"])
            num_processed += 1
            
            print(f"Assistant(tool_use): {item["name"]}({item["input"]})")
            tool_use_content.append({
                "type": "tool_result",
                "tool_use_id": item["id"],
                "content": str(tool_instance.execute()),
            })

        except Exception as err:
            traceback.print_exc()
            tool_use_content.append({
                "is_error": True,
                "type": "tool_result",
                "tool_use_id": item["id"],
                "content": str(err)
            })

    messages.append({ "role": "user", "content": tool_use_content })

    return num_processed

def send_message(message: str):
    global messages

    depth = 0

    try:
        print('User: ', message)
        messages.append({
            "role": "user",
            "content": [{
                "type": "text",
                "text": message
            }],
        })

        data = None

        # Loop until end_turn
        while True:
            if depth > 10:
                print('Maximum depth exceeded!')
                break

            if data is not None:
                tokens = data['usage']['input_tokens'] + data['usage']['output_tokens']

                if tokens >= 1000:
                    print('You hit the conversation token limit!')
                    break

            data = call_llm(messages)
            print_content(data["content"])
            messages.append({
                "role": "assistant",
                "content": data["content"],
            })

            depth += 1

            match data:
                case { "stop_reason": "tool_use" }:
                    process_tool_use(data["content"])
                case { "stop_reason": "end_turn" }:
                    break
                case { "stop_reason": "stop_sequence" }:
                    break
                case { "stop_reason": "refusal" }:
                    print('We could not process your previous request due to safety rules.')
                    break
                case { "stop_reason": "max_tokens" }:
                    # Abort if there's an incomplete tool_use
                    if any(x["type"] == "tool_use" for x in data["content"]):
                        print('Incomplete tool_use returned by model, aborting...')
                        break

                    print('Hit max tokens, trying to continue...')
                case { "stop_reason": "pause_turn" }:
                    pass
                case _:
                    print('Unknown data format')
                    break
            
            # Halt if there's no content
            if len(data["content"]) == 0:
                print('Received empty content from model, stopping...')
                break


    except HTTPError as e:
        body = e.read()
        print(e.code, body.decode())
        print('MESSAGES------------------------')
        print(messages)

    print('\n')

messages: List = []

send_message("Hello, what's the weather like here? can you add 3 degrees to whatever you get")



print('MESSAGES------------------------')
print(messages)

