from typing import Optional

import pandas as pd
import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch, LeagueTeam
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder

from utils.data import get_divisions, get_matches, get_teams, init_connection
from utils.utils import get_info_match, hide_streamlit_elements, get_unique_order

hide_streamlit_elements()


def filter_matches(
    matches: list[LeagueMatch],
    team: Optional[LeagueTeam],
    division: LeagueDivision,
    matchday_select: Optional[str],
):
    match_list_filter = []
    for m in matches:
        if matchday_select is not None and m.matchday != matchday_select:
            continue
        if m.LeagueDivision.name != division:
            continue
        if team is None or any([md.team.name == team for md in m.detail]):
            match_list_filter.append(m)
    return match_list_filter


def build_match_db(match_list: list[LeagueMatch]):
    object_list = []
    for m in match_list:
        info_match = get_info_match(m)
        score = f"{info_match.score[0]}-{info_match.score[1]}"
        if info_match.score[0] == -1:
            score = ""
        obj = {
            "division": m.LeagueDivision.name,
            "matchday": m.matchday,
            "date": m.date,
            "team1": m.detail[0].team.name,
            "team2": m.detail[1].team.name,
            "score": score,
        }
        object_list.append(obj)
    object_df = pd.DataFrame([dict(s) for s in object_list])
    return object_df


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    matchday_options = {
        div.id: get_unique_order(
            [m.matchday for m in matches_list if m.leagueDivisionId == div.id]
        )
        for div in divisions_list
    }

    pagination_division = {
        div.id: len(
            [
                m
                for m in matches_list
                if m.matchday == 1 and div.id == m.leagueDivisionId
            ]
        )
        for div in divisions_list
    }

    pagination_team = {
        div.id: len(matchday_options[div.id]) / 2 for div in divisions_list
    }

    st.write("# Season 9 playoff matches")

    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_name_select = st.selectbox(
            "Division",
            [d.name for d in divisions_list],
        )
        div_select = [d for d in divisions_list if d.name == div_name_select][0]
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox(
            "Filter team",
            False,
        )
    with col3:
        if use_team_filter:
            team_options = [
                t.name for t in teams_list if t.division.name in div_name_select
            ]
        else:
            team_options = []
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )

    col1, col2 = st.columns([2, 8])
    with col1:
        st.write("")
        st.write("")
        filter_by_md = col1.checkbox("Filter MD", False)
    with col2:
        matchday_select = col2.select_slider(
            "Matchday",
            options=matchday_options[div_select.id],
            disabled=(not filter_by_md),
        )
        if not filter_by_md:
            matchday_select = None

    match_list_filter = filter_matches(
        matches_list, team_select, div_name_select, matchday_select
    )

    df = build_match_db(match_list_filter)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column()
    gb.configure_column(
        "date",
        type=["dateColumnFilter", "customDateTimeFormat"],
        custom_format_string="dd/MM/yy",
        pivot=True,
    )

    if use_team_filter:
        pagination_nb = pagination_team[div_select.id]
    else:
        pagination_nb = pagination_division[div_select.id]

    gb.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=pagination_nb,
    )
    gb.configure_grid_options()
    grid_options = gb.build()

    AgGrid(
        df,
        gridOptions=grid_options,
        fit_columns_on_grid_load=True,
    )


if __name__ == "__main__":
    main()
