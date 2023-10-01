import math
from dataclasses import dataclass
from enum import IntEnum
from itertools import groupby
from statistics import mode
from typing import Literal, Optional

import streamlit as st

from generated.prisma.models import (
    LeagueMatch,
    LeaguePlayer,
    LeagueTeam,
    Period,
    PlayerStats,
)
from utils.constants import CS_TIME_NECESSARY, DEFWIN_SCORE, GAME_TIME


class GamePosition(IntEnum):
    unknown = 0
    GK = 1
    DM = 2
    AM = 3
    ST = 4


def hide_streamlit_elements() -> st._DeltaGenerator:
    hide_st_style = """
              <style>
              footer {visibility: hidden;}
              </style>
              """
    return st.markdown(hide_st_style, unsafe_allow_html=True)


def get_unique_order(lst: list):
    return list(dict.fromkeys(lst))


@dataclass
class InfoMatch:
    score: tuple
    possession: tuple
    action_zone: tuple


def get_info_match(match: LeagueMatch) -> InfoMatch:
    if match.defwin == 1:
        return InfoMatch((DEFWIN_SCORE, 0), (0, 0), (0, 0))
    elif match.defwin == 2:
        return InfoMatch((0, DEFWIN_SCORE), (0, 0), (0, 0))
    if match.defwin == 3 or len(match.periods) == 0:
        return InfoMatch((-5, -5), (0, 0), (0, 0))
    md_1 = match.detail[0]
    score_1 = sum([p.scoreRed for p in match.periods[::2]]) + sum(
        [p.scoreBlue for p in match.periods[1::2]]
    )
    score_2 = sum([p.scoreBlue for p in match.periods[::2]]) + sum(
        [p.scoreRed for p in match.periods[1::2]]
    )
    poss_1 = sum([p.possessionRed for p in match.periods[::2]]) + sum(
        [p.possessionBlue for p in match.periods[1::2]]
    )
    poss_2 = sum([p.possessionBlue for p in match.periods[::2]]) + sum(
        [p.possessionRed for p in match.periods[1::2]]
    )
    action_1 = sum([p.actionZoneRed for p in match.periods[::2]]) + sum(
        [p.actionZoneBlue for p in match.periods[1::2]]
    )
    action_2 = sum([p.actionZoneBlue for p in match.periods[::2]]) + sum(
        [p.actionZoneRed for p in match.periods[1::2]]
    )
    score = [score_1, score_2] if md_1.startsRed else [score_2, score_1]
    possession = [poss_1, poss_2] if md_1.startsRed else [poss_2, poss_1]
    action_zone = [action_1, action_2] if md_1.startsRed else [action_2, action_1]
    score[0] += match.addRed
    score[1] += match.addBlue
    return InfoMatch(tuple(score), tuple(possession), tuple(action_zone))


def is_match_played(match: LeagueMatch):
    if match.addBlue != 0 or match.addRed != 0 or match.defwin != 0:
        return True
    if match.periods is not None and len(match.periods) > 0:
        return True
    return False


@dataclass
class PlayerStatSheet:
    player: Optional[LeaguePlayer]
    player_name: str
    team: LeagueTeam
    is_red: bool
    stats: PlayerStats
    cs: int


def get_statsheet_list(
    players: list[LeaguePlayer], match: LeagueMatch
) -> list[PlayerStatSheet]:
    if len(match.detail) < 2:
        return []
    detail_1, detail_2 = match.detail[0], match.detail[1]
    ps_list: list[PlayerStatSheet] = []
    for i, period in enumerate(match.periods):
        period_stats: Period = period
        for ps in period_stats.PlayerStats:
            pname_period = ps.Player.name
            if ps.Player.team == 1:
                lp_name = pname_period.strip().lower()
                if i % 2 == 0:
                    team = detail_1.team if detail_1.startsRed else detail_2.team
                else:
                    team = detail_2.team if detail_1.startsRed else detail_1.team
                lp_list = [
                    p for p in players if lp_name in [n.lower() for n in p.nicks]
                ]
                if len(lp_list) > 0:
                    lp = lp_list[0]
                    lp_name = lp.name
                else:
                    lp = None
                    lp_name = f"{lp_name} (unknown)"
                stat_sheet = PlayerStatSheet(
                    player=lp,
                    player_name=lp_name,
                    team=team,
                    is_red=True,
                    stats=ps,
                    cs=getCS(ps, period, 1),
                )
                ps_list.append(stat_sheet)
            elif ps.Player.team == 2:
                lp_name = pname_period.strip().lower()
                if i % 2 == 0:
                    team = detail_2.team if detail_1.startsRed else detail_1.team
                else:
                    team = detail_1.team if detail_1.startsRed else detail_2.team
                lp_list = [
                    p for p in players if lp_name in [n.lower() for n in p.nicks]
                ]
                if len(lp_list) > 0:
                    lp = lp_list[0]
                    lp_name = lp.name
                else:
                    lp = None
                    lp_name = f"{lp_name} (unknown)"
                stat_sheet = PlayerStatSheet(
                    player=lp,
                    player_name=lp_name,
                    team=team,
                    is_red=False,
                    stats=ps,
                    cs=getCS(ps, period, 1),
                )
                ps_list.append(stat_sheet)
    return ps_list


def sum_sheets(player_sheets: list[PlayerStatSheet]):
    player_sheets.sort(key=lambda x: x.player_name)
    gpd = [list(ps) for _, ps in groupby(player_sheets, key=lambda p: p.player_name)]
    final_player_sheets: list[PlayerStatSheet] = []
    for group in gpd:
        goals = sum([pss.stats.goals for pss in group])
        assists = sum([pss.stats.assists for pss in group])
        gametime = sum([min(pss.stats.gametime, GAME_TIME * 60) for pss in group])
        secondaryAssists = sum([pss.stats.secondaryAssists for pss in group])
        tertiaryAssists = sum([pss.stats.tertiaryAssists for pss in group])
        saves = sum([pss.stats.saves for pss in group])
        clears = sum([pss.stats.clears for pss in group])
        interceptions = sum([pss.stats.interceptions for pss in group])
        shots = sum([pss.stats.shots for pss in group])
        shotsTarget = sum([pss.stats.shotsTarget for pss in group])
        duels = sum([pss.stats.duels for pss in group])
        reboundDribbles = sum([pss.stats.reboundDribbles for pss in group])
        passesAttempted = sum([pss.stats.passesAttempted for pss in group])
        passesSuccessful = sum([pss.stats.passesSuccessful for pss in group])
        touches = sum([pss.stats.touches for pss in group])
        kicks = sum([pss.stats.kicks for pss in group])
        gamePosition = mode([pss.stats.gamePosition for pss in group])
        ownGoals = sum([pss.stats.ownGoals for pss in group])
        goalsScoredTeam = sum([pss.stats.goalsScoredTeam for pss in group])
        goalsConcededTeam = sum([pss.stats.goalsConcededTeam for pss in group])
        averagePosXList = [
            pss.stats.averagePosX if pss.is_red else -pss.stats.averagePosX
            for pss in group
        ]
        averagePosX = sum(averagePosXList) / len(averagePosXList)
        averagePosYList = [pss.stats.averagePosY for pss in group]
        averagePosY = sum(averagePosYList) / len(averagePosYList)
        cleansheet = sum([pss.cs for pss in group])

        final_ps = PlayerStats(
            id="",
            period=None,
            periodId=1,
            Player=None,
            playerId="",
            goals=goals,
            assists=assists,
            gametime=gametime,
            averagePosX=averagePosX,
            averagePosY=averagePosY,
            clears=clears,
            duels=duels,
            gamePosition=gamePosition,
            goalsConcededTeam=goalsConcededTeam,
            goalsScoredTeam=goalsScoredTeam,
            interceptions=interceptions,
            kicks=kicks,
            ownGoals=ownGoals,
            passesAttempted=passesAttempted,
            passesSuccessful=passesSuccessful,
            reboundDribbles=reboundDribbles,
            saves=saves,
            secondaryAssists=secondaryAssists,
            shots=shots,
            shotsTarget=shotsTarget,
            tertiaryAssists=tertiaryAssists,
            touches=touches,
        )
        final_pss = PlayerStatSheet(
            player=group[0].player,
            player_name=group[0].player_name,
            team=group[0].team,
            is_red=group[0].is_red,
            stats=final_ps,
            cs=cleansheet,
        )
        final_player_sheets.append(final_pss)
    return final_player_sheets


def getCS(stats_player: PlayerStats, period: Period, team: Literal[1, 2]):
    if (
        stats_player.gamePosition == GamePosition.GK
        and stats_player.gametime > CS_TIME_NECESSARY * 60
    ):
        if period.scoreRed == 0 and team == 2:
            return 1
        if period.scoreBlue == 0 and team == 1:
            return 1
    return 0


def display_gametime(gametime: float) -> str:
    minutes = math.floor(gametime / 60)
    seconds = math.floor(gametime % 60)
    if minutes == 0:
        return f"{seconds}s"
    if seconds == 0:
        return f"{minutes}m"
    return f"{minutes}m{seconds}s"


def display_pass_success(v):
    if math.isnan(v):
        return "0.0%"
    return f"{100 * v:.1f}%"
