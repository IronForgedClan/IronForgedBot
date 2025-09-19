import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.services.score_service import ScoreService
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.models.score import ActivityScore, ScoreBreakdown, SkillScore
from ironforgedbot.common.ranks import RANK


class TestScoreService(unittest.IsolatedAsyncioTestCase):
    """Test cases for ScoreService class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_http = AsyncMock()
        self.score_service = ScoreService(self.mock_http)

        self.sample_skills_data = [
            {"id": 0, "name": "Overall", "rank": 73537, "level": 2269, "xp": 431062657},
            {"id": 1, "name": "Attack", "rank": 230259, "level": 99, "xp": 14871752},
            {"id": 2, "name": "Defence", "rank": 280185, "level": 99, "xp": 13415365},
            {"id": 17, "name": "Agility", "rank": 126508, "level": 95, "xp": 9243572},
        ]

        self.sample_activities_data = [
            {"id": 71, "name": "Theatre of Blood", "rank": -1, "score": -1},
            {"id": 29, "name": "Chambers of Xeric", "rank": -1, "score": -1},
            {"id": 85, "name": "Zulrah", "rank": 331152, "score": 175},
            {"id": 6, "name": "Clue Scrolls (all)", "rank": 4743, "score": 3570},
            {"id": 19, "name": "Abyssal Sire", "rank": 43106, "score": 747},
        ]

        self.sample_response_data = {
            "skills": self.sample_skills_data,
            "activities": self.sample_activities_data,
        }

        self.sample_skills_config = [
            {
                "name": "Attack",
                "display_order": 1,
                "emoji_key": "Attack",
                "xp_per_point": 100000,
                "xp_per_point_post_99": 300000,
            },
            {
                "name": "Defence",
                "display_order": 7,
                "emoji_key": "Defence",
                "xp_per_point": 100000,
                "xp_per_point_post_99": 300000,
            },
            {
                "name": "Agility",
                "display_order": 5,
                "emoji_key": "Agility",
                "xp_per_point": 30000,
                "xp_per_point_post_99": 90000,
            },
        ]

        self.sample_raids_config = [
            {
                "name": "Theatre of Blood",
                "display_order": 3,
                "emoji_key": "Theatre_of_Blood",
                "kc_per_point": 0.4,
            },
            {
                "name": "Chambers of Xeric",
                "display_order": 1,
                "emoji_key": "Chambers_of_Xeric",
                "kc_per_point": 0.8,
            },
        ]

        self.sample_bosses_config = [
            {
                "name": "Zulrah",
                "display_order": 59,
                "emoji_key": "Zulrah",
                "kc_per_point": 12,
            },
            {
                "name": "Abyssal Sire",
                "display_order": 2,
                "emoji_key": "Abyssal_Sire",
                "kc_per_point": 10,
            },
        ]

        self.sample_clues_config = [
            {
                "name": "Clue Scrolls (beginner)",
                "display_name": "Beginner",
                "display_order": 1,
                "emoji_key": "Beginner_Clue",
                "kc_per_point": 10,
            },
            {
                "name": "Clue Scrolls (easy)",
                "display_name": "Easy",
                "display_order": 2,
                "emoji_key": "Easy_Clue",
                "kc_per_point": 5,
            },
        ]

    def test_init(self):
        """Test ScoreService initialization"""
        self.assertEqual(self.score_service.http, self.mock_http)
        self.assertIn("hiscore_oldschool", self.score_service.hiscores_url)
        self.assertEqual(self.score_service.level_99_xp, 13_034_431)

    @patch("ironforgedbot.services.score_service.SCORE_CACHE")
    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    async def test_get_player_score_cache_hit(self, mock_normalize, mock_cache):
        """Test get_player_score returns cached data when available"""
        player_name = "TestPlayer"
        mock_normalize.return_value = player_name

        mock_breakdown = ScoreBreakdown(skills=[], clues=[], raids=[], bosses=[])
        mock_cache.get = AsyncMock(return_value=mock_breakdown)

        result = await self.score_service.get_player_score(player_name)

        self.assertEqual(result, mock_breakdown)
        mock_cache.get.assert_called_once_with(player_name)
        self.mock_http.get.assert_not_called()

    @patch("ironforgedbot.services.score_service.SCORE_CACHE")
    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    @patch("ironforgedbot.storage.data.SKILLS")
    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.RAIDS")
    @patch("ironforgedbot.storage.data.BOSSES")
    async def test_get_player_score_cache_miss_with_valid_response(
        self,
        mock_bosses,
        mock_raids,
        mock_clues,
        mock_skills,
        mock_normalize,
        mock_cache,
    ):
        """Test get_player_score fetches and caches data when cache miss"""
        player_name = "TestPlayer"
        mock_normalize.return_value = player_name
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()

        mock_skills.__iter__.return_value = iter(self.sample_skills_config)
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter(self.sample_bosses_config)

        self.mock_http.get.return_value = {
            "status": 200,
            "body": self.sample_response_data,
        }

        result = await self.score_service.get_player_score(player_name)

        self.assertIsInstance(result, ScoreBreakdown)
        self.assertIsInstance(result.skills, list)
        self.assertIsInstance(result.clues, list)
        self.assertIsInstance(result.raids, list)
        self.assertIsInstance(result.bosses, list)
        mock_cache.set.assert_called_once()
        self.mock_http.get.assert_called_once()

    @patch("ironforgedbot.services.score_service.SCORE_CACHE")
    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    async def test_get_player_score_404_error(self, mock_normalize, mock_cache):
        """Test get_player_score raises HiscoresNotFound for 404 response"""
        player_name = "NonExistentPlayer"
        mock_normalize.return_value = player_name
        mock_cache.get = AsyncMock(return_value=None)

        self.mock_http.get.return_value = {"status": 404}

        with self.assertRaises(HiscoresNotFound):
            await self.score_service.get_player_score(player_name)

    @patch("ironforgedbot.services.score_service.SCORE_CACHE")
    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    async def test_get_player_score_server_error(self, mock_normalize, mock_cache):
        """Test get_player_score raises HiscoresError for server errors"""
        player_name = "TestPlayer"
        mock_normalize.return_value = player_name
        mock_cache.get = AsyncMock(return_value=None)

        self.mock_http.get.return_value = {"status": 500}

        with self.assertRaises(HiscoresError) as context:
            await self.score_service.get_player_score(player_name)

        self.assertIn("Unexpected response code 500", str(context.exception))

    @patch("ironforgedbot.services.score_service.SCORE_CACHE")
    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    @patch("ironforgedbot.storage.data.SKILLS")
    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.RAIDS")
    @patch("ironforgedbot.storage.data.BOSSES")
    async def test_get_player_score_bypass_cache(
        self,
        mock_bosses,
        mock_raids,
        mock_clues,
        mock_skills,
        mock_normalize,
        mock_cache,
    ):
        """Test get_player_score bypasses cache when bypass_cache=True"""
        player_name = "TestPlayer"
        mock_normalize.return_value = player_name
        mock_breakdown = ScoreBreakdown(skills=[], clues=[], raids=[], bosses=[])
        mock_cache.get = AsyncMock(return_value=mock_breakdown)
        mock_cache.set = AsyncMock()

        mock_skills.__iter__.return_value = iter([])
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter([])

        self.mock_http.get.return_value = {
            "status": 200,
            "body": {"skills": [], "activities": []},
        }

        result = await self.score_service.get_player_score(
            player_name, bypass_cache=True
        )

        self.mock_http.get.assert_called_once()
        mock_cache.set.assert_called_once()

    def test_process_skills_no_skills_data(self):
        """Test _process_skills raises RuntimeError when SKILLS is None"""
        with patch("ironforgedbot.services.score_service.SKILLS", None):
            with self.assertRaises(RuntimeError) as context:
                self.score_service._process_skills(self.sample_response_data)

            self.assertEqual(str(context.exception), "Unable to read skills data")

    def test_process_skills_none_score_data(self):
        """Test _process_skills raises RuntimeError when score_data is None"""
        with self.assertRaises(RuntimeError):
            self.score_service._process_skills(None)

    def test_process_skills_none_skills_in_data(self):
        """Test _process_skills raises RuntimeError when skills key is None"""
        with self.assertRaises(RuntimeError):
            self.score_service._process_skills({"skills": None})

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_valid_data(self, mock_skills):
        """Test _process_skills with valid skill data"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        result = self.score_service._process_skills(self.sample_response_data)

        self.assertIsInstance(result, list)
        skill_names = [skill.name for skill in result]
        self.assertNotIn("Overall", skill_names)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_skips_overall(self, mock_skills):
        """Test _process_skills skips Overall skill"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        result = self.score_service._process_skills(self.sample_response_data)

        skill_names = [skill.name for skill in result]
        self.assertNotIn("Overall", skill_names)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_handles_missing_skill(self, mock_skills):
        """Test _process_skills handles skills not in SKILLS config"""
        mock_skills.__iter__.return_value = iter([])  # Empty config

        test_data = {
            "skills": [
                {
                    "id": 0,
                    "name": "Overall",
                    "rank": 73537,
                    "level": 2269,
                    "xp": 431062657,
                },
                {
                    "id": 999,
                    "name": "NonexistentSkill",
                    "rank": 1,
                    "level": 50,
                    "xp": 100000,
                },
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(result, [])

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_level_below_99(self, mock_skills):
        """Test _process_skills calculates points correctly for level < 99"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [
                {"id": 2, "name": "Defence", "rank": 280185, "level": 85, "xp": 3500000}
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]
        self.assertEqual(skill.name, "Defence")
        self.assertEqual(skill.level, 85)
        self.assertEqual(skill.xp, 3500000)
        # Points = xp / xp_per_point = 3500000 / 100000 = 35
        self.assertEqual(skill.points, 35)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_level_99_plus(self, mock_skills):
        """Test _process_skills calculates points correctly for level >= 99"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [
                {"id": 1, "name": "Attack", "rank": 230259, "level": 99, "xp": 15000000}
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]
        self.assertEqual(skill.name, "Attack")
        self.assertEqual(skill.level, 99)
        self.assertEqual(skill.xp, 15000000)

        # Points calculation for 99+:
        # Base points: 13034431 / 100000 = 130
        # Post-99 points: (15000000 - 13034431) / 300000 = 6
        # Total: 130 + 6 = 136
        expected_points = int(13034431 / 100000) + int((15000000 - 13034431) / 300000)
        self.assertEqual(skill.points, expected_points)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_minimum_level_and_xp(self, mock_skills):
        """Test _process_skills handles minimum level and XP values"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [{"id": 1, "name": "Attack", "rank": 1, "level": 0, "xp": -100}]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]
        self.assertEqual(skill.level, 1)  # Should be minimum 1
        self.assertEqual(skill.xp, 0)  # Should be minimum 0
        self.assertEqual(skill.points, 0)  # 0 XP should give 0 points

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_creates_correct_skillscore_objects(self, mock_skills):
        """Test _process_skills creates SkillScore objects with correct attributes"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [
                {"id": 1, "name": "Attack", "rank": 230259, "level": 70, "xp": 800000}
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]

        self.assertIsInstance(skill, SkillScore)
        self.assertEqual(skill.name, "Attack")
        self.assertEqual(skill.display_name, None)  # Set to None in code
        self.assertEqual(skill.display_order, 1)
        self.assertEqual(skill.emoji_key, "Attack")
        self.assertEqual(skill.level, 70)
        self.assertEqual(skill.xp, 800000)
        self.assertEqual(skill.points, 8)  # 800000 / 100000

    def test_process_activities_no_activity_data(self):
        """Test _process_activities raises RuntimeError when activity data is None"""
        with patch("ironforgedbot.services.score_service.CLUES", None), patch(
            "ironforgedbot.services.score_service.BOSSES", None
        ), patch("ironforgedbot.services.score_service.RAIDS", None):
            with self.assertRaises(RuntimeError) as context:
                self.score_service._process_activities(self.sample_response_data)

            self.assertEqual(str(context.exception), "Unable to read activity data")

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_valid_data(self, mock_raids, mock_bosses, mock_clues):
        """Test _process_activities with valid activity data"""
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter(self.sample_bosses_config)

        clues, raids, bosses = self.score_service._process_activities(
            self.sample_response_data
        )

        self.assertIsInstance(clues, list)
        self.assertIsInstance(raids, list)
        self.assertIsInstance(bosses, list)

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_boss_zero_kc_filtered(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities filters out bosses with 0 KC"""
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter(self.sample_bosses_config)

        test_data = {
            "activities": [
                {
                    "id": 85,
                    "name": "Zulrah",
                    "rank": -1,
                    "score": 0,
                }
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(bosses), 0)  # Should be filtered out

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_negative_kc_becomes_zero(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles negative KC by making it 0"""
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {
                    "id": 7,
                    "name": "Clue Scrolls (beginner)",
                    "rank": 253,
                    "score": -50,
                }  # Negative score
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].kc, 0)
        self.assertEqual(clues[0].points, 0)

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_display_name_handling(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles display_name correctly"""
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {"id": 71, "name": "Theatre of Blood", "rank": -1, "score": 150}
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(raids), 1)
        self.assertEqual(raids[0].display_name, None)

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_creates_correct_activityscore_objects(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities creates ActivityScore objects with correct attributes"""
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {"id": 7, "name": "Clue Scrolls (beginner)", "rank": 253, "score": 1000}
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(clues), 1)
        clue = clues[0]

        self.assertIsInstance(clue, ActivityScore)
        self.assertEqual(clue.name, "Clue Scrolls (beginner)")
        self.assertEqual(clue.display_name, "Beginner")  # From config
        self.assertEqual(clue.display_order, 1)
        self.assertEqual(clue.emoji_key, "Beginner_Clue")
        self.assertEqual(clue.kc, 1000)
        self.assertEqual(clue.points, 100)  # 1000 / 10

    @patch("ironforgedbot.services.score_service.normalize_discord_string")
    async def test_get_player_points_total(self, mock_normalize):
        """Test get_player_points_total calculates total correctly"""
        player_name = "TestPlayer"
        mock_normalize.return_value = player_name

        skill1 = SkillScore(
            name="Attack",
            display_name=None,
            display_order=1,
            emoji_key="attack",
            xp=1000000,
            level=80,
            points=100,
        )
        skill2 = SkillScore(
            name="Defence",
            display_name=None,
            display_order=2,
            emoji_key="defence",
            xp=2000000,
            level=90,
            points=200,
        )

        activity1 = ActivityScore(
            name="Zulrah",
            display_name=None,
            display_order=1,
            emoji_key="zulrah",
            kc=100,
            points=50,
        )
        activity2 = ActivityScore(
            name="CoX",
            display_name=None,
            display_order=2,
            emoji_key="cox",
            kc=150,
            points=75,
        )

        mock_breakdown = ScoreBreakdown(
            skills=[skill1, skill2], clues=[activity1], raids=[activity2], bosses=[]
        )

        with patch.object(
            self.score_service, "get_player_score", return_value=mock_breakdown
        ):
            result = await self.score_service.get_player_points_total(player_name)

            self.assertEqual(result, 425)  # 100 + 200 + 50 + 75

    @patch("ironforgedbot.services.score_service.get_rank_from_points")
    async def test_get_rank(self, mock_get_rank_from_points):
        """Test get_rank returns correct rank based on points"""
        player_name = "TestPlayer"
        mock_get_rank_from_points.return_value = "Dragon"

        with patch.object(
            self.score_service, "get_player_points_total", return_value=5000
        ) as mock_points:
            result = await self.score_service.get_rank(player_name)

            self.assertIsInstance(result, RANK)
            self.assertEqual(result.value, "Dragon")
            mock_points.assert_called_once_with(player_name)
            mock_get_rank_from_points.assert_called_once_with(points=5000)

    async def test_get_rank_runtime_error(self):
        """Test get_rank propagates RuntimeError from get_player_points_total"""
        player_name = "TestPlayer"

        with patch.object(
            self.score_service,
            "get_player_points_total",
            side_effect=RuntimeError("Test error"),
        ):
            with self.assertRaises(RuntimeError):
                await self.score_service.get_rank(player_name)

    def test_hiscores_url_format(self):
        """Test that hiscores URL is correctly formatted"""
        expected_url = (
            "https://secure.runescape.com/m=hiscore_oldschool/"
            "index_lite.json?player={rsn}"
        )
        self.assertEqual(self.score_service.hiscores_url, expected_url)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_with_string_level_and_xp(self, mock_skills):
        """Test _process_skills handles string values for level and XP"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [
                {
                    "id": 1,
                    "name": "Attack",
                    "rank": 230259,
                    "level": "70",
                    "xp": "800000",
                }  # String values
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]
        self.assertEqual(skill.level, 70)  # Should be converted to int
        self.assertEqual(skill.xp, 800000)  # Should be converted to int

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_with_string_score(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles string values for score"""
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {
                    "id": 7,
                    "name": "Clue Scrolls (beginner)",
                    "rank": 253,
                    "score": "1000",
                }
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(clues), 1)
        self.assertEqual(clues[0].kc, 1000)  # Should be converted to int

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_handles_negative_one_scores(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles -1 scores (unattempted activities)"""
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {
                    "id": 71,
                    "name": "Theatre of Blood",
                    "rank": -1,
                    "score": -1,
                }
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(raids), 1)
        self.assertEqual(raids[0].kc, 0)
        self.assertEqual(raids[0].points, 0)

    @patch("ironforgedbot.storage.data.SKILLS")
    def test_process_skills_with_very_high_xp(self, mock_skills):
        """Test _process_skills handles very high XP values correctly"""
        mock_skills.__iter__.return_value = iter(self.sample_skills_config)

        test_data = {
            "skills": [
                {
                    "id": 1,
                    "name": "Attack",
                    "rank": 230259,
                    "level": 99,
                    "xp": 25000000,
                }
            ]
        }

        result = self.score_service._process_skills(test_data)

        self.assertEqual(len(result), 1)
        skill = result[0]
        self.assertEqual(skill.name, "Attack")
        self.assertEqual(skill.level, 99)
        self.assertEqual(skill.xp, 25000000)

        # Points calculation for high XP:
        # Base points: 13034431 / 100000 = 130
        # Post-99 points: (25000000 - 13034431) / 300000 = 39
        # Total: 130 + 39 = 169
        expected_points = int(13034431 / 100000) + int((25000000 - 13034431) / 300000)
        self.assertEqual(skill.points, expected_points)

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_with_realistic_high_scores(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities with realistic high activity scores"""
        mock_clues.__iter__.return_value = iter(self.sample_clues_config)
        mock_raids.__iter__.return_value = iter([])
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {
                    "id": 7,
                    "name": "Clue Scrolls (beginner)",
                    "rank": 253,
                    "score": 3570,
                }
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(clues), 1)
        clue = clues[0]
        self.assertEqual(clue.kc, 3570)
        self.assertEqual(clue.points, 357)  # 3570 / 10

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_handles_negative_one_api_values(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles -1 values from API (unattempted activities)"""
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {
                    "id": 71,
                    "name": "Theatre of Blood",
                    "rank": -1,
                    "score": -1,
                }  # Unattempted activity
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(raids), 1)
        raid = raids[0]
        self.assertEqual(raid.kc, 0)  # max(-1, 0) = 0
        self.assertEqual(raid.points, 0)  # max(0 / 0.4, 0) = 0

    @patch("ironforgedbot.storage.data.CLUES")
    @patch("ironforgedbot.storage.data.BOSSES")
    @patch("ironforgedbot.storage.data.RAIDS")
    def test_process_activities_with_float_kc_per_point(
        self, mock_raids, mock_bosses, mock_clues
    ):
        """Test _process_activities handles float kc_per_point values correctly"""
        mock_clues.__iter__.return_value = iter([])
        mock_raids.__iter__.return_value = iter(self.sample_raids_config)
        mock_bosses.__iter__.return_value = iter([])

        test_data = {
            "activities": [
                {"id": 71, "name": "Theatre of Blood", "rank": 1000, "score": 150}
            ]
        }

        clues, raids, bosses = self.score_service._process_activities(test_data)

        self.assertEqual(len(raids), 1)
        raid = raids[0]
        self.assertEqual(raid.kc, 150)
        self.assertEqual(raid.points, 375)
