from dataclasses import dataclass

import pandas as pd
import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch, LeagueTeam
from st_pages import add_indentation

from utils.data import (
    get_divisions,
    get_matches,
    init_connection,
)
from utils.utils import hide_streamlit_elements, get_info_match, get_unique_order

hide_streamlit_elements()
add_indentation()


@dataclass
class StandingTeam:
    name: str
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


def get_div_select(divisions: list[LeagueDivision]):
    col1, _ = st.columns([4, 10])
    div_name_list = [d.name for d in divisions]
    div_name_select = col1.selectbox("Division", div_name_list)
    div_select = [d for d in divisions if d.name == div_name_select][0]
    return div_select


def get_matchday_select(matches_list: list[LeagueMatch], division: LeagueDivision):
    matchday_options = get_unique_order(
        [m.matchday for m in matches_list if m.leagueDivisionId == division.id]
    )
    matchdays_values = range(len(matchday_options))

    matchdays_select = st.select_slider(
        "Matchdays",
        options=matchdays_values,
        value=(0, max(matchdays_values)),
        format_func=(lambda v: matchday_options[v]),
    )

    return matchdays_select


def build_match_db_team(
    match_list: list[LeagueMatch],
    team: LeagueTeam,
    matchdays_select: tuple[int],
):
    md_list = get_unique_order([m.matchday for m in match_list])
    md_dict = {v: i for i, v in enumerate(md_list)}
    standing_team = StandingTeam(
        name=team.name,
        games=0,
        wins=0,
        draws=0,
        losses=0,
        defwins=0,
        goals_scored=0,
        goals_conceded=0,
    )
    for m in match_list:
        info_match = get_info_match(m)
        if info_match.score[0] == -1 or len(m.detail) < 2:
            continue
        if m.detail[0].team.name != team.name and m.detail[1].team.name != team.name:
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
    standings = []
    for team in division.teams:
        standing = build_match_db_team(match_list, team, matchdays_select)
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
    return standings_df


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    divisions_list = get_divisions(db)

    st.write("# S10 standings")

    div_select = get_div_select(divisions_list)
    matchdays_select = get_matchday_select(matches_list, div_select)

    info_matches = build_match_db(matches_list, div_select, matchdays_select)
    height_df = 38 * len(info_matches)
    st.dataframe(info_matches, use_container_width=True, height=height_df)


if __name__ == "__main__":
    main()
