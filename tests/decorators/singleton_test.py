import unittest

from ironforgedbot.decorators.singleton import singleton


@singleton
class TestSingleton:
    def __init__(self, value):
        self.value = value
        self.internal_state = {}

    async def set_value(self, key, value):
        self.internal_state[key] = value

    async def get_value(self, key):
        return self.internal_state.get(key, None)


class TestSingletonDecorator(unittest.IsolatedAsyncioTestCase):
    async def test_singleton_instance_creation(self):
        """Test that only one instance is created."""
        instance1 = await TestSingleton(10)
        instance2 = await TestSingleton(20)

        self.assertIs(instance1, instance2)

    async def test_singleton_internal_state(self):
        instance1 = await TestSingleton(10)
        await instance1.set_value("key1", "value")
        instance2 = await TestSingleton(20)

        value = await instance2.get_value("key1")

        self.assertEqual(value, "value")
        self.assertIs(instance1, instance2)

    async def test_singleton_instance_initialization(self):
        instance1 = await TestSingleton(10)
        instance2 = await TestSingleton(20)

        self.assertEqual(instance1.value, 10)
        self.assertEqual(instance1.value, instance2.value)
