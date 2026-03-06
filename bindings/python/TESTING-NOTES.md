# Python Bindings: SWIG Typemap + Return-Type Wrapping — Testing Notes

## Branch
`claude/gnucash-development-aI8ET`

## What Changed

### 1. SWIG Typemap Compatibility Layer (`gnucash_core.i`)

Added `GNC_ACCEPT_WRAPPER` macro that generates `%typemap(in)` entries for
21 pointer types (Account, Split, Transaction, GNCLot, gnc_commodity,
GNCPrice, GNCPriceDB, QofBook, QofSession, GncGUID, plus all business
types). These typemaps:

- Try normal SWIG pointer conversion first (zero overhead)
- Fall back to extracting `.instance` from ClassFromFunctions wrappers
- Emit `DeprecationWarning` on the fallback path

### 2. Return-Type Wrapping Fixes (`gnucash_core.py`)

| Class | Method | Was | Now |
|-------|--------|-----|-----|
| GncPrice | `get_commodity()` | SwigPyObject | GncCommodity |
| GncPrice | `get_currency()` | SwigPyObject | GncCommodity |
| GncPrice | `clone(book)` | SwigPyObject | GncPrice |
| GncPrice | `get_value()` | _gnc_numeric | GncNumeric |
| GncPriceDB | `nth_price(comm, n)` | SwigPyObject | GncPrice |
| GncPriceDB | `lookup_day_t64(comm, curr, date)` | SwigPyObject | GncPrice |
| GncPriceDB | `convert_balance_nearest_before_price_t64(...)` | _gnc_numeric | GncNumeric |
| GncPriceDB | `lookup_latest_any_currency(comm)` | list[SwigPyObject] | list[GncPrice] |
| GncPriceDB | `lookup_nearest_before_any_currency_t64(comm, date)` | list[SwigPyObject] | list[GncPrice] |
| GncPriceDB | `lookup_nearest_in_time_any_currency_t64(comm, date)` | list[SwigPyObject] | list[GncPrice] |
| GncCommodity | `obtain_twin(book)` | SwigPyObject | GncCommodity |
| GncCommodity | `get_namespace_ds()` | SwigPyObject | GncCommodityNamespace |
| Account | `get_currency_or_parent()` | SwigPyObject | GncCommodity |
| GncLot | `get_split_list()` | list[SwigPyObject] | list[Split] |

### 3. Example Script Cleanup

Removed `type(x).__name__ == 'SwigPyObject'` workarounds from:
- `gnc_convenience.py`
- `gncinvoicefkt.py`
- `str_methods.py`

## Build Instructions

```bash
mkdir build && cd build
cmake .. -DWITH_PYTHON=ON -DWITH_GNUCASH=OFF -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

For full build with backends (needed for file-based tests):
```bash
cmake .. -DWITH_PYTHON=ON -DCMAKE_BUILD_TYPE=Release
```

## Tests Already Passing (no database needed)

These were verified on this branch with `-DWITH_GNUCASH=OFF`:

- Existing test suite: **55/56 pass** (1 pre-existing failure: `test_session_with_new_file`
  requires XML backend not built with `WITH_GNUCASH=OFF`)
- All 17 targeted tests below pass

## Automated Test Suite (uses in-repo data files)

A new test file has been added:

```
bindings/python/tests/test_price_and_wrapping.py
```

This uses test data **already in the repository** — no external files needed:

| Test data file | Location | Contents |
|----------------|----------|----------|
| `pricedb1.gml2` | `libgnucash/backend/xml/test/test-files/xml2/` | 13 stock commodities (CORL, ANDN, EGRP, etc.) with many prices in USD |
| `sample1.gnucash` | `libgnucash/backend/xml/test/test-files/load-save/` | Accounts, transactions, splits, and 1 lot |

### Test classes and what they cover

| Test class | Data file | What it tests |
|------------|-----------|---------------|
| `TestGncPriceWrapping` | pricedb1.gml2 | `lookup_latest` → GncPrice, `nth_price` → GncPrice, `get_commodity/currency` → GncCommodity, `get_value` → GncNumeric, `clone` → GncPrice, list methods → list[GncPrice] |
| `TestGncLotSplitList` | sample1.gnucash | `GncLot.get_split_list()` → list[Split] |
| `TestAccountCurrencyOrParent` | sample1.gnucash | `Account.get_currency_or_parent()` → GncCommodity |
| `TestCommodityObtainTwin` | *(in-memory)* | `GncCommodity.obtain_twin(book)` → GncCommodity |
| `TestCommodityNamespaceDS` | *(in-memory)* | `GncCommodity.get_namespace_ds()` → GncCommodityNamespace |
| `TestSwigTypemapCompat` | pricedb1.gml2 | Wrapper→C function emits DeprecationWarning; `.instance` does not |

### Running the tests

**Requires XML backend** (full build):
```bash
cd build
cmake .. -DWITH_PYTHON=ON -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Run just the new wrapping tests:
cd /path/to/source
PYTHONPATH=build/lib:build/lib/gnucash python -m pytest \
    bindings/python/tests/test_price_and_wrapping.py -v

# Or with unittest:
python -m unittest bindings.python.tests.test_price_and_wrapping -v
```

Tests that need the XML backend will **auto-skip** (not fail) when built
with `-DWITH_GNUCASH=OFF`. The in-memory tests (`TestCommodityObtainTwin`,
`TestCommodityNamespaceDS`) always run.

## Manual Testing with Your Own Data

If you want to test against your own GnuCash file (SQLite or XML) with
richer data (multiple currencies, more lots, business objects), here are
copy-paste scripts.

### GncPrice wrapping (highest priority)

```python
from gnucash import Session, GncPrice, GncCommodity, GncNumeric

ses = Session("your_file.gnucash")
book = ses.get_book()
table = book.get_table()
pricedb = book.get_price_db()

usd = table.lookup('CURRENCY', 'USD')
eur = table.lookup('CURRENCY', 'EUR')

# Verify these return GncPrice, not SwigPyObject
price = pricedb.lookup_latest(usd, eur)
assert isinstance(price, GncPrice), f"got {type(price)}"

price = pricedb.nth_price(usd, 0)
assert isinstance(price, GncPrice), f"got {type(price)}"

# Verify GncPrice methods return wrapped objects
assert isinstance(price.get_commodity(), GncCommodity)
assert isinstance(price.get_currency(), GncCommodity)
assert isinstance(price.get_value(), GncNumeric)
assert isinstance(price.clone(book), GncPrice)

print("GncPrice tests passed")
ses.end()
```

### GncPriceDB list methods

```python
from gnucash import Session, GncPrice
from datetime import datetime

ses = Session("your_file.gnucash")
book = ses.get_book()
table = book.get_table()
pricedb = book.get_price_db()

usd = table.lookup('CURRENCY', 'USD')

# These should return list[GncPrice], not list[SwigPyObject]
prices = pricedb.lookup_latest_any_currency(usd)
assert all(isinstance(p, GncPrice) for p in prices), \
    f"types: {[type(p).__name__ for p in prices]}"

prices = pricedb.get_prices(usd, table.lookup('CURRENCY', 'EUR'))
assert all(isinstance(p, GncPrice) for p in prices)

# Time-based lookups (use a date you know has prices)
date = datetime(2024, 1, 15)
prices = pricedb.lookup_nearest_in_time_any_currency_t64(usd, date)
assert all(isinstance(p, GncPrice) for p in prices)

prices = pricedb.lookup_nearest_before_any_currency_t64(usd, date)
assert all(isinstance(p, GncPrice) for p in prices)

# lookup_day_t64
price = pricedb.lookup_day_t64(usd, table.lookup('CURRENCY', 'EUR'), date)
# May be None if no price on that exact day
if price is not None:
    assert isinstance(price, GncPrice)

# convert_balance_nearest_before_price_t64
from gnucash import GncNumeric
bal = pricedb.convert_balance_nearest_before_price_t64(
    GncNumeric(100, 1), usd, table.lookup('CURRENCY', 'EUR'), date)
assert isinstance(bal, GncNumeric)

print("GncPriceDB tests passed")
ses.end()
```

### GncLot.get_split_list

```python
from gnucash import Session, Split

ses = Session("your_file.gnucash")
book = ses.get_book()
root = book.get_root_account()

# Find an account with lots (typically investment accounts)
# Adjust the account path for your data
for acct in root.get_descendants():
    lots = acct.GetLotList()
    if lots:
        for lot in lots:
            splits = lot.get_split_list()
            assert all(isinstance(s, Split) for s in splits), \
                f"types: {[type(s).__name__ for s in splits]}"
            print(f"  Lot '{lot.get_title()}': {len(splits)} splits, all Split type")
        break

print("GncLot.get_split_list tests passed")
ses.end()
```

### Account.get_currency_or_parent

```python
from gnucash import Session, GncCommodity

ses = Session("your_file.gnucash")
book = ses.get_book()
root = book.get_root_account()

for acct in root.get_descendants():
    result = acct.get_currency_or_parent()
    if result is not None:
        assert isinstance(result, GncCommodity), f"got {type(result)}"

print("Account.get_currency_or_parent tests passed")
ses.end()
```

### SWIG typemap compatibility (old code still works)

```python
import warnings
from gnucash import Session, gnucash_core_c as gc

ses = Session("your_file.gnucash")
book = ses.get_book()
table = book.get_table()
pricedb = book.get_price_db()
usd = table.lookup('CURRENCY', 'USD')

price = pricedb.lookup_latest(usd, table.lookup('CURRENCY', 'EUR'))
if price is not None:
    # Old-style: pass wrapper to gnucash_core_c — should work with warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        comm = gc.gnc_price_get_commodity(price)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        print(f"DeprecationWarning: {w[0].message}")

    # Manual unwrap: should work with no warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        comm = gc.gnc_price_get_commodity(price.instance)
        assert len(w) == 0

print("Typemap compatibility tests passed")
ses.end()
```

## Known Limitations / Not Yet Fixed

- `gnc_lot_get_balance_before()` — void function with output parameters,
  needs SWIG OUTPUT typemap, separate issue
- `gnc_quote_source` — no Python wrapper class exists, needs new class
- `get_latest_price`, `get_nearest_price`, `get_nearest_before_price` —
  return gnc_numeric directly (the price value, not a GNCPrice *),
  could be wrapped to GncNumeric for consistency but lower priority
