"""
Writes an optimization result as an update of the start .clang-format file: only the options
that changed are edited or added, and the rest of the file (comments, key order, quoting,
alignment) stays as it is.

The file is read with ruamel.yaml in round-trip mode only to find where each value is; the
edits are made on the text, because dumping the round-trip data would still reformat it (e.g.
the aligned "Regex:           '...'" of IncludeCategories).
"""
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

_PLAIN_SCALAR = re.compile(r'^[A-Za-z_][A-Za-z0-9_.+-]*$')
_RESERVED_WORDS = {'true', 'false', 'null', '~', 'yes', 'no', 'on', 'off'}


def format_scalar(value: Any) -> str:
    """Formats a value as a YAML scalar that clang-format reads back as the same value."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    text = str(value)
    # Yes/No are plain in clang-format's own --dump-config output; quote other words that a
    # YAML reader could take for a boolean or null, and anything that is not a simple word
    if _PLAIN_SCALAR.match(text) and (text in ('Yes', 'No') or text.lower() not in _RESERVED_WORDS):
        return text
    return "'" + text.replace("'", "''") + "'"


def _scalar_end(line: str, start: int) -> int:
    """Returns the end column of the scalar that starts at `start` in `line`."""
    if line[start:start + 1] == "'":
        position = start + 1
        while position < len(line):
            if line[position] == "'":
                if line[position + 1:position + 2] == "'":
                    position += 2
                    continue
                return position + 1
            position += 1
        return len(line)
    if line[start:start + 1] == '"':
        position = start + 1
        while position < len(line):
            if line[position] == '\\':
                position += 2
                continue
            if line[position] == '"':
                return position + 1
            position += 1
        return len(line)
    comment = re.search(r'\s#', line[start:])
    end = start + comment.start() if comment else len(line)
    return len(line[:end].rstrip())


def changed_options(start_options: Dict[str, Any], result_options: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    """Returns {option path: (start value, result value)} for the options whose value changed."""
    changes = {}
    for path, info in result_options.items():
        start_value = start_options[path]['value'] if path in start_options else None
        if path not in start_options or info['value'] != start_value:
            changes[path] = (start_value, info['value'])
    return changes


def update_config_text(text: str, changes: Dict[str, Tuple[Any, Any]], result_options: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Applies the changed options to the text of a .clang-format file.

    An option that the file sets is edited in place. An option that it does not set is added at
    the end of its parent block (BraceWrapping, KeepEmptyLines, ...) or, without one, at the end
    of the file. A parent given as a scalar shorthand (e.g. "AlignConsecutiveAssignments: None")
    becomes a block with all its sub-options from the result.

    Args:
        text (str): The start .clang-format file.
        changes (dict): {option path: (start value, result value)} from changed_options().
        result_options (dict): The flat result, for all sub-options of a replaced shorthand.

    Returns:
        tuple: (new text, problems). The problems list the changes that could not be written
               (e.g. a flow-style parent map); when it is not empty, the text is not usable.
    """
    if not changes:
        return text, []
    try:
        data = YAML().load(text)
    except YAMLError as e:
        # E.g. per-language sections separated by "---": the update supports one document only
        reason = str(e).splitlines()[0] if str(e) else type(e).__name__
        return text, [f"the start config cannot be read as one YAML document ({reason})"]
    if not isinstance(data, CommentedMap):
        return text, ["the start config is not a YAML mapping"]

    lines = text.split('\n')
    replacements = {} # line index -> (start column, end column, new text)
    insertions = {} # line index -> lines to insert after it
    appended = [] # lines to add at the end of the file
    problems = []

    # Indentation of new sub-options: that of the first block map of the file, or 2
    indent = 2
    for key in data:
        child_map = data[key]
        if isinstance(child_map, CommentedMap) and len(child_map) and not child_map.fa.flow_style():
            indent = child_map.lc.key(next(iter(child_map)))[1]
            break

    def replace_value(node, key, value):
        line_index, column = node.lc.value(key)
        end = _scalar_end(lines[line_index], column)
        replacements[line_index] = (column, end, format_scalar(value))

    groups: Dict[str, List[Tuple[List[str], Any]]] = {}
    for path, (_, value) in changes.items():
        parts = path.split('.')
        if len(parts) > 2:
            problems.append(f"{path}: options nested deeper than two levels are not supported")
            continue
        groups.setdefault(parts[0], []).append((parts[1:], value))

    for top, items in groups.items():
        if items[0][0] == []: # a top-level option
            value = items[0][1]
            if top not in data:
                appended.append(f"{top}: {format_scalar(value)}")
            elif isinstance(data[top], (dict, list)):
                problems.append(f"{top}: the start config has a map or list where the result has a scalar")
            else:
                replace_value(data, top, value)
            continue
        if top not in data:
            appended.append(f"{top}:")
            appended.extend(f"{' ' * indent}{child[0]}: {format_scalar(value)}" for child, value in items)
        elif isinstance(data[top], CommentedMap):
            node = data[top]
            if node.fa.flow_style():
                problems.append(f"{top}: flow-style maps ({{...}}) are not supported, write it as a block")
                continue
            child_indent = node.lc.key(next(iter(node)))[1] if len(node) else indent
            last_line = max(node.lc.key(key)[0] for key in node) if len(node) else data.lc.key(top)[0]
            for child, value in items:
                if child[0] in node:
                    replace_value(node, child[0], value)
                else:
                    insertions.setdefault(last_line, []).append(f"{' ' * child_indent}{child[0]}: {format_scalar(value)}")
        elif isinstance(data[top], list):
            problems.append(f"{top}: the start config has a list where the result has sub-options")
        else:
            # A scalar shorthand: the value is removed ("Key:", a comment after it stays) and the
            # whole struct is written from the result below it
            line_index, column = data.lc.value(top)
            replacements[line_index] = (column, _scalar_end(lines[line_index], column), '')
            sub_options = [(path.split('.', 1)[1], info['value']) for path, info in result_options.items() if path.startswith(top + '.')]
            insertions.setdefault(line_index, []).extend(f"{' ' * indent}{child}: {format_scalar(value)}" for child, value in sub_options)

    if problems:
        return text, problems

    for line_index, (start, end, new_value) in replacements.items():
        line = lines[line_index]
        lines[line_index] = line[:start] + new_value + line[end:]
        if not new_value and '#' not in lines[line_index]:
            lines[line_index] = lines[line_index].rstrip() # "Key: " of a removed shorthand
    for line_index in sorted(insertions, reverse=True):
        lines[line_index + 1:line_index + 1] = insertions[line_index]
    if appended:
        # Keep the final newline after the appended lines
        while lines and lines[-1] == '':
            lines.pop()
        lines.extend(appended)
        lines.append('')
    return '\n'.join(lines), []


def dump_config(clang_format: str, text: str) -> str:
    """Returns 'clang-format --dump-config' for a configuration text."""
    with tempfile.TemporaryDirectory() as directory:
        style_file = os.path.join(directory, 'style.yml')
        with open(style_file, 'w') as f:
            f.write(text)
        result = subprocess.run([clang_format, f"--style=file:{style_file}", "--dump-config"],
                                capture_output=True, text=True, check=True)
        return result.stdout
