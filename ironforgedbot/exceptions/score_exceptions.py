class HiscoresError(Exception):
    def __init__(
        self,
        message="Error response from the hiscores.",
    ):
        self.message = message
        super().__init__(self.message)


class HiscoresNotFound(Exception):
    def __init__(
        self,
        message="Player not found on the hiscores.",
    ):
        self.message = message
        super().__init__(self.message)
