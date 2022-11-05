import math

import streamlit as st
from prisma import Prisma
from prisma.models import (
    LeagueDivision,
    LeagueMatch,
    LeaguePlayer,
    LeagueTeam,
)

from utils.utils import (
    GamePosition,
    PlayerStatSheet,
    get_info_match,
    get_statsheet_list,
    hide_streamlit_elements,
    sum_sheets,
)

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
    for m in matches:
        m.detail.sort(key=lambda d: not d.home)
        m.periods.sort(key=lambda p: p.id)
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
    players = _db.leagueplayer.find_many(
        order={"id": "asc"},
    )
    return players


def select_match(
    divisions: list[LeagueDivision],
    matches: list[LeagueMatch],
    teams: list[LeagueTeam],
):
    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_name_select = st.selectbox(
            "Division",
            [d.name for d in divisions],
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
            team_options = [t.name for t in teams if t.division.name in div_name_select]
        else:
            team_options = []
        team_options.sort()
        team_select = st.selectbox(
            "Team",
            team_options,
        )

    match_list_filter: list[LeagueMatch] = []
    for m in matches:
        if m.LeagueDivision.name != div_name_select:
            continue
        if len(m.periods) == 0:
            continue
        if team_select is None or any([md.team.name == team_select for md in m.detail]):
            match_list_filter.append(m)

    match_to_edit_title = st.selectbox("Match", [m.title for m in match_list_filter])
    match_edit_list = [m for m in match_list_filter if m.title == match_to_edit_title]
    if len(match_edit_list) > 0:
        return match_edit_list[0]

    return None


def display_gametime(gametime: float) -> str:
    minutes = math.floor(gametime / 60)
    seconds = math.floor(gametime % 60)
    if minutes == 0:
        return f"{seconds}s"
    if seconds == 0:
        return f"{minutes}m"
    return f"{minutes}m{seconds}s"


def display_statsheet(statsheet: PlayerStatSheet):
    st.write(f"### {statsheet.player_name}")
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Gametime", display_gametime(statsheet.stats.gametime))
    col2.metric("Position", GamePosition(statsheet.stats.gamePosition).name)
    col3.metric("Goals", statsheet.stats.goals)
    col4.metric("Assists", statsheet.stats.assists)

    col1.metric("Assists (2)", statsheet.stats.secondaryAssists)
    col2.metric("Assists (3)", statsheet.stats.tertiaryAssists)
    col3.metric("Passes", statsheet.stats.passesAttempted)
    col4.metric(
        "Pass success %",
        f"{statsheet.stats.passesSuccessful / statsheet.stats.passesAttempted * 100:.1f}%",
    )

    col1.metric("Touches", statsheet.stats.touches)
    col2.metric("Kicks", statsheet.stats.kicks)
    col3.metric("Duels", statsheet.stats.duels)
    col4.metric("Interceptions", statsheet.stats.interceptions)

    col1.metric("Shots", statsheet.stats.shots)
    col2.metric("Shorts (T)", statsheet.stats.shotsTarget)
    col3.metric("Saves", statsheet.stats.saves)
    col4.metric("Own goals", statsheet.stats.ownGoals)


def display_stats_general(match: LeagueMatch):
    detail_1, detail_2 = match.detail[0], match.detail[1]
    info_match = get_info_match(match)

    st.write(
        f"## {detail_1.team.name} {info_match.score[0]}-{info_match.score[1]} {detail_2.team.name}"
    )
    poss_1 = info_match.possession[0] / (sum(info_match.possession))
    poss_2 = 1 - poss_1
    st.text(f"Possession: {100 * poss_1:.1f}% - {100 * poss_2:.1f}%")

    action_1 = info_match.action_zone[0] / (sum(info_match.action_zone))
    action_2 = 1 - action_1
    st.text(f"Action zone: {100 * action_1:.1f}% - {100 * action_2:.1f}%")


def display_stats_team(statsheet_list: list[PlayerStatSheet], team: LeagueTeam):
    pss_list_1 = [pss for pss in statsheet_list if pss.team == team]
    pss_list_team1 = sum_sheets(pss_list_1)
    pss_list_team1.sort(key=lambda pss: (pss.stats.gamePosition, -pss.stats.gametime))
    player_name = st.selectbox(
        "View player stats", [pss.player_name for pss in pss_list_team1]
    )
    pss_filter = [pss for pss in pss_list_team1 if pss.player_name == player_name]
    if len(pss_filter) > 0:
        display_statsheet(pss_filter[0])


def display_stats_teams(match: LeagueMatch, players: list[LeaguePlayer]):
    detail_1, detail_2 = match.detail[0], match.detail[1]
    tab1, tab2 = st.tabs([detail_1.team.name, detail_2.team.name])

    ps_list = get_statsheet_list(players, match)

    with tab1:
        display_stats_team(ps_list, detail_1.team)

    with tab2:
        display_stats_team(ps_list, detail_2.team)
    return None


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    teams_list = get_teams(db)
    divisions_list = get_divisions(db)
    players_list = get_players(db)

    st.write("# Match details")

    match_play: LeagueMatch = select_match(divisions_list, matches_list, teams_list)
    if match_play is None:
        return

    display_stats_general(match_play)
    display_stats_teams(match_play, players_list)


if __name__ == "__main__":
    main()
