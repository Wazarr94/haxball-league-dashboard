from enum import IntEnum

LEAGUE_TITLE = "S3"
LEAGUE_NAME = "FUTLIFE"
TEAM_SIZE = 3
LEAGUE_TEAM_SIZE_MIN = 5
LEAGUE_TEAM_SIZE_MAX = 15
GAME_TIME = 5
CS_TIME_NECESSARY = GAME_TIME * 3 / 4
DEFWIN_SCORE = 5


class GamePosition(IntEnum):
    unknown = 0
    GK = 1
    AM = 2
    ST = 3
