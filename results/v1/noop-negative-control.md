# Agent Sandbox Eval Report

- Trajectory: `results/v1/noop-negative-control.jsonl`
- Agent: `noop`
- Total tasks: 25
- Passed tasks: 0
- Pass rate: 0.0%
- Average score: 0.00
- Tool calls: 0
- Average tool calls per task: 0.0
- Average runtime per task: 525ms
- Timeout rate: 0.0%
- Verification rate: 0.0%
- Task/grader bug count: 0
- Model calls: 0
- Input tokens: 0
- Output tokens: 0
- Estimated model cost: $0.000000
- Model cost coverage: 0.0%
- Top failure: `no_progress`

## Failure Modes

- `no_progress`: 25

## Tool Use


## Tasks

- `read-state-001`: FAIL no_progress
- `reconcile-state-001`: FAIL no_progress
- `update-status-001`: FAIL no_progress
- `fix-cli-args-001`: FAIL no_progress
- `fix-date-format-001`: FAIL no_progress
- `fix-dedupe-001`: FAIL no_progress
- `fix-env-parser-001`: FAIL no_progress
- `fix-parser-001`: FAIL no_progress
- `fix-python-function-001`: FAIL no_progress
- `extract-ini-001`: FAIL no_progress
- `extract-log-metric-001`: FAIL no_progress
- `fix-config-001`: FAIL no_progress
- `fix-permissions-001`: FAIL no_progress
- `fix-script-001`: FAIL no_progress
- `json-summary-001`: FAIL no_progress
- `locate-file-001`: FAIL no_progress
- `normalize-json-001`: FAIL no_progress
- `pass-command-001`: FAIL no_progress
- `python-utility-001`: FAIL no_progress
- `replace-token-001`: FAIL no_progress
- `reverse-lines-001`: FAIL no_progress
- `sort-list-001`: FAIL no_progress
- `transform-csv-001`: FAIL no_progress
- `unique-values-001`: FAIL no_progress
- `word-count-001`: FAIL no_progress

## Failure Evidence

### `read-state-001`
- Success command: python -c "import json; data=json.load(open('state.json')); assert data['owner'] == 'ops' and data['reviewed'] is True"
- Expected exit code: 0
- Actual exit code: 1
- stderr: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; data=json.load(open('state.json')); assert data['owner'] == 'ops' and data['reviewed'] is True
                                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `reconcile-state-001`
- Success command: python -c "import json; assert json.load(open('state.json'))['file_status'] == 'done'"
- Expected exit code: 0
- Actual exit code: 1
- stderr: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; assert json.load(open('state.json'))['file_status'] == 'done'
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `update-status-001`
- Required JSON file: state.json
- Required JSON fields: status
- Actual exit code: 1
- stdout: [{"actual": "todo", "expected": "done", "field": "status"}]
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-cli-args-001`
- Success command: python cli.py Alice | grep -q '^Hello, Alice$'
- Expected exit code: 0
- Actual exit code: 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-date-format-001`
- Success command: python -m unittest -q
- Expected exit code: 0
- Actual exit code: 1
- stderr: ======================================================================
FAIL: test_iso_date (test_formatter.FormatterTest.test_iso_date)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/test_formatter.py", line 9, in test_iso_date
    self.assertEqual(format_date(date(2026, 5, 26)), "2026-05-26")
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '05/26/2026' != '2026-05-26'
- 05/26/2026
+
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-dedupe-001`
- Success command: python -m unittest -q
- Expected exit code: 0
- Actual exit code: 1
- stderr: ======================================================================
FAIL: test_preserves_first_seen_order (test_dedupe.DedupeTest.test_preserves_first_seen_order)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/test_dedupe.py", line 8, in test_preserves_first_seen_order
    self.assertEqual(unique(["b", "a", "b", "c", "a"]), ["b", "a", "c"])
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Ass
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-env-parser-001`
- Success command: python -m unittest -q
- Expected exit code: 0
- Actual exit code: 1
- stderr: ======================================================================
ERROR: test_ignores_comments_and_blanks (test_env_parser.EnvParserTest.test_ignores_comments_and_blanks)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/test_env_parser.py", line 9, in test_ignores_comments_and_blanks
    self.assertEqual(parse_env(lines), {"API_KEY": "abc", "MODE": "prod"})
                     ~~~~~~~~~^^^^^^^
  File "/workspace/en
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-parser-001`
- Success command: python -m unittest -q
- Expected exit code: 0
- Actual exit code: 1
- stderr: ======================================================================
ERROR: test_parse_line (test_parser.ParserTest.test_parse_line)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/test_parser.py", line 8, in test_parse_line
    self.assertEqual(parse_line("mode = prod"), ("mode", "prod"))
                     ~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/workspace/parser.py", line 2, in parse_line
    key, value = line.split(":
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-python-function-001`
- Success command: python -m unittest -q
- Expected exit code: 0
- Actual exit code: 1
- stderr: ======================================================================
FAIL: test_adds_numbers (test_calculator.CalculatorTest.test_adds_numbers)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspace/test_calculator.py", line 8, in test_adds_numbers
    self.assertEqual(add(20, 22), 42)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
AssertionError: -2 != 42

----------------------------------------------------------------------
Ran 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `extract-ini-001`
- Success command: grep -q '^port=8080$' result.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: result.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `extract-log-metric-001`
- Success command: grep -q '^errors=3$' metrics.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: metrics.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `fix-config-001`
- Success command: grep -q '^mode=prod$' app.conf
- Expected exit code: 0
- Actual exit code: 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-permissions-001`
- Success command: ./run.sh | grep -q '^ok$'
- Expected exit code: 0
- Actual exit code: 1
- stderr: sh: 1: ./run.sh: Permission denied
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `fix-script-001`
- Success command: sh run.sh | grep -q '^ready$'
- Expected exit code: 0
- Actual exit code: 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `json-summary-001`
- Success command: grep -q '^active=2$' summary.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: summary.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `locate-file-001`
- Success command: grep -q '^./notes/alpha.txt$' answer.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: answer.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `normalize-json-001`
- Success command: python -c "import json; assert open('normalized.json').read() == open('expected.json').read() and json.load(open('normalized.json')) == {'a': 1, 'items': [2, 1], 'z': 3}"
- Expected exit code: 0
- Actual exit code: 1
- stderr: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import json; assert open('normalized.json').read() == open('expected.json').read() and json.load(open('normalized.json')) == {'a': 1, 'items': [2, 1], 'z': 3}
                        ~~~~^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'normalized.json'
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `pass-command-001`
- Success command: test -f answer.txt && grep -q ready answer.txt
- Expected exit code: 0
- Actual exit code: 1
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `python-utility-001`
- Success command: python slugify.py "Hello World!" | grep -q '^hello-world$'
- Expected exit code: 0
- Actual exit code: 1
- stderr: python: can't open file '/workspace/slugify.py': [Errno 2] No such file or directory
- Agent tool calls: 0
- Final grader exit code: 1
- Agent made no tool calls before grading.

### `replace-token-001`
- Success command: grep -q '^Project: Agent Sandbox Eval$' output.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: output.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `reverse-lines-001`
- Success command: cmp -s reversed.txt expected.txt
- Expected exit code: 0
- Actual exit code: 2
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `sort-list-001`
- Success command: cmp -s sorted.txt expected.txt
- Expected exit code: 0
- Actual exit code: 2
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `transform-csv-001`
- Success command: grep -q '^total=42$' total.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: total.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `unique-values-001`
- Success command: grep -q '^unique=4$' unique.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: unique.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.

### `word-count-001`
- Success command: grep -q '^words=10$' count.txt
- Expected exit code: 0
- Actual exit code: 2
- stderr: grep: count.txt: No such file or directory
- Agent tool calls: 0
- Final grader exit code: 2
- Agent made no tool calls before grading.
