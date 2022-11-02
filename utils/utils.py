from enum import IntEnum
import streamlit as st
from dataclasses import dataclass

from prisma.models import LeagueMatch


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


@dataclass
class InfoMatch:
    score: tuple
    possession: tuple
    action_zone: tuple


def get_info_match(match: LeagueMatch) -> InfoMatch:
    if match.defwin == 1:
        return InfoMatch((5, 0), (0, 0), (0, 0))
    elif match.defwin == 2:
        return InfoMatch((0, 5), (0, 0), (0, 0))
    if len(match.periods) == 0:
        return InfoMatch((-1, -1), (0, 0), (0, 0))
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
