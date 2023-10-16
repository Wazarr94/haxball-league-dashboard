import streamlit as st
from st_pages import add_indentation

from generated.prisma import Prisma
from generated.prisma.models import LeagueDivision, LeaguePlayer, LeagueTeam
from utils.constants import LEAGUE_TEAM_SIZE_MAX, LEAGUE_TITLE
from utils.data import get_divisions, get_teams, init_connection
from utils.utils import hide_streamlit_elements

hide_streamlit_elements()
add_indentation()


def select_team_div(teams: list[LeagueTeam], divisions: list[LeagueDivision]):
    col1, col2 = st.columns([4, 8])
    with col1:
        div_select = st.selectbox("Division", divisions, format_func=lambda d: d.name)
    with col2:
        if div_select is not None:
            team_options = [td.team for td in div_select.teams]
        else:
            team_options = []
        team_select = st.selectbox("Team", team_options, format_func=lambda t: t.name)
        if len(team_options) == 0:
            return None, div_select

    # Get the team from the teams list to have the full object
    team = [t for t in teams if t.id == team_select.id][0]
    return team, div_select


def display_players(players: list[LeaguePlayer], nb_cols: int = 2) -> None:
    columns = st.columns(nb_cols)
    for i, col in enumerate(columns):
        for player in players[i::nb_cols]:
            col.write(f"- {player.name}")


def display_active_players(team: LeagueTeam):
    active_players = [p.player for p in team.players if p.active]
    st.write(f"**Active players ({len(active_players)}/{LEAGUE_TEAM_SIZE_MAX}):**")

    display_players(active_players)


def display_former_players(team: LeagueTeam):
    former_players = [p.player for p in team.players if not p.active]
    st.write("**Former players:**")

    display_players(former_players)


def main():
    if "db" not in st.session_state:
        db = init_connection()
        st.session_state["db"] = db

    db: Prisma = st.session_state["db"]

    teams_list = get_teams(db)
    divisions_list = get_divisions(db)

    st.write(f"# {LEAGUE_TITLE} teams")

    team, div = select_team_div(teams_list, divisions_list)
    if team is None:
        st.error("No teams found")
        return

    st.write(f"## {team.name}")
    st.caption(f"Initials: {team.initials}")

    display_active_players(team)
    display_former_players(team)


if __name__ == "__main__":
    main()
