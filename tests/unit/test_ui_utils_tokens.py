# ABOUTME: Unit tests for _extract_token_fragments, the pure chunk-content parser.
# ABOUTME: Covers string content, list-of-str, blocks with .text, dict blocks, and empties.

from dataclasses import dataclass

from autobots_devtools_shared_lib.dynagent.ui.ui_utils import _extract_token_fragments


@dataclass
class _Chunk:
    content: object


@dataclass
class _TextBlock:
    text: str


def test_string_content_returns_single_fragment():
    assert _extract_token_fragments(_Chunk(content="hello")) == ["hello"]


def test_list_of_strings_returns_each():
    assert _extract_token_fragments(_Chunk(content=["a", "b"])) == ["a", "b"]


def test_list_of_text_blocks_reads_dot_text():
    assert _extract_token_fragments(_Chunk(content=[_TextBlock(text="x")])) == ["x"]


def test_list_of_dict_blocks_reads_text_key():
    assert _extract_token_fragments(_Chunk(content=[{"text": "y"}, {"type": "other"}])) == ["y"]


def test_none_chunk_returns_empty():
    assert _extract_token_fragments(None) == []


def test_empty_string_content_returns_empty():
    assert _extract_token_fragments(_Chunk(content="")) == []


def test_chunk_without_content_attr_returns_empty():
    assert _extract_token_fragments(object()) == []
