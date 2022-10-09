import datetime
import streamlit as st
import pandas as pd
from prisma import Prisma
from prisma.models import LeagueMatch
from st_aggrid import AgGrid, AgGridTheme
from st_aggrid.grid_options_builder import GridOptionsBuilder


@st.experimental_memo(ttl=600)
def get_matches(_db: Prisma):
    matches = _db.leaguematch.find_many(
        include={
            "LeagueDivision": True,
            "LeagueMatchDetail": {
                "include": {
                    "team": True,
                }
            },
        }
    )
    return matches


@st.experimental_memo(ttl=600)
def get_divisions(_db: Prisma):
    divisions = _db.leaguedivision.find_many()
    return divisions


@st.experimental_memo(ttl=600)
def get_teams(_db: Prisma):
    teams = _db.leagueteam.find_many(
        include={
            "division": True,
            "LeaguePlayerTeams": {
                "include": {
                    "player": True,
                }
            },
        }
    )
    return teams


def build_match_db(match_list: list[LeagueMatch]):
    object_df = []
    for m in match_list:
        obj = {
            "division": m.LeagueDivision.name,
            "matchday": m.matchday,
            "date": m.date,
            "team1": m.LeagueMatchDetail[0].team.name,
            "team2": m.LeagueMatchDetail[1].team.name,
            "score": "",
        }
        object_df.append(obj)
    object_df = pd.DataFrame([dict(s) for s in object_df])
    return object_df


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    matchday_options = set([m.matchday for m in matches_list])
    pagination_division = (
        len(matches_list) / len(divisions_list) / max(matchday_options)
    )
    pagination_team = max(matchday_options) / 2

    st.write("# Season 3 matches")

    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_select = st.selectbox(
            "Division",
            [d.name for d in divisions_list],
        )
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox(
            "Filter team",
            False,
        )
    with col3:
        if use_team_filter:
            team_options = [t.name for t in teams_list if t.division.name in div_select]
        else:
            team_options = []
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )

    matchdays_select = st.slider(
        "Matchdays",
        min_value=min(matchday_options),
        max_value=max(matchday_options),
        value=(min(matchday_options), max(matchday_options)),
    )

    match_list_filter = []
    for m in matches_list:
        if m.matchday < matchdays_select[0] or m.matchday > matchdays_select[1]:
            continue
        if m.LeagueDivision.name != div_select:
            continue
        if team_select is None or any(
            [md.team.name == team_select for md in m.LeagueMatchDetail]
        ):
            match_list_filter.append(m)

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
        pagination_nb = pagination_team
    else:
        pagination_nb = pagination_division

    gb.configure_pagination(
        enabled=True,
        paginationAutoPageSize=False,
        paginationPageSize=pagination_nb,
    )
    gb.configure_grid_options()
    gridOptions = gb.build()

    AgGrid(
        df,
        gridOptions=gridOptions,
        fit_columns_on_grid_load=True,
    )


if __name__ == "__main__":
    main()