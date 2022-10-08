# streamlit_app.py
import datetime
from numpy import unique
import streamlit as st
import pandas as pd
from prisma import Prisma
from prisma.models import LeagueMatch


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
            "date": datetime.date(m.date.year, m.date.month, m.date.day),
            "team1": m.LeagueMatchDetail[0].team.name,
            "team2": m.LeagueMatchDetail[1].team.name,
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

    st.write("# Season 3 matches")

    col1, col2 = st.columns([4, 8])
    with col1:
        div_select = st.selectbox(
            "Division",
            [d.name for d in divisions_list],
        )
    with col2:
        team_options = [t.name for t in teams_list if t.division.name in div_select]
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )
    matchday_options = set([m.matchday for m in matches_list])
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
        if any([md.team.name in team_select for md in m.LeagueMatchDetail]):
            match_list_filter.append(m)

    st.dataframe(
        build_match_db(match_list_filter),
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
