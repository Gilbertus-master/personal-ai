import json
import tempfile

from app.ingestion.chatgpt.parser import (
    parse_chatgpt_export_file,
    _extract_text_parts,
)


def _make_export(conversations: list[dict]) -> str:
    return json.dumps(conversations, ensure_ascii=False)


def test_extract_text_parts():
    message = {"content": {"parts": ["Hello", "World"]}}
    assert _extract_text_parts(message) == "Hello\nWorld"


def test_extract_text_parts_empty():
    message = {"content": {"parts": []}}
    assert _extract_text_parts(message) == ""


def test_extract_text_parts_non_string():
    message = {"content": {"parts": ["Hello", {"type": "image"}, "World"]}}
    assert _extract_text_parts(message) == "Hello\nWorld"


def test_parse_single_conversation():
    export = [
        {
            "conversation_id": "conv-1",
            "title": "Test Chat",
            "create_time": 1710000000.0,
            "mapping": {
                "node-1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Cześć"]},
                        "create_time": 1710000001.0,
                    }
                },
                "node-2": {
                    "message": {
                        "author": {"role": "assistant"},
                        "content": {"parts": ["Hej!"]},
                        "create_time": 1710000002.0,
                    }
                },
            },
        }
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(export))
        f.flush()
        convs = parse_chatgpt_export_file(f.name)

    assert len(convs) == 1
    assert convs[0].title == "Test Chat"
    assert convs[0].conversation_id == "conv-1"
    assert len(convs[0].messages) == 2
    assert convs[0].messages[0].author == "user"
    assert convs[0].messages[0].text == "Cześć"


def test_skip_system_messages():
    export = [
        {
            "conversation_id": "conv-1",
            "title": "Test",
            "create_time": 1710000000.0,
            "mapping": {
                "node-1": {
                    "message": {
                        "author": {"role": "system"},
                        "content": {"parts": ["System prompt"]},
                        "create_time": 1710000000.0,
                    }
                },
                "node-2": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello"]},
                        "create_time": 1710000001.0,
                    }
                },
            },
        }
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(export))
        f.flush()
        convs = parse_chatgpt_export_file(f.name)

    assert len(convs[0].messages) == 1
    assert convs[0].messages[0].author == "user"


def test_empty_conversations():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write("[]")
        f.flush()
        convs = parse_chatgpt_export_file(f.name)

    assert convs == []
