"""Guards against a class of corruption that has happened twice: a regex written as "\b" inside a normal Python string
becomes a backspace character, and the pattern silently stops matching word boundaries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_source_file_contains_a_stray_control_character():
    bad = []
    for path in [*ROOT.joinpath("app").rglob("*.py"), *ROOT.joinpath("pipeline").rglob("*.py"), *ROOT.joinpath("tests").rglob("*.py")]:
        text = path.read_text(encoding="utf-8")
        for index, char in enumerate(text):
            if ord(char) < 32 and char not in "\n\t\r":
                bad.append(f"{path.relative_to(ROOT)} line {text.count(chr(10), 0, index) + 1}: {ord(char):#x}")
    assert not bad, "control characters in source (a \b typed in a non-raw string?): " + "; ".join(bad)
