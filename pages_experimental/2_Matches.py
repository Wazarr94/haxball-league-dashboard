from typing import Optional

import pandas as pd
import streamlit as st
from prisma import Prisma
from prisma.models import LeagueMatch
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder
from st_pages import add_indentation

from utils.data import get_divisions, get_matches, init_connection
from utils.utils import get_info_match, get_unique_order, hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


def filter_matches(
    matches: list[LeagueMatch],
    team_name: Optional[str],
    division_name: str,
    matchday_select: Optional[str],
):
    match_list_filter = []
    for m in matches:
        if matchday_select is not None and m.matchday != matchday_select:
            continue
        if m.LeagueDivision.name != division_name:
            continue
        if team_name is None or any([md.team.name == team_name for md in m.detail]):
            match_list_filter.append(m)
    return match_list_filter


def build_match_db(match_list: list[LeagueMatch]):
    object_list = []
    for m in match_list:
        info_match = get_info_match(m)
        score = f"{info_match.score[0]}-{info_match.score[1]}"
        team1 = ""
        if len(m.detail) > 0:
            team1 = m.detail[0].team.initials
        team2 = ""
        if len(m.detail) > 1:
            team2 = m.detail[1].team.initials
        if info_match.score[0] == -1:
            score = ""
        obj = {
            "division": m.LeagueDivision.name,
            "matchday": m.matchday,
            "date": m.date,
            "team1": team1,
            "team2": team2,
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
    divisions_list = get_divisions(db)

    matchday_options = {
        div.id: get_unique_order(
            [m.matchday for m in matches_list if m.leagueDivisionId == div.id]
        )
        for div in divisions_list
    }

    pagination_division = {}
    for div in divisions_list:
        first_md: str = matchday_options[div.id][0]
        matches_div = [m for m in matches_list if div.id == m.leagueDivisionId]
        pagination_div = len([m for m in matches_div if m.matchday == first_md])
        pagination_division[div.id] = pagination_div

    pagination_team = {
        div.id: len(matchday_options[div.id]) / 2 for div in divisions_list
    }

    st.write("# S1 preseason matches")

    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div = st.selectbox("Division", divisions_list, format_func=lambda d: d.name)
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox("Filter team", False)
    with col3:
        if use_team_filter:
            team_options = [td.team for td in div.teams]
        else:
            team_options = []
        team_select = st.selectbox("Team", team_options, format_func=lambda t: t.name)

    col1, col2 = st.columns([2, 8])
    with col1:
        st.write("")
        st.write("")
        filter_by_md = col1.checkbox("Filter MD", False)
    with col2:
        if div is None:
            matchdays_options_div = [1, 1]
        else:
            matchdays_options_div = matchday_options[div.id]
        matchday_select = col2.select_slider(
            "Matchday",
            options=matchdays_options_div,
            disabled=(not filter_by_md),
        )
        if not filter_by_md:
            matchday_select = None

    match_list_filter = filter_matches(
        matches_list, team_select, div.name, matchday_select
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

    if div is None:
        pagination_nb = 1
    else:
        if use_team_filter:
            pagination_nb = pagination_team[div.id]
        else:
            pagination_nb = pagination_division[div.id]

    gb.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=pagination_nb,
    )
    gb.configure_grid_options()
    grid_options = gb.build()

    AgGrid(df, gridOptions=grid_options, fit_columns_on_grid_load=True)


if __name__ == "__main__":
    main()
