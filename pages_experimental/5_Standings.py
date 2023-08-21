from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st
from st_pages import add_indentation

from generated.prisma import Prisma
from generated.prisma.models import LeagueDivision, LeagueMatch, LeagueTeam
from utils.constants import LEAGUE_TITLE
from utils.data import (
    get_divisions,
    get_matches,
    init_connection,
)
from utils.utils import get_info_match, get_unique_order, hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


@dataclass
class StandingTeam:
    name: str
    initials: str
    games: int
    wins: int
    draws: int
    losses: int
    defwins: int
    goals_scored: int
    goals_conceded: int

    @property
    def points(self):
        return 3 * self.wins + self.draws

    @property
    def differential(self):
        return self.goals_scored - self.goals_conceded


def get_div_select(divisions: list[LeagueDivision]) -> Optional[LeagueDivision]:
    col1, _ = st.columns([4, 10])
    div_select = st.selectbox("Division", divisions, format_func=lambda d: d.name)
    return div_select


def format_matchday(value: int, matchday_options: list[int], empty: bool):
    if empty:
        return value

    return matchday_options[value]


def get_matchday_select(matches_list: list[LeagueMatch], division: LeagueDivision):
    matchday_options = get_unique_order(
        [m.matchday for m in matches_list if m.leagueDivisionId == division.id]
    )
    if len(matchday_options) == 0:
        matchdays_values = (1, 1)
        matchdays_values_opt = (1, 1)
        empty = True
    else:
        matchdays_values = range(len(matchday_options))
        matchdays_values_opt = (0, max(matchdays_values))
        empty = False

    matchdays_select = st.select_slider(
        "Matchdays",
        options=matchdays_values,
        value=matchdays_values_opt,
        format_func=lambda v: format_matchday(v, matchday_options, empty),
    )

    return matchdays_select


def build_match_db_team(
    match_list: list[LeagueMatch],
    division: LeagueDivision,
    team: LeagueTeam,
    matchdays_select: tuple[int, int],
):
    matches_div = [m for m in match_list if m.leagueDivisionId == division.id]
    md_list = get_unique_order([m.matchday for m in matches_div])
    md_dict = {v: i for i, v in enumerate(md_list)}
    standing_team = StandingTeam(
        name=team.name,
        initials=team.initials,
        games=0,
        wins=0,
        draws=0,
        losses=0,
        defwins=0,
        goals_scored=0,
        goals_conceded=0,
    )
    for m in matches_div:
        info_match = get_info_match(m)
        if info_match.score[0] == -1 or len(m.detail) < 2:
            continue
        if not any([md.team.name == team.name for md in m.detail]):
            continue
        if (
            md_dict[m.matchday] < matchdays_select[0]
            or md_dict[m.matchday] > matchdays_select[1]
        ):
            continue

        standing_team.games += 1
        if m.detail[1].team.id == team.id:
            score_team = info_match.score[1]
            score_opponent = info_match.score[0]
            if m.defwin == 1:
                standing_team.defwins += 1
        else:
            score_team = info_match.score[0]
            score_opponent = info_match.score[1]
            if m.defwin == 2:
                standing_team.defwins += 1

        if score_team > score_opponent:
            standing_team.wins += 1
        elif score_team == score_opponent:
            standing_team.draws += 1
        else:
            standing_team.losses += 1

        standing_team.goals_scored += score_team
        standing_team.goals_conceded += score_opponent

    return standing_team


def build_match_db(
    match_list: list[LeagueMatch],
    division: LeagueDivision,
    matchdays_select: tuple[int],
):
    if len(division.teams) == 0:
        return None

    standings = []
    for team_div in division.teams:
        standing = build_match_db_team(
            match_list, division, team_div.team, matchdays_select
        )
        obj_standing = {
            "team": standing.name,
            "GP": standing.games,
            "W": standing.wins,
            "D": standing.draws,
            "L": standing.losses,
            "PTS": standing.points,
            "DEF": standing.defwins,
            "GF": standing.goals_scored,
            "GA": standing.goals_conceded,
            "DIFF": standing.differential,
        }
        standings.append(obj_standing)
    standings_df = pd.DataFrame(
        [
            dict(s)
            for s in sorted(
                standings, key=lambda s: (s["PTS"], s["DIFF"], s["GF"]), reverse=True
            )
        ]
    )
    standings_df.index = standings_df.index + 1
    return standings_df


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    divisions_list = get_divisions(db)

    st.write(f"# {LEAGUE_TITLE} standings")

    div_select = get_div_select(divisions_list)
    matchdays_select = get_matchday_select(matches_list, div_select)

    if div_select is None:
        st.error("No matches found")
        return

    info_matches = build_match_db(matches_list, div_select, matchdays_select)
    if info_matches is None:
        st.error("No teams found")
        return

    st.dataframe(info_matches)


if __name__ == "__main__":
    main()
