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


def select_team(teams: list[LeagueTeam], divisions: list[LeagueDivision]):
    col1, col2 = st.columns([4, 8])
    with col1:
        div_select = st.selectbox(
            "Division",
            [d.name for d in divisions],
        )
    with col2:
        team_options = [t.name for t in teams if t.division.name in div_select]
        team_options.sort()
        team_name_select = st.selectbox(
            "Team",
            team_options,
        )
    team_obj = [t for t in teams if t.name == team_name_select][0]
    return team_obj


def select_player(team: LeagueTeam):
    active_players = [tp.player for tp in team.players if tp.active]
    active_players_name = [p.name for p in active_players]
    player_name_select = st.selectbox(
        "Player",
        active_players_name,
    )
    player_obj = [p for p in active_players if p.name == player_name_select][0]
    return player_obj


def process_new_nick(player: LeaguePlayer, nick: str):
    return None


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    st.write("# Edit player details")

    team = select_team(teams_list, divisions_list)
    if team is None:
        return

    player = select_player(team)
    if player is None:
        return

    st.write(f"## {player.name}")

    st.write("### Nicks")
    for nick in player.nicks:
        st.write(f"- {nick}")
    new_nick = st.text_input("New nick", "")
    nick_submitted = st.button("Add new nick")
    if nick_submitted:
        process_new_nick(player, new_nick)


if __name__ == "__main__":
    main()
