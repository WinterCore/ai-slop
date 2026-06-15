from typing import List
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import traceback
import json
import os

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")


def call_llm(messages: List):
    reqbody = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 500,
        "messages": messages,
        "tool_choice": { "type": "auto" },
        "system": [{
            "type": "text",
            "text": "When a tool use returns an error, surface the error directly to the user, don't try to guess what went wrong and tell the user something else. Literally display the error string literal as returned by the service"
        }],
        "tools":  [{
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "input_schema": {
              "type": "object",
              "properties": {
                "city": {
                  "type": "string",
                  "description": "The city to get the weather for, e.g. Moscow"
                }
              },
              "required": ["city"]
            }
        },
        {
            "name": "add",
            "description": "Adds two numbers",
            "input_schema": {
              "type": "object",
              "properties": {
                "a": {
                  "type": "number",
                  "description": "The first operand"
                },
                "b": {
                  "type": "number",
                  "description": "The second operand"
                }
              },
              "required": ["a", "b"]
            }
        },
        {
            "name": "get_user_city",
            "description": "Get the current city (location) of the user",
            "input_schema": { "type": "object", "properties": {} },
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

def get_weather(city):
    raise Exception("The server melted")
    return "99°C, ARMAGEDDON"

def add(a, b):
    return a + b

def get_user_city():
    return "The sun"

def process_tool_use(content):
    num_processed = 0

    tool_use_content = []
    for item in content:
        if item["type"] != "tool_use":
            continue
    
        try:
            if item["name"] == "get_weather":
                print('Assistant(tool_use): get_weather(', item["input"]["city"], ')')
                tool_use_content.append({
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    "content": get_weather(item["input"]["city"])
                })
                num_processed += 1

            if item["name"] == "get_user_city":
                print('Assistant(tool_use): get_user_city()')
                tool_use_content.append({
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    "content": get_user_city()
                })
                num_processed += 1

            if item["name"] == "add":
                print('Assistant(tool_use): add(', item["input"]["a"], ',', item["input"]["b"], ')')
                tool_use_content.append({
                    "type": "tool_result",
                    "tool_use_id": item["id"],
                    "content": str(add(item["input"]["a"], item["input"]["b"]))
                })
                num_processed += 1
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
              
def agent_loop(data):
    if data["stop_reason"] == "tool_use":
        num_processed = process_tool_use(data["content"])

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

        # Loop until end_turn
        while True:
            if depth > 5:
                print('Maximum depth exceeded!')
                break

            data = call_llm(messages)
            print_content(data["content"])
            messages.append({
                "role": "assistant",
                "content": data["content"],
            })

            if data["stop_reason"] != "tool_use":
                break;

            agent_loop(data)
            depth += 1
    except HTTPError as e:
        body = e.read()
        print(e.code, body.decode())
        print('MESSAGES------------------------')
        print(messages)

    print('\n')

messages: List = []

send_message("Hello")
send_message("What's the temperature like today? Add 50 to the temperature")



print('MESSAGES------------------------')
print(messages)
