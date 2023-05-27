import copy
from typing import Optional

import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch, LeaguePlayer, LeagueTeam
from st_pages import add_indentation

from utils.data import (
    get_divisions,
    get_matches,
    get_players,
    init_connection,
)
from utils.utils import (
    GamePosition,
    PlayerStatSheet,
    display_gametime,
    get_info_match,
    get_statsheet_list,
    get_unique_order,
    hide_streamlit_elements,
    sum_sheets,
)

hide_streamlit_elements()
add_indentation()


def select_match(
    divisions: list[LeagueDivision],
    matches: list[LeagueMatch],
) -> Optional[LeagueMatch]:
    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_select = st.selectbox("Division", divisions, format_func=lambda d: d.name)
    with col2:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox("Filter team", False)
    with col3:
        if use_team_filter and div_select is not None:
            team_options = [td.team for td in div_select.teams]
        else:
            team_options = []
        team_select = st.selectbox("Team", team_options, format_func=lambda t: t.name)

    if div_select is None:
        matches_div = []
        matchdays_options_div = [1, 1]
    else:
        matches_div = [m for m in matches if m.leagueDivisionId == div_select.id]
        md_list = get_unique_order([m.matchday for m in matches_div])
        matchdays_options_div = {v: i for i, v in enumerate(md_list)}

    matchday_select = st.select_slider("Matchday", options=matchdays_options_div)

    match_list_filter: list[LeagueMatch] = []
    for m in matches_div:
        if m.matchday != matchday_select:
            continue
        if len(m.periods) == 0:
            continue
        if team_select is None or any(
            [md.team.name == team_select.name for md in m.detail]
        ):
            match_list_filter.append(m)

    match = st.selectbox("Match", match_list_filter, format_func=lambda m: m.title)
    return match


def display_statsheet(statsheet: PlayerStatSheet):
    st.write(f"### {statsheet.player_name}")
    col1, col2, col3, col4 = st.columns(4)
    ss = statsheet.stats

    col1.metric("Gametime", display_gametime(ss.gametime))
    col2.metric("Position", GamePosition(ss.gamePosition).name)
    col3.metric("Goals", ss.goals)
    col4.metric("Assists", ss.assists)

    col1.metric("Assists (2)", ss.secondaryAssists)
    col2.metric("Assists (3)", ss.tertiaryAssists)
    col3.metric("Passes", ss.passesAttempted)
    col4.metric(
        "Pass success %",
        f"{ss.passesSuccessful / (ss.passesAttempted or 1) * 100:.1f}%",
    )

    col1.metric("Touches", ss.touches)
    col2.metric("Kicks", ss.kicks)
    col3.metric("Saves", ss.saves)
    col4.metric("CS", statsheet.cs)

    col1.metric("Shots", ss.shots)
    col2.metric("Shots (T)", ss.shotsTarget)
    col3.metric("Rebounds", ss.reboundDribbles)
    col4.metric("Own goals", ss.ownGoals)


def format_period_filter(v: int):
    if v == 0:
        return "All periods"
    return f"Period {v}"


def filter_periods(match: LeagueMatch):
    match_copy = copy.deepcopy(match)
    period_select = st.selectbox(
        "Select periods",
        list(range(len(match.periods) + 1)),
        format_func=format_period_filter,
    )

    if period_select == 0:
        return match_copy

    match_copy.addBlue = 0
    match_copy.addRed = 0
    match_copy.periods = [match.periods[period_select - 1]]
    if period_select % 2 == 0:
        match_copy.detail[0].startsRed = not match_copy.detail[0].startsRed
        match_copy.detail[1].startsRed = not match_copy.detail[1].startsRed
    return match_copy


def display_stats_general(match: LeagueMatch):
    detail_1, detail_2 = match.detail[0], match.detail[1]
    info = get_info_match(match)

    st.write(
        f"## {detail_1.team.name} {info.score[0]}-{info.score[1]} {detail_2.team.name}"
    )
    if match.replayURL != "":
        st.write(f"Replay link: {match.replayURL}")
    else:
        st.write("No replay link available")

    poss_1 = info.possession[0] / (sum(info.possession))
    poss_2 = 1 - poss_1
    st.text(f"Possession: {100 * poss_1:.1f}% - {100 * poss_2:.1f}%")

    action_1 = info.action_zone[0] / (sum(info.action_zone))
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
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    matches_list = get_matches(db)
    divisions_list = get_divisions(db)
    players_list = get_players(db)

    st.write("# Match details")

    match_play: LeagueMatch = select_match(divisions_list, matches_list)
    if match_play is None:
        return

    match_periods = filter_periods(match_play)
    display_stats_general(match_periods)
    display_stats_teams(match_periods, players_list)


if __name__ == "__main__":
    main()
