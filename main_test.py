from parameterized import parameterized
import unittest

import main


def hiscores():
    """Hiscores constant for testing.

    Called as a function to prevent unexpected
    mutations between tests affecting output.

    Equates to scores:
        skills: 1249
        activities: 370
    """
    scores = [
        '882108,80,2030525',
        '857788,80,1986799',
        '869033,89,5049503',
        '882768,88,4792127',
        '982705,84,3177495',
        '703316,73,1084703',
        '753632,88,4757030',
        '609025,83,2906155',
        '196899,92,6929160',
        '580031,80,2123851',
        '466486,82,2503585',
        '78469,99,13512762',
        '283455,86,3729682',
        '345314,81,2206940',
        '305414,83,2729908',
        '532877,73,1026949',
        '292822,80,2057879',
        '314157,81,2341976',
        '719672,77,1524934',
        '567075,80,1993041',
        '210281,81,2282874',
        '432457,76,1375258',
        '152887,86,3607578',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '39833,797',
        '6205,387',
        '22976,200',
        '76935,170',
        '407582,34',
        '600606,1',
        '181388,5',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '40995,274',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '48111,668',
        '5491,111',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '198739,168',
        '-1,-1',
        '73743,25',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '349220,18',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '198803,6',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '60281,190',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '-1,-1',
        '245562,405',
        '-1,-1',
        '-1,-1',
        ''
    ]
    return scores


class TestIronForgedBot(unittest.TestCase):

    @parameterized.expand([
        ({'GUILDID': 'bleep', 'BOT_TOKEN': 'bloop'}, True),
        ({'GUILDID': 'bleep'}, False),
        ({'BOT_TOKEN': 'bloop'}, False),
    ])
    def test_validate_initial_config(self, config, expected):
        self.assertEqual(main.validate_initial_config(config), expected)

    def test_do_score(self):
        expected = """johnnycache has 1619
Points from skills: 1249
Points from minigames & bossing: 370"""

        self.assertEqual(
            main.do_score('johnnycache', hiscores()),
            expected)


    def test_do_breakdown(self):
        expected_message = 'Total Points for johnnycache: 1619\n'
        expected_breakdown = """---Points from Skills---
Attack: 20
Defence: 19
Strength: 50
Hitpoints: 47
Ranged: 31
Prayer: 30
Magic: 47
Cooking: 29
Woodcutting: 138
Fletching: 21
Fishing: 50
Firemaking: 131
Crafting: 106
Smithing: 44
Mining: 90
Herblore: 41
Agility: 68
Thieving: 23
Slayer: 50
Farming: 39
Runecraft: 76
Hunter: 27
Construction: 72
Total Skill Points: 1249 (77.15% of total)

---Points from Minigames & Bossing---
Clue Scrolls (beginner): 38
Clue Scrolls (easy): 40
Clue Scrolls (medium): 51
Clue Scrolls (hard): 17
Clue Scrolls (elite): 1
Clue Scrolls (master): 10
Rifts closed: 39
Barrows Chests: 44
Bryophyta: 37
Dagannoth Rex: 2
Hespori: 22
Obor: 2
Tempoross: 27
Wintertodt: 40
Total Minigame & Bossing Points: 370 (22.85% of total)

Total Points: 1619
"""

        self.assertEqual(
            main.do_breakdown('johnnycache', hiscores()),
            (expected_message, expected_breakdown))

