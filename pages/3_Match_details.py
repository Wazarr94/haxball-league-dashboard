import streamlit as st
from prisma import Prisma
from prisma.models import (
    LeagueMatch,
    LeagueDivision,
    LeagueTeam,
    PlayerStats,
)

from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


@st.experimental_memo(ttl=600)
def get_matches(_db: Prisma):
    matches = _db.leaguematch.find_many(
        include={
            "LeagueDivision": True,
            "detail": {
                "include": {
                    "team": True,
                }
            },
            "periods": {
                "include": {
                    "PlayerStats": {
                        "include": {
                            "Player": {
                                "include": {
                                    "goalDetail": {
                                        "include": {
                                            "goal": True,
                                        }
                                    },
                                }
                            },
                        }
                    }
                }
            },
        },
        order={"id": "asc"},
    )
    return matches


@st.experimental_memo(ttl=600)
def get_divisions(_db: Prisma):
    divisions = _db.leaguedivision.find_many(
        order={"id": "asc"},
    )
    return divisions


@st.experimental_memo(ttl=600)
def get_teams(_db: Prisma):
    teams = _db.leagueteam.find_many(
        include={
            "division": True,
            "players": {
                "include": {
                    "player": True,
                }
            },
        },
        order={"id": "asc"},
    )
    return teams


@st.experimental_memo(ttl=600)
def get_players(_db: Prisma):
    teams = _db.leagueplayer.find_many(
        order={"id": "asc"},
    )
    return teams


def temp(
    divisions_list: list[LeagueDivision],
    matches_list: list[LeagueMatch],
    teams_list: list[LeagueTeam],
):
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

    match_list_filter: list[LeagueMatch] = []
    for m in matches_list:
        if m.LeagueDivision.name != div_name_select:
            continue
        if len(m.periods) == 0:
            continue
        if team_select is None or any([md.team.name == team_select for md in m.detail]):
            match_list_filter.append(m)

    match_to_edit_title = st.selectbox("Match", [m.title for m in match_list_filter])
    match_to_edit = [m for m in match_list_filter if m.title == match_to_edit_title][0]

    return match_to_edit


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    teams_list = get_teams(db)
    divisions_list = get_divisions(db)
    players_list = get_players(db)

    matchday_options = {
        div.id: set([m.matchday for m in matches_list if m.leagueDivisionId == div.id])
        for div in divisions_list
    }

    st.write("# Match details")

    match_details = temp(divisions_list, matches_list, teams_list)

    periods_match = match_details.periods
    periods_match.sort(key=lambda x: x.id)
    period_stats = periods_match[0]

    ps_red: dict[str, PlayerStats] = {}
    ps_blue: dict[str, PlayerStats] = {}
    for ps in period_stats.PlayerStats:
        pname_period = ps.Player.name
        if ps.Player.team == 1:
            lp_name = pname_period
            lp_list = [p for p in players_list if pname_period in p.nicks]
            if len(lp_list) > 0:
                lp_name = lp_list[0].name
            else:
                lp_name = f"{lp_name} (unknown)"
            ps_red[lp_name] = ps
        elif ps.Player.team == 2:
            lp_name = pname_period
            lp_list = [p for p in players_list if pname_period in p.nicks]
            if len(lp_list) > 0:
                lp_name = lp_list[0].name
            else:
                lp_name = f"{lp_name} (unknown)"
            ps_blue[lp_name] = ps

    detail_1, detail_2 = match_details.detail[0], match_details.detail[1]
    team_red = detail_1.team if detail_1.startsRed else detail_2.team
    team_blue = detail_2.team if detail_1.startsRed else detail_1.team

    tab1, tab2 = st.tabs([team_red.name, team_blue.name])
    with tab1:
        for lp_name, ps in ps_red.items():
            st.write(f"### {lp_name}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Goals", ps.goals)
            col2.metric("Assists", ps.assists)
            col3.metric("Saves", ps.saves)
    with tab2:
        for lp_name, ps in ps_blue.items():
            st.write(f"### {lp_name}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Goals", ps.goals)
            col2.metric("Assists", ps.assists)
            col3.metric("Saves", ps.saves)


if __name__ == "__main__":
    main()
