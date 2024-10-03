class BotState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BotState, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.is_shutting_down = False


state = BotState()
