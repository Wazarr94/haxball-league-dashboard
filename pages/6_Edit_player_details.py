from typing import Optional

import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeaguePlayer, LeagueTeam

from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


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
def get_divisions(_db: Prisma):
    divisions = _db.leaguedivision.find_many(
        order={"id": "asc"},
    )
    return divisions


@st.experimental_memo(ttl=600)
def get_players(_db: Prisma):
    teams = _db.leagueplayer.find_many(
        order={"id": "asc"},
    )
    return teams


def select_team(teams: list[LeagueTeam], divisions: list[LeagueDivision]):
    col1, col2, col3 = st.columns([2, 3, 9])
    with col1:
        st.text("")
        st.text("")
        use_team_filter = st.checkbox(
            "Filter team",
            False,
        )
    with col2:
        div_filter = [d.name for d in divisions] if use_team_filter else []
        div_select = st.selectbox(
            "Division",
            div_filter,
        )
    with col3:
        if use_team_filter:
            team_options = [t.name for t in teams if t.division.name in div_select]
            team_options.sort()
        else:
            team_options = []
        team_name_select = st.selectbox(
            "Team",
            team_options,
        )
    team_list = [t for t in teams if t.name == team_name_select]
    if len(team_list) == 0:
        return None
    return team_list[0]


def select_player(team: Optional[LeagueTeam], players: list[LeaguePlayer]):
    if team is None:
        players_list = [p for p in players]
    else:
        players_list = [tp.player for tp in team.players if tp.active]
    players_name_list = [p.name for p in players_list]
    player_name_select = st.selectbox(
        "Player",
        players_name_list,
    )
    player_obj = [p for p in players_list if p.name == player_name_select][0]
    return player_obj


def select_new_team(teams: list[LeagueTeam]):
    return None


def process_new_player(player_name: str, team: LeagueTeam):
    return None


def process_new_nick(player: LeaguePlayer, nick: str):
    return None


def process_new_team(
    player: LeaguePlayer,
    new_team: Optional[LeagueTeam],
    current_team: Optional[LeagueTeam],
):
    return None


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    if not st.session_state["authentication_status"]:
        st.error("You are not allowed to see this page")
        return

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)
    players_list = get_players(db)

    st.write("# Edit player details")

    team = select_team(teams_list, divisions_list)

    st.write("## Add new player")
    player_name = st.text_input("Player name", "")
    player_submitted = st.button("Add player", disabled=(team is None))
    if player_submitted:
        process_new_player(player_name, team)

    st.write("## Edit player")
    player = select_player(team, players_list)
    if player is None:
        return

    st.write(f"### {player.name}")

    st.write("#### Nicks")
    for nick in player.nicks:
        st.write(f"- {nick}")
    new_nick = st.text_input("New nick", "")
    nick_submitted = st.button("Add nick")
    if nick_submitted:
        process_new_nick(player, new_nick)

    st.write("#### Team")
    new_team = st.text_input("New team", "")
    team_submitted = st.button("Change team")
    if team_submitted:
        process_new_team(player, new_team, team)


if __name__ == "__main__":
    main()
