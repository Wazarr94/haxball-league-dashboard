import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueTeam

from utils.data import get_divisions, get_teams
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()


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
        team_select = st.selectbox(
            "Team",
            team_options,
        )
    team_obj = [t for t in teams if t.name == team_select][0]
    return team_obj


def display_active_players(team: LeagueTeam):
    active_players = [p.player for p in team.players if p.active]
    st.write(f"**Active players ({len(active_players)}/12):**")

    col1, col2 = st.columns(2)
    with col1:
        for player in active_players[::2]:
            st.write(f"- {player.name}")
    with col2:
        for player in active_players[1::2]:
            st.write(f"- {player.name}")


def display_former_players(team: LeagueTeam):
    former_players = [p.player for p in team.players if not p.active]
    st.write(f"**Former players:**")

    col1, col2 = st.columns(2)
    with col1:
        for player in former_players[::2]:
            st.write(f"- {player.name}")
    with col2:
        for player in former_players[1::2]:
            st.write(f"- {player.name}")


def main():
    if "db" not in st.session_state:
        return
    db: Prisma = st.session_state["db"]

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    st.write("# Season 9 playoff teams")

    team = select_team(teams_list, divisions_list)
    if team is None:
        return

    st.write(f"## {team.name}")

    display_active_players(team)
    display_former_players(team)


if __name__ == "__main__":
    main()
