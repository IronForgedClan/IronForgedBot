import enum
import unittest


class TestPermConstants(unittest.TestCase):
    def test_perm_enum_values(self):
        from api.permissions import PERM

        self.assertEqual(PERM.META_READ, "meta:read")
        self.assertEqual(PERM.MEMBERS_READ, "members:read")
        self.assertEqual(PERM.MEMBERS_LIST, "members:list")
        self.assertEqual(PERM.INGOTS_READ, "ingots:read")
        self.assertEqual(PERM.INGOTS_READ_TRANSACTIONS, "ingots:read:transactions")
        self.assertEqual(PERM.SCORES_READ, "scores:read")
        self.assertEqual(PERM.SCORES_READ_HISTORY, "scores:read:history")

    def test_perm_is_str_enum(self):
        from api.permissions import PERM

        self.assertTrue(issubclass(PERM, enum.StrEnum))

    def test_known_perms_complete(self):
        from api.permissions import KNOWN_PERMS, PERM

        names = {name for name, _ in KNOWN_PERMS}
        self.assertEqual(names, set(PERM))

    def test_known_perms_have_descriptions(self):
        from api.permissions import KNOWN_PERMS

        for name, desc in KNOWN_PERMS:
            self.assertIsInstance(name, str)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_known_perm_names_matches_known_perms(self):
        from api.permissions import KNOWN_PERM_NAMES, KNOWN_PERMS

        self.assertEqual(KNOWN_PERM_NAMES, frozenset(name for name, _ in KNOWN_PERMS))
