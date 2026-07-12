import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import manage_api_consumers  # noqa: E402,F401  (resolves @patch targets)

from api.models import ApiConsumer  # noqa: E402


def _make_consumer(
    name: str = "tester",
    enabled: bool = True,
    perms: list[str] | None = None,
    consumer_id: int = 1,
) -> MagicMock:
    c = MagicMock(spec=ApiConsumer)
    c.id = consumer_id
    c.name = name
    c.enabled = enabled
    c.perms = perms if perms is not None else []
    return c


class FakePrompter:
    def __init__(self, answers: list[str]):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def ask(self, text: str) -> str:
        self.calls.append(("ask", text))
        if not self.answers:
            raise AssertionError(f"FakePrompter exhausted on ask({text!r})")
        return self.answers.pop(0)

    def confirm(self, text: str, default: bool = False) -> bool:
        self.calls.append(("confirm", text))
        if not self.answers:
            raise AssertionError(f"FakePrompter exhausted on confirm({text!r})")
        return self.answers.pop(0).strip().lower() in ("y", "yes")

    def menu(self, options, prompt="Select"):
        self.calls.append(("menu", prompt))
        if not self.answers:
            raise AssertionError(f"FakePrompter exhausted on menu({prompt!r})")
        return int(self.answers.pop(0)) - 1

    def multi_select(
        self,
        options,
        current=None,
        prompt: str = "toggle",
    ) -> set[str]:
        self.calls.append(("multi_select", prompt))
        if not self.answers:
            raise AssertionError(f"FakePrompter exhausted on multi_select({prompt!r})")
        raw = self.answers.pop(0).strip()
        current_set = set(current) if current else set()
        if not raw:
            return current_set
        indices = [int(x) for x in raw.split(",") if x.strip()]
        for i in indices:
            key = options[i - 1][0]
            if key in current_set:
                current_set.discard(key)
            else:
                current_set.add(key)
        return current_set


def _patched_db_with_session(mock_db) -> AsyncMock:
    mock_db._engine = None
    mock_db.dispose = AsyncMock()
    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_db.get_session.return_value = mock_ctx
    return mock_session


@patch("manage_api_consumers.db")
@patch("manage_api_consumers.list_consumers")
class TestListSubcommand(unittest.TestCase):
    def test_list_prints_table(self, mock_list_consumers, mock_db):
        from manage_api_consumers import main

        _patched_db_with_session(mock_db)

        consumers = [
            _make_consumer(
                "alpha", enabled=True, perms=["members:read"], consumer_id=1
            ),
            _make_consumer("beta", enabled=False, perms=[], consumer_id=2),
        ]
        mock_list_consumers.return_value = consumers

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["list"])

        self.assertEqual(rc, 0)
        self.assertIn("alpha", buf.getvalue())
        self.assertIn("beta", buf.getvalue())
        mock_list_consumers.assert_awaited_once()


@patch("manage_api_consumers.db")
@patch("manage_api_consumers.Prompter")
@patch("manage_api_consumers.get_consumer_by_name")
@patch("manage_api_consumers.create_consumer")
@patch("manage_api_consumers.known_perm_options")
class TestInteractiveCreate(unittest.TestCase):
    def test_create_flow(
        self,
        mock_known_perm_options,
        mock_create,
        mock_get_consumer,
        mock_prompter_cls,
        mock_db,
    ):
        from manage_api_consumers import main

        mock_known_perm_options.return_value = [
            ("ingots:read", "Read ingots"),
            ("members:list", "List members"),
            ("members:read", "Read member"),
            ("scores:read", "Read scores"),
        ]
        mock_get_consumer.return_value = None

        consumer = _make_consumer("statsite", perms=[])
        mock_create.return_value = (consumer, "iron_TEST_TOKEN_abc123")

        fake = FakePrompter(["1", "statsite", "Stats dashboard", "1,3", "y", "", "7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        mock_create.assert_awaited_once()
        args, kwargs = mock_create.call_args
        self.assertEqual(args[1], "statsite")
        self.assertEqual(set(kwargs["perms"]), {"ingots:read", "members:read"})
        self.assertEqual(kwargs["description"], "Stats dashboard")
        self.assertIn("iron_TEST_TOKEN_abc123", buf.getvalue())

    def test_create_aborts_on_no_at_confirm(
        self,
        mock_known_perm_options,
        mock_create,
        mock_get_consumer,
        mock_prompter_cls,
        mock_db,
    ):
        from manage_api_consumers import main

        mock_known_perm_options.return_value = [("ingots:read", "Read ingots")]
        mock_get_consumer.return_value = None

        fake = FakePrompter(["1", "ghost", "", "1", "n", "", "7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        with redirect_stdout(io.StringIO()):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        mock_create.assert_not_called()


@patch("manage_api_consumers.db")
@patch("manage_api_consumers.Prompter")
@patch("manage_api_consumers.set_perms")
@patch("manage_api_consumers.list_consumers")
@patch("manage_api_consumers.known_perm_options")
class TestInteractiveChangePerms(unittest.TestCase):
    def test_grant_via_custom_toggle(
        self,
        mock_known_perm_options,
        mock_list_consumers,
        mock_set_perms,
        mock_prompter_cls,
        mock_db,
    ):
        from manage_api_consumers import main

        mock_known_perm_options.return_value = [
            ("ingots:read", "Read ingots"),
            ("members:list", "List members"),
        ]
        mock_list_consumers.return_value = [
            _make_consumer("statsite", perms=["members:list"]),
        ]
        updated = _make_consumer("statsite", perms=["members:list", "ingots:read"])
        mock_set_perms.return_value = updated

        fake = FakePrompter(["2", "1", "3", "1", "y", "", "7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        with redirect_stdout(io.StringIO()):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        mock_set_perms.assert_awaited_once()
        args, _ = mock_set_perms.call_args
        self.assertEqual(args[1], "statsite")
        self.assertEqual(set(args[2]), {"members:list", "ingots:read"})

    def test_revoke_via_custom_toggle(
        self,
        mock_known_perm_options,
        mock_list_consumers,
        mock_set_perms,
        mock_prompter_cls,
        mock_db,
    ):
        from manage_api_consumers import main

        mock_known_perm_options.return_value = [
            ("ingots:read", "Read ingots"),
            ("members:list", "List members"),
        ]
        mock_list_consumers.return_value = [
            _make_consumer("statsite", perms=["members:list", "ingots:read"]),
        ]
        updated = _make_consumer("statsite", perms=["members:list"])
        mock_set_perms.return_value = updated

        fake = FakePrompter(["2", "1", "3", "1", "y", "", "7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        with redirect_stdout(io.StringIO()):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        mock_set_perms.assert_awaited_once()
        args, _ = mock_set_perms.call_args
        self.assertEqual(args[1], "statsite")
        self.assertEqual(args[2], ["members:list"])


@patch("manage_api_consumers.db")
@patch("manage_api_consumers.Prompter")
@patch("manage_api_consumers.list_consumers")
class TestInteractiveMenuValidation(unittest.TestCase):
    def test_reprompts_on_invalid_top_menu(
        self, mock_list_consumers, mock_prompter_cls, mock_db
    ):
        from manage_api_consumers import main

        mock_list_consumers.return_value = []

        fake = FakePrompter(["99", "", "7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        with redirect_stdout(io.StringIO()):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        menu_prompts = [c for c in fake.calls if c[0] == "menu"]
        self.assertEqual(len(menu_prompts), 2)

    def test_exits_cleanly_on_quit(
        self, mock_list_consumers, mock_prompter_cls, mock_db
    ):
        from manage_api_consumers import main

        mock_list_consumers.return_value = []

        fake = FakePrompter(["7"])
        mock_prompter_cls.return_value = fake

        _patched_db_with_session(mock_db)

        with redirect_stdout(io.StringIO()):
            rc = main(["interactive"])

        self.assertEqual(rc, 0)
        self.assertEqual(len([c for c in fake.calls if c[0] == "menu"]), 1)
