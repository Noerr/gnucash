"""Tests for GncPrice / GncPriceDB / GncLot return-type wrapping.

These tests require an XML backend (i.e. build with -DWITH_GNUCASH=ON or at
least with the XML backend enabled) because they open on-disk GnuCash files.

Test data comes from files already in the repo:
  - pricedb1.gml2  : 13 commodities, many prices in USD, 1 root account
  - sample1.gnucash : accounts, transactions, splits, 1 lot
"""

import os
import shutil
import tempfile
import warnings
from datetime import datetime
from pathlib import Path
from unittest import TestCase, main, skipUnless
from urllib.parse import urlunparse

# Locate test data relative to the source tree.  When running from a build
# directory the source tree is typically the parent; we walk up until we find
# the marker directory.
def _find_source_root():
    """Walk up from this file looking for the repo root."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / "libgnucash").is_dir():
            return d
        d = d.parent
    # Fall back to environment variable set by CMake / CTest
    builddir = os.environ.get("GNC_BUILDDIR")
    if builddir:
        # source tree is often one level up from build dir
        candidate = Path(builddir).parent
        if (candidate / "libgnucash").is_dir():
            return candidate
    return None

_SRC_ROOT = _find_source_root()
_PRICEDB_FILE = (
    _SRC_ROOT / "libgnucash" / "backend" / "xml" / "test" / "test-files"
    / "xml2" / "pricedb1.gml2"
) if _SRC_ROOT else None
_SAMPLE_FILE = (
    _SRC_ROOT / "libgnucash" / "backend" / "xml" / "test" / "test-files"
    / "load-save" / "sample1.gnucash"
) if _SRC_ROOT else None

_HAS_TEST_DATA = _PRICEDB_FILE is not None and _PRICEDB_FILE.exists()
_HAS_SAMPLE_DATA = _SAMPLE_FILE is not None and _SAMPLE_FILE.exists()


def _copy_to_tmp(src_path, tmpdir):
    """Copy a GnuCash file into a temp dir and return an xml:// URI."""
    fname = os.path.basename(src_path)
    dest = os.path.join(tmpdir, fname)
    shutil.copy2(str(src_path), dest)
    # URI format: xml://<dir>/<filename>  (matches test_session.py convention)
    return urlunparse(("xml", tmpdir, fname, "", "", ""))


def _can_open_xml():
    """Return True if the XML backend is available."""
    try:
        from gnucash import Session, SessionOpenMode
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = urlunparse(("xml", tmpdir, "probe", "", "", ""))
            with Session(uri, SessionOpenMode.SESSION_NEW_STORE) as ses:
                pass
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test: GncPrice and GncPriceDB wrapping via pricedb1.gml2
# ---------------------------------------------------------------------------
@skipUnless(_HAS_TEST_DATA, "pricedb1.gml2 not found in source tree")
class TestGncPriceWrapping(TestCase):
    """Open pricedb1.gml2 and verify that GncPrice / GncPriceDB methods
    return properly wrapped Python objects instead of raw SwigPyObjects."""

    @classmethod
    def setUpClass(cls):
        if not _can_open_xml():
            raise unittest.SkipTest("XML backend not available")
        cls._tmpdir = tempfile.mkdtemp(prefix="gnc_test_price_")
        from gnucash import Session, SessionOpenMode
        uri = _copy_to_tmp(_PRICEDB_FILE, cls._tmpdir)
        cls.ses = Session(uri, SessionOpenMode.SESSION_NORMAL_OPEN)
        cls.book = cls.ses.get_book()
        cls.table = cls.book.get_table()
        cls.pricedb = cls.book.get_price_db()
        # Look up a commodity we know is in the file
        cls.usd = cls.table.lookup("CURRENCY", "USD")
        cls.corl = cls.table.lookup("NASDAQ", "CORL")

    @classmethod
    def tearDownClass(cls):
        cls.ses.end()
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    # -- basic sanity --

    def test_commodity_lookup(self):
        """Verify we can find the commodities in the test file."""
        self.assertIsNotNone(self.usd)
        self.assertIsNotNone(self.corl)

    # -- GncPriceDB single-price lookups --

    def test_lookup_latest_returns_gnc_price(self):
        from gnucash import GncPrice
        price = self.pricedb.lookup_latest(self.corl, self.usd)
        self.assertIsNotNone(price, "No price found for CORL/USD")
        self.assertIsInstance(price, GncPrice)

    def test_nth_price_returns_gnc_price(self):
        from gnucash import GncPrice
        price = self.pricedb.nth_price(self.corl, 0)
        self.assertIsNotNone(price, "nth_price(CORL, 0) returned None")
        self.assertIsInstance(price, GncPrice)

    # -- GncPrice attribute methods --

    def test_get_commodity_returns_gnc_commodity(self):
        from gnucash import GncPrice, GncCommodity
        price = self.pricedb.lookup_latest(self.corl, self.usd)
        self.assertIsNotNone(price)
        comm = price.get_commodity()
        self.assertIsInstance(comm, GncCommodity)

    def test_get_currency_returns_gnc_commodity(self):
        from gnucash import GncPrice, GncCommodity
        price = self.pricedb.lookup_latest(self.corl, self.usd)
        self.assertIsNotNone(price)
        curr = price.get_currency()
        self.assertIsInstance(curr, GncCommodity)

    def test_get_value_returns_gnc_numeric(self):
        from gnucash import GncPrice, GncNumeric
        price = self.pricedb.lookup_latest(self.corl, self.usd)
        self.assertIsNotNone(price)
        val = price.get_value()
        self.assertIsInstance(val, GncNumeric)

    def test_clone_returns_gnc_price(self):
        from gnucash import GncPrice
        price = self.pricedb.lookup_latest(self.corl, self.usd)
        self.assertIsNotNone(price)
        cloned = price.clone(self.book)
        self.assertIsInstance(cloned, GncPrice)

    # -- GncPriceDB list methods --

    def test_lookup_latest_any_currency_returns_list_of_gnc_price(self):
        from gnucash import GncPrice
        prices = self.pricedb.lookup_latest_any_currency(self.corl)
        self.assertIsInstance(prices, list)
        # pricedb1.gml2 has CORL priced in USD so we expect at least 1
        self.assertGreater(len(prices), 0,
                           "Expected at least one price for CORL")
        for p in prices:
            self.assertIsInstance(p, GncPrice)

    def test_get_prices_returns_list_of_gnc_price(self):
        from gnucash import GncPrice
        prices = self.pricedb.get_prices(self.corl, self.usd)
        self.assertIsInstance(prices, list)
        self.assertGreater(len(prices), 0)
        for p in prices:
            self.assertIsInstance(p, GncPrice)

    def test_lookup_nearest_in_time_any_currency(self):
        from gnucash import GncPrice
        # Prices in pricedb1 are from 2001-03-26
        date = datetime(2001, 3, 26)
        prices = self.pricedb.lookup_nearest_in_time_any_currency_t64(
            self.corl, date)
        self.assertIsInstance(prices, list)
        for p in prices:
            self.assertIsInstance(p, GncPrice)

    def test_lookup_nearest_before_any_currency(self):
        from gnucash import GncPrice
        date = datetime(2001, 4, 1)
        prices = self.pricedb.lookup_nearest_before_any_currency_t64(
            self.corl, date)
        self.assertIsInstance(prices, list)
        for p in prices:
            self.assertIsInstance(p, GncPrice)


# ---------------------------------------------------------------------------
# Test: GncLot.get_split_list via sample1.gnucash
# ---------------------------------------------------------------------------
@skipUnless(_HAS_SAMPLE_DATA, "sample1.gnucash not found in source tree")
class TestGncLotSplitList(TestCase):
    """Open sample1.gnucash and verify that GncLot.get_split_list() returns
    properly wrapped Split objects."""

    @classmethod
    def setUpClass(cls):
        if not _can_open_xml():
            raise unittest.SkipTest("XML backend not available")
        cls._tmpdir = tempfile.mkdtemp(prefix="gnc_test_lot_")
        from gnucash import Session, SessionOpenMode
        uri = _copy_to_tmp(_SAMPLE_FILE, cls._tmpdir)
        cls.ses = Session(uri, SessionOpenMode.SESSION_NORMAL_OPEN)
        cls.book = cls.ses.get_book()

    @classmethod
    def tearDownClass(cls):
        cls.ses.end()
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def _find_lot(self):
        """Find the first lot in any account."""
        root = self.book.get_root_account()
        for acct in root.get_descendants():
            lots = acct.GetLotList()
            if lots:
                return lots[0]
        return None

    def test_lot_exists(self):
        """sample1.gnucash should have at least one lot."""
        lot = self._find_lot()
        self.assertIsNotNone(lot, "No lots found in sample1.gnucash")

    def test_get_split_list_returns_splits(self):
        from gnucash import Split
        lot = self._find_lot()
        if lot is None:
            self.skipTest("No lots in sample1.gnucash")
        splits = lot.get_split_list()
        self.assertIsInstance(splits, list)
        self.assertGreater(len(splits), 0, "Lot has no splits")
        for s in splits:
            self.assertIsInstance(s, Split)


# ---------------------------------------------------------------------------
# Test: Account.get_currency_or_parent via sample1.gnucash
# ---------------------------------------------------------------------------
@skipUnless(_HAS_SAMPLE_DATA, "sample1.gnucash not found in source tree")
class TestAccountCurrencyOrParent(TestCase):
    """Verify Account.get_currency_or_parent() returns GncCommodity."""

    @classmethod
    def setUpClass(cls):
        if not _can_open_xml():
            raise unittest.SkipTest("XML backend not available")
        cls._tmpdir = tempfile.mkdtemp(prefix="gnc_test_acct_")
        from gnucash import Session, SessionOpenMode
        uri = _copy_to_tmp(_SAMPLE_FILE, cls._tmpdir)
        cls.ses = Session(uri, SessionOpenMode.SESSION_NORMAL_OPEN)
        cls.book = cls.ses.get_book()

    @classmethod
    def tearDownClass(cls):
        cls.ses.end()
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_get_currency_or_parent_returns_commodity(self):
        from gnucash import GncCommodity
        root = self.book.get_root_account()
        descendants = root.get_descendants()
        self.assertGreater(len(descendants), 0)
        found_one = False
        for acct in descendants:
            result = acct.get_currency_or_parent()
            if result is not None:
                self.assertIsInstance(result, GncCommodity)
                found_one = True
        self.assertTrue(found_one,
                        "No account returned a non-None commodity")


# ---------------------------------------------------------------------------
# Test: GncCommodity.obtain_twin wrapping
# ---------------------------------------------------------------------------
class TestCommodityObtainTwin(TestCase):
    """Verify GncCommodity.obtain_twin(book) returns GncCommodity."""

    def test_obtain_twin_same_book(self):
        from gnucash import Session, GncCommodity
        ses = Session()
        book = ses.get_book()
        table = book.get_table()
        usd = table.lookup("CURRENCY", "USD")
        self.assertIsNotNone(usd)
        twin = usd.obtain_twin(book)
        self.assertIsInstance(twin, GncCommodity)
        ses.end()


# ---------------------------------------------------------------------------
# Test: GncCommodity.get_namespace_ds wrapping
# ---------------------------------------------------------------------------
class TestCommodityNamespaceDS(TestCase):
    """Verify GncCommodity.get_namespace_ds() returns
    GncCommodityNamespace."""

    def test_get_namespace_ds(self):
        from gnucash import Session
        from gnucash.gnucash_core import GncCommodityNamespace
        ses = Session()
        book = ses.get_book()
        table = book.get_table()
        usd = table.lookup("CURRENCY", "USD")
        self.assertIsNotNone(usd)
        ns = usd.get_namespace_ds()
        self.assertIsInstance(ns, GncCommodityNamespace)
        ses.end()


# ---------------------------------------------------------------------------
# Test: SWIG typemap compatibility (wrapper → instance unwrap)
# ---------------------------------------------------------------------------
@skipUnless(_HAS_TEST_DATA, "pricedb1.gml2 not found in source tree")
class TestSwigTypemapCompat(TestCase):
    """Verify that passing a ClassFromFunctions wrapper to a C function
    still works (via the SWIG typemap) and emits a DeprecationWarning."""

    @classmethod
    def setUpClass(cls):
        if not _can_open_xml():
            raise unittest.SkipTest("XML backend not available")
        cls._tmpdir = tempfile.mkdtemp(prefix="gnc_test_swig_")
        from gnucash import Session, SessionOpenMode
        uri = _copy_to_tmp(_PRICEDB_FILE, cls._tmpdir)
        cls.ses = Session(uri, SessionOpenMode.SESSION_NORMAL_OPEN)
        cls.book = cls.ses.get_book()
        cls.table = cls.book.get_table()
        cls.pricedb = cls.book.get_price_db()
        cls.usd = cls.table.lookup("CURRENCY", "USD")
        cls.corl = cls.table.lookup("NASDAQ", "CORL")

    @classmethod
    def tearDownClass(cls):
        cls.ses.end()
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_wrapper_triggers_deprecation_warning(self):
        """Passing a GncPrice wrapper to gnucash_core_c should emit
        DeprecationWarning and still return a valid result."""
        from gnucash import GncPrice
        from gnucash import gnucash_core_c as gc

        price = self.pricedb.lookup_latest(self.corl, self.usd)
        if price is None:
            self.skipTest("No price data")

        self.assertIsInstance(price, GncPrice)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Pass the wrapper object directly — typemap should unwrap it
            comm_instance = gc.gnc_price_get_commodity(price)
            # Check that a DeprecationWarning was issued
            dep_warnings = [x for x in w
                            if issubclass(x.category, DeprecationWarning)]
            self.assertGreater(len(dep_warnings), 0,
                               "Expected DeprecationWarning from typemap")

    def test_raw_instance_no_warning(self):
        """Passing price.instance directly should NOT emit a warning."""
        from gnucash import gnucash_core_c as gc

        price = self.pricedb.lookup_latest(self.corl, self.usd)
        if price is None:
            self.skipTest("No price data")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            comm_instance = gc.gnc_price_get_commodity(price.instance)
            dep_warnings = [x for x in w
                            if issubclass(x.category, DeprecationWarning)]
            self.assertEqual(len(dep_warnings), 0,
                             "Unexpected DeprecationWarning for .instance")


if __name__ == '__main__':
    import unittest
    main()
