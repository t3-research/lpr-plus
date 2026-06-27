import unittest

from lpr_plus.catalog import cumulative_suites, load_base_transformations, load_refined_transformations


class CatalogTest(unittest.TestCase):
    def test_catalog_counts(self):
        self.assertEqual(len(load_base_transformations()), 5)
        self.assertEqual(len(load_refined_transformations()), 30)
        self.assertEqual(
            [suite["id"] for suite in cumulative_suites()],
            [
                "base-only",
                "base-plus-30",
            ],
        )


if __name__ == "__main__":
    unittest.main()
