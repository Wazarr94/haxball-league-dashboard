import streamlit as st
import math
from prisma import Prisma
from prisma.models import LeagueMatch, LeagueDivision, LeagueTeam, PlayerStats, Period
from dataclasses import dataclass
from itertools import groupby

from utils.utils import GamePosition, hide_streamlit_elements, get_info_match

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


@dataclass
class PlayerStatSheet:
    name: str
    team: str
    period_team: int
    stats: PlayerStats


def sum_sheets(player_sheets: list[PlayerStatSheet]):
    player_sheets.sort(key=lambda x: x.name)
    grouped = [list(res) for _, res in groupby(player_sheets, key=lambda p: p.name)]
    final_player_sheets: list[PlayerStatSheet] = []
    for group in grouped:
        goals = sum([pss.stats.goals for pss in group])
        assists = sum([pss.stats.assists for pss in group])
        gametime = sum([min(pss.stats.gametime, 7 * 60) for pss in group])
        secondaryAssists = sum([pss.stats.secondaryAssists for pss in group])
        tertiaryAssists = sum([pss.stats.tertiaryAssists for pss in group])
        saves = sum([pss.stats.saves for pss in group])
        clears = sum([pss.stats.clears for pss in group])
        interceptions = sum([pss.stats.interceptions for pss in group])
        shots = sum([pss.stats.shots for pss in group])
        shotsTarget = sum([pss.stats.shotsTarget for pss in group])
        duels = sum([pss.stats.duels for pss in group])
        reboundDribbles = sum([pss.stats.reboundDribbles for pss in group])
        passesAttempted = sum([pss.stats.passesAttempted for pss in group])
        passesSuccessful = sum([pss.stats.passesSuccessful for pss in group])
        touches = sum([pss.stats.touches for pss in group])
        kicks = sum([pss.stats.kicks for pss in group])
        gamePosition = [pss.stats.gamePosition for pss in group][0]
        ownGoals = sum([pss.stats.ownGoals for pss in group])
        goalsScoredTeam = sum([pss.stats.goalsScoredTeam for pss in group])
        goalsConcededTeam = sum([pss.stats.goalsConcededTeam for pss in group])
        averagePosXList = [
            pss.stats.averagePosX if pss.period_team == 1 else -pss.stats.averagePosX
            for pss in group
        ]
        averagePosX = sum(averagePosXList) / len(averagePosXList)
        averagePosYList = [pss.stats.averagePosY for pss in group]
        averagePosY = sum(averagePosYList) / len(averagePosYList)

        final_ps = PlayerStats(
            id="",
            period=None,
            periodId=1,
            Player=None,
            playerId="",
            goals=goals,
            assists=assists,
            gametime=gametime,
            averagePosX=averagePosX,
            averagePosY=averagePosY,
            clears=clears,
            duels=duels,
            gamePosition=gamePosition,
            goalsConcededTeam=goalsConcededTeam,
            goalsScoredTeam=goalsScoredTeam,
            interceptions=interceptions,
            kicks=kicks,
            ownGoals=ownGoals,
            passesAttempted=passesAttempted,
            passesSuccessful=passesSuccessful,
            reboundDribbles=reboundDribbles,
            saves=saves,
            secondaryAssists=secondaryAssists,
            shots=shots,
            shotsTarget=shotsTarget,
            tertiaryAssists=tertiaryAssists,
            touches=touches,
        )
        final_pss = PlayerStatSheet(
            group[0].name, group[0].team, group[0].period_team, final_ps
        )
        final_player_sheets.append(final_pss)
    return final_player_sheets


def display_gametime(gametime: float) -> str:
    minutes = math.floor(gametime / 60)
    seconds = math.floor(gametime % 60)
    if minutes == 0:
        return f"{seconds}s"
    if seconds == 0:
        return f"{minutes}m"
    return f"{minutes}m{seconds}s"


def display_statsheet(statsheet: PlayerStatSheet):
    st.write(f"### {statsheet.name}")
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
    col4.metric("Clears", statsheet.stats.clears)


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

    match_details: LeagueMatch = temp(divisions_list, matches_list, teams_list)
    info_match = get_info_match(match_details)

    periods_match = match_details.periods
    periods_match.sort(key=lambda x: x.id)

    detail_1, detail_2 = match_details.detail[0], match_details.detail[1]
    team_red = detail_1.team if detail_1.startsRed else detail_2.team
    team_blue = detail_2.team if detail_1.startsRed else detail_1.team

    ps_list: list[PlayerStatSheet] = []
    for i, period in enumerate(periods_match):
        period_stats: Period = period
        for ps in period_stats.PlayerStats:
            pname_period = ps.Player.name
            if ps.Player.team == 1:
                lp_name = pname_period
                team = team_red if i % 2 == 0 else team_blue
                lp_list = [p for p in players_list if pname_period in p.nicks]
                if len(lp_list) > 0:
                    lp_name = lp_list[0].name
                else:
                    lp_name = f"{lp_name} (unknown)"
                stat_sheet = PlayerStatSheet(lp_name, team, 1, ps)
                ps_list.append(stat_sheet)
            elif ps.Player.team == 2:
                lp_name = pname_period
                team = team_blue if i % 2 == 0 else team_red
                lp_list = [p for p in players_list if pname_period in p.nicks]
                if len(lp_list) > 0:
                    lp_name = lp_list[0].name
                else:
                    lp_name = f"{lp_name} (unknown)"
                stat_sheet = PlayerStatSheet(lp_name, team, 2, ps)
                ps_list.append(stat_sheet)

    st.write(
        f"## {team_red.name} {info_match.score[0]}-{info_match.score[1]} {team_blue.name}"
    )
    poss_red = info_match.possession[0] / (sum(info_match.possession))
    poss_blue = 1 - poss_red
    st.text(f"Possession: {100 * poss_red:.1f}% - {100 * poss_blue:.1f}%")

    action_red = info_match.action_zone[0] / (sum(info_match.action_zone))
    action_blue = 1 - action_red
    st.text(f"Action zone: {100 * action_red:.1f}% - {100 * action_blue:.1f}%")

    tab1, tab2 = st.tabs([team_red.name, team_blue.name])

    with tab1:
        pss_list_1 = [pss for pss in ps_list if pss.team == team_red]
        pss_list_team1 = sum_sheets(pss_list_1)
        pss_list_team1.sort(
            key=lambda pss: (pss.stats.gamePosition, -pss.stats.gametime)
        )
        player_name = st.selectbox(
            "View player stats", [pss.name for pss in pss_list_team1]
        )
        pss_filter = [pss for pss in pss_list_team1 if pss.name == player_name]
        if len(pss_filter) > 0:
            display_statsheet(pss_filter[0])

    with tab2:
        pss_list_2 = [pss for pss in ps_list if pss.team == team_blue]
        pss_list_team2 = sum_sheets(pss_list_2)
        pss_list_team2.sort(
            key=lambda pss: (pss.stats.gamePosition, -pss.stats.gametime)
        )
        player_name = st.selectbox(
            "View player stats", [pss.name for pss in pss_list_team2]
        )
        pss_filter = [pss for pss in pss_list_team2 if pss.name == player_name]
        if len(pss_filter) > 0:
            display_statsheet(pss_filter[0])


if __name__ == "__main__":
    main()
