import math

import pytest

from tf3companion import luadata


def test_parses_game_userdata_document():
    text = """function data()
return {
\t-- comment
	name = "Example Region",
\tcount = -3,
\tratio = 1.5e2,
\tflags = { true, false, },
\t["key with space"] = 0x10,
\t[2] = "two";
\tnested = { a = { }, b = { 1, 2, 3 } },
}
end
"""
    assert luadata.loads(text) == {
        "name": "Example Region",
        "count": -3,
        "ratio": 150.0,
        "flags": [True, False],
        "key with space": 16,
        2: "two",
        "nested": {"a": [], "b": [1, 2, 3]},
    }


def test_tables_with_keys_one_to_n_become_lists_in_order():
    assert luadata.loads("return { [2] = 'b', [1] = 'a', [3] = 'c' }") == ["a", "b", "c"]
    assert luadata.loads("return { [1] = 'a', [3] = 'c' }") == {1: "a", 3: "c"}


def test_decimal_escapes_are_utf8_bytes():
    # Non-ASCII text escaped byte by byte by the Lua serializer.
    assert luadata.loads(r'return "S\195\163o"') == "S\u00e3o"
    assert luadata.loads('return "S\\u{E3}o"') == "S\u00e3o"
    assert luadata.loads(r'return "a\"b\\c\n"') == 'a"b\\c\n'


def test_special_numbers():
    value = luadata.loads("return { math.huge, -math.huge, inf }")
    assert value[0] == math.inf and value[1] == -math.inf and value[2] == math.inf


def test_nil_values_are_dropped():
    assert luadata.loads("return { a = nil, b = 1 }") == {"b": 1}


def test_roundtrip_through_dumps():
    data = {"id": 3, "list": [1, 2.5, 'x"y', {"\u00e7": True}], "empty": [], "neg": -7}
    assert luadata.loads(luadata.dumps(data)) == data


@pytest.mark.parametrize("text", ["return { a = }", "return { 1, 2", "return foo", "return {} extra"])
def test_rejects_malformed_documents(text):
    with pytest.raises(luadata.LuaDataError):
        luadata.loads(text)


@pytest.mark.parametrize(
    "text",
    [
        "return os.execute('touch /tmp/unsafe')",
        "return {} os.execute('anything')",
        "return { [nil] = 1 }",
        "return { [{}] = 1 }",
        "return { [nan] = 1 }",
        "return { [true] = 1, [1] = 2 }",
        "return { a = 1, a = 2 }",
        r'return "\999"',
        r'return "\xzz"',
        r'return "\u{110000}"',
    ],
)
def test_rejects_executable_or_ambiguous_data(text):
    with pytest.raises(luadata.LuaDataError):
        luadata.loads(text)


def test_excessive_nesting_is_a_data_error():
    with pytest.raises(luadata.LuaDataError):
        luadata.loads("return " + "{" * 2000 + "}" * 2000)
