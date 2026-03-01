# Coding Rules

General coding rules created from real defects.

Keep this list short and descriptions concise.

Update with new rules as needed, but avoid over-engineering or nitpicking.

---

### Constants

- **No magic numbers.** Numeric literals (prices, thresholds) go in `config.py`.
- **No magic strings.** Warehouse codes, location tags, etc. go in `config.py`.
- **No heuristic lookups.** Use foreign keys, not name-matching, to resolve relationships.

### Return Types

- **Return what the caller expects.** If a column is `REAL`, return a `float`, not a dict.
- **No duplicate keys in dict literals.** The last one silently wins — a subtle bug.

### Exception Handling

- **Never `except: pass`.** Always capture the exception and log it.
- **Use `except Exception:`, not bare `except:`.** Bare `except` catches `SystemExit` and `KeyboardInterrupt`.
- **Surface failures to callers.** Logging an error is not enough — add a `"warning"` key or re-raise so the caller can act on it.
- **Log at the right level.** Expected/benign → `debug`. Unexpected but non-fatal → `warning`. Use `pass` only if you can justify silence.
- **Don't use exceptions for normal control flow.** If a condition is expected (e.g. insufficient stock), return a status instead of raising. Reserve exceptions for truly unexpected errors.

### Database & Performance

- **Never scan a full column in Python to find a MAX.** Use `SELECT MAX(…)` or equivalent SQL aggregate — let the database do the work.
- **Index every foreign-key column.** SQLite only auto-indexes primary keys. All FK columns used in joins or filters need an explicit `CREATE INDEX` in `schema.sql`.
- **Reuse database connections.** `db_conn()` supports nesting — wrap a batch of service calls in a single `with db_conn():` block so inner calls reuse the same connection instead of opening/closing thousands of connections.
- **Prune iteration lists.** When looping over a growing list (e.g. all SOs across weeks), track completed items in a set and skip them instead of re-querying entities that are already done.
- **Use WAL mode.** `get_connection()` enables `PRAGMA journal_mode=WAL` and `synchronous=NORMAL` for better write throughput.

### Shared Data Structures

- **Centralize dict↔column mappings.** When a dict is stored across prefixed DB columns (e.g. `ship_to_*`), use shared helpers (`utils.py`) instead of inline `.get()` calls in every service.

### Quantities

- **All quantity columns are `INTEGER`.** Store in the smallest base unit (grams for `"g"` items, millilitres for `"ml"` items, pieces for `"ea"` items). Never use `REAL` for quantities.
- **Use `format_qty(value, uom)` (Python) or `formatQtyWithUom(value, uom)` (TypeScript) for display.** Raw integers are converted to human-readable strings (e.g. `2400` + `"g"` → `"2.4 kg"`).
- **No `float()` casts on qty columns.** Use `int()` when accepting values from external inputs. All service function signatures that accept a quantity use `int`, not `float`.
- **No float-tolerance checks** (e.g. `> 0.001`). With integer quantities, use plain `> 0`.
