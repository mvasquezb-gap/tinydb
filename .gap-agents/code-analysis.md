### 8.1 TinyDB Canonical Variable Names (Severity: Low)

TinyDB has established domain-specific variable names that are part of its internal conventions and public API. These names are intentionally concise and carry precise meaning within this codebase. They must not be treated as generic or vague.

**Flag when:**

- A new variable introduced in the diff is named `data`, `info`, `manager`, `handle`, `flag`, or `result` while referring to a TinyDB document, table, or storage object
- A PR renames an existing TinyDB canonical name to one of the above generic names

**Suggested fix:** Use names that reflect the TinyDB domain. Examples:

```python
# Bad
data = table.get(str(doc_id), None)
manager = self.table_class(self.storage, name, **kwargs)

# Good
raw_doc = table.get(str(doc_id), None)
table_instance = self.table_class(self.storage, name, **kwargs)
```

**Do NOT flag:**

- `table` — refers specifically to a `Table` instance, the core TinyDB entity
- `doc_id`, `doc_ids` — canonical identifiers for TinyDB documents
- `cond` — the established parameter name for query conditions (`QueryLike`)
- `raw_doc` — the established name for a document dict before class conversion
- `_tables`, `_storage`, `_query_cache`, `_next_id` — existing private instance attributes

---

### 8.2 Storage Layer Access Boundary (Severity: Medium)

TinyDB enforces a strict separation between the table layer (`table.py`, `database.py`) and the storage layer (`storages.py`). The only sanctioned way for table-layer code to interact with storage is through `self._storage.read()` and `self._storage.write()`. Reaching past this interface into storage internals is forbidden.

**Flag when:**

- Code in `table.py` or `database.py` accesses `self._storage._handle`, `self._storage._mode`, `self._storage._file`, or any other private attribute of the storage object
- Table-layer code calls file-level operations (`seek`, `truncate`, `flush`) directly on the storage's internal file handle
- Code in `middlewares.py` accesses `self.storage._handle` or any private attribute of the wrapped storage object

**Suggested fix:** Add a dedicated method to the storage class that performs the low-level operation, and call that method from the table layer instead.

```python
# Bad — table.py reaching into storage internals
tables = self._storage.read()
if hasattr(self._storage, '_handle') and self._storage._handle:
    self._storage._handle.seek(0)

# Good — operation belongs in storages.py
tables = self._storage.read()
```

**Do NOT flag:**

- `self._storage.read()` and `self._storage.write()` called from `table.py` — these are the intended interface
- `self.storage.read()`, `self.storage.write()`, `self.storage.close()`, `self.storage.flush()` called from `middlewares.py` — middleware is designed to delegate through this interface

---

### 8.3 Storage Reads Inside Loops (Severity: Medium)

In TinyDB, every call to `self._storage.read()` or `self._read_table()` reads the entire database file from disk. Calling either inside a loop is always a bug — it performs a full file read on every iteration.

**Flag when:**

- `self._storage.read()` appears inside the body of a `for` or `while` loop
- `self._read_table()` appears inside the body of a `for` or `while` loop
- `self.storage.read()` appears inside a loop in `middlewares.py`

**Suggested fix:** Call the read once before the loop and iterate the result.

```python
# Bad — reads entire file on every iteration
for doc_id in list(table.keys()):
    self._storage.read()
    if _cond(table[doc_id]):
        ...

# Good — single read before the loop
table = self._read_table()
for doc_id in list(table.keys()):
    if _cond(table[doc_id]):
        ...
```

**Do NOT flag:**

- A single `self._read_table()` or `self._storage.read()` call made before a loop to load data — this is the correct pattern
- Calls inside the implementation of `_read_table()` or `_write_table()` themselves

---

### 8.4 File Access Mode Validation Strings (Severity: Low)

TinyDB defines a fixed set of valid file access modes: `'r'`, `'rb'`, `'r+'`, `'rb+'`. When these strings appear together inside the access mode validation tuple in `storages.py`, they are documented API values and must not be treated as magic strings.

**Flag when:**

- A single access mode string (e.g., `'r+'`) is used in isolation in a new conditional outside the full validation tuple
- A new string is added to the access mode check that is not one of the four established values

**Suggested fix:** Always validate against the full tuple of accepted modes, never a single string in isolation.

```python
# Bad — lone string in a new condition
if access_mode != 'r+':
    warnings.warn(...)

# Good — full validation tuple
if access_mode not in ('r', 'rb', 'r+', 'rb+'):
    warnings.warn(...)
```

**Do NOT flag:**

- The existing validation `if access_mode not in ('r', 'rb', 'r+', 'rb+')` — this is TinyDB's documented access mode guard, not a magic value

---

### 8.5 KeyError as Not-Found Signal (Severity: Medium)

In TinyDB, `KeyError` raised during a document lookup by ID means the document does not exist. This is an expected, recoverable condition. The correct response is to return `None` or raise a descriptive `ValueError` — never to silently pass.

**Flag when:**

- `except KeyError: pass` is used in any document retrieval or update operation
- `KeyError` is caught and re-raised as-is with no context about which document ID was missing

**Suggested fix:** Return `None` to signal "not found" (the TinyDB convention) or raise a `ValueError` with the missing ID:

```python
# Bad
except KeyError:
    pass

# Good — not-found return
except KeyError:
    return None

# Good — informative re-raise
except KeyError as e:
    raise ValueError(f"Document with ID {doc_id} not found") from e
```

**Do NOT flag:**

- `except KeyError: return None` — this is the established TinyDB not-found pattern
- `except KeyError: updated_docs = None` where the assignment clearly communicates that no documents matched — the intent is explicit
