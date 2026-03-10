# Code Analysis Instructions — TinyDB

These are the rules for reviewing Pull Requests in this repository. For each PR, analyze only the changed lines (diff). Apply every rule below. Report issues grouped by severity: **High**, **Medium**, **Low**. If no issues are found, say so.

---

## 1. Naming & Intent

### 1.1 Descriptive Naming (Severity: Low)

Flag any variable, parameter, or local function name that is too generic to communicate intent. Generic names provide no information about the value they hold.

**Flag these names (and similar):**
- `data`, `info`, `result`, `obj`, `item`, `value` when used as a local variable for a specific domain object
- `manager` when referring to a specific type (e.g., a table instance)
- `handle` when it refers to a concrete resource (e.g., a file handle)
- Any single-letter variable outside of loop counters or math expressions

**Suggested fix:** Replace with a name that describes what the variable holds or represents. Examples:
- `data` → `raw_doc`, `document_data`, `record`
- `info` → `doc_ids`, `insert_results`
- `manager` → `table_instance`, `table_ref`
- `handle` → `file_handle`, `storage_file`

**Do NOT flag:**
- Names that clearly communicate their content: `raw_doc`, `document_by_id`, `next_doc_id`, `table_instance`, `table_data`, `repr_parts`
- Standard Python idioms: `_` for ignored values, `e` in `except ... as e`

---

### 1.2 Boolean Conventions (Severity: Low)

Boolean variables must sound like a yes/no question. A reader should be able to say "if [name]..." and have it read naturally.

**Flag booleans that do not follow this pattern:**
- `found`, `flag`, `done`, `ready`, `status`, `check` — these read as nouns or adjectives, not questions

**Suggested fix:** Rename with a `is_`, `has_`, `can_`, `should_`, or `was_` prefix:
- `found` → `is_found` or `has_match`
- `flag` → `has_value` or `is_cached`

**Do NOT flag:**
- `is_cached`, `is_found`, `has_value`, `can_write` — these already follow the convention

---

### 1.3 Magic Values (Severity: Low)

Flag unexplained numeric or string literals used directly in logic (comparisons, conditions, arithmetic). Literals that encode business rules or thresholds must be extracted to named constants.

**Flag when:**
- A numeric literal other than `0` or `1` appears in a condition or comparison (e.g., `self.length > 10`, `>= 1000`)
- A string literal is used directly in a conditional check (e.g., `if access_mode != 'r+'`) without explanation

**Suggested fix:** Extract to an `UPPER_CASE` module or class-level constant:
```python
# Bad
if self.length > 10:

# Good
MAX_CACHE_SIZE = 10
if self.length > MAX_CACHE_SIZE:
```

**Do NOT flag:**
- Named constants used in comparisons (e.g., `self.WRITE_CACHE_SIZE`, `self.capacity`)
- `0` and `1` used as neutral reset/sentinel values when their meaning is obvious from context
- Named constants defined inline when their name is descriptive (e.g., `RESET_VALUE = 0`)

---

## 2. Architecture & Design

### 2.1 Single Responsibility (Severity: Medium)

Each function or method should do one thing. Flag functions that combine unrelated responsibilities.

**Flag when a function or nested function:**
- Parses or deserializes input **and** writes/updates a data structure (e.g., calling `json.loads` inside a table updater)
- Validates data **and** performs I/O in a single scope with no separation
- Does work that belongs to a different abstraction layer

**Suggested fix:** Split into two functions: one for parsing/validation, one for persistence.

**Do NOT flag:**
- Small helpers with a single, focused transformation (e.g., `copy_field`, `increment`)
- Functions that do one coherent operation even if it has multiple steps (e.g., iterate + filter + yield)

---

### 2.2 Leaky Abstractions (Severity: Medium)

Flag code that reaches through an abstraction boundary to access implementation details of a lower layer.

**Flag when:**
- Table-level logic accesses `_handle`, `_file`, `_mode`, or other private storage internals directly (e.g., `self._storage._handle.seek(0)` inside `table.py`)
- Higher-level code bypasses the public API of a collaborator to manipulate its internal state

**Suggested fix:** Move the low-level operation into the abstraction that owns it (e.g., add a `reset()` or `rewind()` method to the storage class).

**Do NOT flag:**
- Using `self._storage.read()` or `self._storage.write()` — these are the intended public/internal API of the storage layer

---

## 3. Error Handling

### 3.1 Swallowed Exceptions (Severity: High / Medium)

Flag any `except` block that silences an exception without giving the caller or operator any signal that something went wrong.

**Flag (High) when the except block:**
- Contains only `pass` with no logging or re-raise
- Prints a message and returns silently (no re-raise)
- Assigns a fallback value but discards the exception entirely when the failure is significant

**Flag (Medium) when:**
- The except block catches a specific exception and only `pass`es without logging

**Suggested fix:** At minimum, log the error. Prefer re-raising or wrapping in a domain-specific exception.

```python
# Bad
except KeyError:
    pass

# Good
except KeyError:
    logger.warning("Document not found: %s", doc_id)
    raise
```

**Do NOT flag:**
- `except` blocks that capture the exception (`as e`) and assign a meaningful fallback, with clear intent
- `except` blocks that re-raise, chain (`raise ... from e`), or convert to a domain exception

---

### 3.2 Broad Exceptions (Severity: Medium)

Flag `except Exception` in non-top-level code. Catching all exceptions hides bugs and makes debugging hard.

**Flag when:**
- `except Exception` (or bare `except:`) is used inside a helper, method, or library function that is not a top-level entry point or error boundary

**Suggested fix:** Use the most specific exception type(s) applicable:
```python
# Bad
except Exception:
    return False

# Good
except (KeyError, TypeError):
    return False
```

**Do NOT flag:**
- `except (KeyError, TypeError)` or other tuples of specific exceptions, even if more than one type is listed
- Adding a new specific exception type to an existing tuple (e.g., adding `ValueError`)

---

### 3.3 State Consistency (Severity: High)

Flag changes that can leave the system in a corrupt or inconsistent state if an operation fails midway.

**Flag when:**
- A counter, flag, or index is reset/updated **before** the I/O operation it tracks succeeds
- State is modified before a write, such that a failed write leaves the state out of sync

```python
# Bad — counter reset before write; if write fails, counter is wrong
self._cache_modified_count = 0
self.storage.write(self.cache)

# Good — write first, reset only on success
self.storage.write(self.cache)
self._cache_modified_count = 0
```

**Suggested fix:** Use an atomic pattern: perform the side-effectful operation first, update local state only on success.

**Do NOT flag:**
- Guard conditions that check state before flushing (e.g., `if self._cache_modified_count > 0: self.flush()`)

---

## 4. Performance

### 4.1 N+1 Queries (Severity: Medium)

Flag any storage read, database query, or network call made inside a loop. This is the N+1 query pattern and causes O(N) I/O where O(1) is possible.

**Flag when:**
- `self._storage.read()`, `self._read_table()`, or equivalent is called inside a `for` loop
- A query or fetch is made per-iteration when a single up-front read would suffice

```python
# Bad
for doc_id in list(table.keys()):
    self._storage.read()   # N reads for N documents
    ...

# Good
for doc_id in list(table.keys()):
    ...  # use already-loaded table
```

**Do NOT flag:**
- Loops where no I/O is performed inside
- A single read performed **before** the loop starts, with results passed into the loop

---

### 4.2 Memory Safety (Severity: Medium)

Flag patterns that load an unbounded or large dataset entirely into memory when a streaming or lazy approach is available.

**Flag when:**
- `file.read()` is used to load an entire file into a string before parsing (prefer `json.load(handle)` over `json.loads(handle.read())`)
- `list(generator_expression)` is used to eagerly collect all results without a limit or pagination guard when the dataset may be large

**Suggested fix:**
- Use `json.load(handle)` instead of `json.loads(handle.read())`
- Use generators (`yield`) or add pagination/limits for large collections

**Do NOT flag:**
- List comprehensions used for filtering when the dataset is already bounded by a query
- `list()` calls on known-small iterables

---

## 5. Security

### 5.1 Unsafe Serialization / Code Execution (Severity: High)

Flag any use of deserialization or evaluation functions that can execute arbitrary code from external input.

**Flag:**
- `eval(...)` on any input that may come from outside the process (user input, file contents, network)
- `pickle.loads(...)` on any payload that may come from an untrusted source
- `yaml.load(stream, Loader=yaml.Loader)` or `yaml.load(stream)` without `Loader=yaml.SafeLoader`

**Suggested fixes:**
- Replace `eval(s)` with `ast.literal_eval(s)` for simple data, or use a proper parser
- Replace `pickle.loads(...)` with `json.loads(...)` or another safe format
- Replace `yaml.load(...)` with `yaml.safe_load(...)`

**Do NOT flag:**
- `json.loads(...)` or `json.load(...)` — JSON parsing is safe
- `yaml.safe_load(...)` — explicitly safe
- `ast.literal_eval(...)` — restricted to Python literals, safe

---

## Severity Reference

| Severity | When to use |
|----------|-------------|
| **High** | Code that can cause data loss, security vulnerabilities, or corrupt state |
| **Medium** | Code that violates architectural principles or causes bugs under load/error conditions |
| **Low** | Code quality issues: naming, style, readability |
| **None** | No issue — do not comment |

---

## Output Format

Group findings by severity. For each issue include:
- The file and line(s) affected
- The rule violated
- A concrete suggestion

If no issues are found, respond with: `No issues found. Great work!`
