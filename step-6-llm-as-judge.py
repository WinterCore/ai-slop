from urllib.request import Request, urlopen
import json
import os
import pytest

from anthropic_api import (
    Message,
    MessagesRequest,
    MessagesResponse,
    TextBlock,
)

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")

MAX_TOKENS = 1_000

# TODO: replace with your judge rubric — the grading criteria + the exact
# output shape you want back (e.g. a strict {pass, reason} verdict).
SYSTEM = [TextBlock(text="You are a grader. TODO: define the rubric and the required output format.")]

def call_llm(messages: list[Message]) -> MessagesResponse:
    body = MessagesRequest(
        model="claude-haiku-4-5",
        max_tokens=MAX_TOKENS,
        messages=messages,
        system=SYSTEM,
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

class TestLlmAsJudge:
    # TODO: your eval set of {input, reference} cases for the fuzzy task.
    cases: list = []

    def test_run_eval_set(self):
        # TODO: for each case -> run the system under test -> have the judge
        # grade the output against the reference -> tally a pass-rate.
        pass
