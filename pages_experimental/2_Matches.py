import math
from typing import Optional

import pandas as pd
import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder
from st_pages import add_indentation

from utils.constants import LEAGUE_TITLE
from utils.data import get_divisions, get_matches, init_connection
from utils.utils import get_info_match, get_unique_order, hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


def get_div_team_select(
    divisions: list[LeagueDivision],
) -> tuple[Optional[LeagueDivision], Optional[str], bool]:
    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_select = st.selectbox("Division", divisions, format_func=lambda d: d.name)
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox("Filter team", False)
    with col3:
        if use_team_filter and div_select is not None:
            team_options = [td.team.name for td in div_select.teams]
        else:
            team_options = []
        team_select = st.selectbox("Team", team_options)

    return div_select, team_select, use_team_filter


def get_md_select(
    div: Optional[LeagueDivision], matches: list[LeagueMatch]
) -> Optional[str]:
    col1, col2 = st.columns([2, 8])
    with col1:
        st.write("")
        st.write("")
        filter_by_md = col1.checkbox("Filter MD", False)
    with col2:
        if div is None:
            matchdays_options_div = [1, 1]
        else:
            matches_div = [m for m in matches if m.leagueDivisionId == div.id]
            md_list = get_unique_order([m.matchday for m in matches_div])
            matchdays_options_div = {v: i for i, v in enumerate(md_list)}

        matchday_select = col2.select_slider(
            "Matchday",
            options=matchdays_options_div,
            disabled=(not filter_by_md),
        )
        if not filter_by_md:
            matchday_select = None

    return matchday_select


def filter_matches(
    matches: list[LeagueMatch],
    team_name: Optional[str],
    division: LeagueDivision,
    matchday_select: Optional[str],
):
    matches_div = [m for m in matches if m.leagueDivisionId == division.id]
    match_list_filter = []
    for m in matches_div:
        if matchday_select is not None and m.matchday != matchday_select:
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
            team1 = m.detail[0].team.name
        team2 = ""
        if len(m.detail) > 1:
            team2 = m.detail[1].team.name
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


def get_grid_options(
    df: pd.DataFrame,
    div: Optional[LeagueDivision],
    matches: list[LeagueMatch],
    use_team_filter: bool,
):
    matches_div = [m for m in matches if m.leagueDivisionId == div.id]
    md_list = get_unique_order([m.matchday for m in matches_div])
    matchdays_options_div = {v: i for i, v in enumerate(md_list)}
    first_md: str = md_list[0] if len(md_list) > 0 else 1

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
    elif use_team_filter:
        pagination_nb = math.ceil(len(matchdays_options_div) / 2)
    else:
        pagination_nb = len([m for m in matches_div if m.matchday == first_md])

    gb.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=pagination_nb,
    )
    gb.configure_grid_options()
    grid_options = gb.build()

    return grid_options


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    divisions_list = get_divisions(db)

    st.write(f"# {LEAGUE_TITLE} matches")

    div, team_select, use_team_filter = get_div_team_select(divisions_list)
    matchday_select = get_md_select(div, matches_list)

    match_list_filter = filter_matches(matches_list, team_select, div, matchday_select)

    df = build_match_db(match_list_filter)
    grid_options = get_grid_options(df, div, matches_list, use_team_filter)

    AgGrid(df, gridOptions=grid_options, fit_columns_on_grid_load=True)


if __name__ == "__main__":
    main()
