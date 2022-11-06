from io import BytesIO
from typing import Optional

import pandas as pd
import polars as pl
import streamlit as st
from prisma import Prisma
from prisma.models import LeagueDivision, LeagueMatch, LeaguePlayer, LeagueTeam

from utils.data import get_divisions, get_matches, get_players, get_teams
from utils.utils import (
    GamePosition,
    PlayerStatSheet,
    get_statsheet_list,
    hide_streamlit_elements,
    sum_sheets,
    is_match_played,
    display_gametime,
)

hide_streamlit_elements()


def get_div_team_select(divisions: list[LeagueDivision], teams: list[LeagueTeam]):
    col1, col2, col3 = st.columns([3, 2, 9])
    with col1:
        div_name_select = st.selectbox(
            "Division",
            [d.name for d in divisions],
        )
        div_select = [d for d in divisions if d.name == div_name_select][0]
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
        team_name_select = st.selectbox(
            "Team",
            team_options,
        )
    return div_select, team_name_select


def get_max_matchday_stats(matches: list[LeagueMatch], division: LeagueDivision):
    matches_div = [m for m in matches if m.leagueDivisionId == division.id]
    md_not_played = [m.matchday for m in matches_div if not is_match_played(m)]
    if len(md_not_played) == 0:
        return max([m.matchday for m in matches_div])
    return max(1, min(set(md_not_played)) - 1)


def filter_matches(
    matches: list[LeagueMatch],
    team_name: Optional[str],
    division: LeagueDivision,
    matchdays_select: tuple[int],
):
    match_list_filter = []
    for m in matches:
        if m.matchday < matchdays_select[0] or m.matchday > matchdays_select[1]:
            continue
        if m.LeagueDivision.name != division:
            continue
        if team_name is None or any([md.team.name == team_name for md in m.detail]):
            match_list_filter.append(m)
    return match_list_filter


def get_stats(
    matches: list[LeagueMatch],
    teams: list[LeagueTeam],
    players: list[LeaguePlayer],
    div_select: LeagueDivision,
    team_name_select: Optional[str],
):
    period_sheets: list[PlayerStatSheet] = []
    for m in matches:
        ps_list = get_statsheet_list(players, m)
        pss_list = [pss for pss in ps_list]
        period_sheets.extend(pss_list)
    player_sheets = sum_sheets(period_sheets)

    players_stats: list[LeaguePlayer] = []
    for team in teams:
        if team.division.id == div_select.id:
            if team_name_select is None or (
                team_name_select is not None and team.name == team_name_select
            ):
                active_players = [p.player for p in team.players if p.active]
                players_stats.extend(active_players)
    players_stats_id = [p.id for p in players_stats]

    player_sheets_final = [
        ps
        for ps in player_sheets
        if ps.player is not None and ps.player.id in players_stats_id
    ]

    return player_sheets_final


def download_stats(df: pd.DataFrame):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
    return buffer


def treat_stat(stat: pl.Expr, normalized: bool, gametime: pl.Expr):
    if normalized:
        return stat / (gametime / (14 * 60))
    return stat


def display_options_stats():
    col1, col2 = st.columns(2)
    normalize_stats = col1.checkbox("Normalize stats per 14mn ?", value=False)
    filter_players_time = col2.checkbox("Hide players with < 14mn ?")
    return normalize_stats, filter_players_time


def display_stat(v):
    if isinstance(v, int):
        return f"{v}"
    return f"{v:.2f}"


def display_stats(
    statsheets: list[PlayerStatSheet],
    normalized: bool,
    filter_players: bool,
):
    df_json = [
        {"player": ps.player.dict(), "stats": ps.stats.dict(), "cs": ps.cs}
        for ps in statsheets
    ]
    df_pd = pd.json_normalize(df_json)
    df = pl.DataFrame(df_pd)
    df = df.select(
        [
            pl.col("player.name"),
            pl.col("stats.gamePosition").apply(lambda g: GamePosition(g).name),
            pl.col("stats.gametime").floor().cast(pl.Int64),
            treat_stat(
                pl.col("stats.goals"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.assists"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("cs"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.saves"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.ownGoals"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.passesAttempted"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ).alias("passes"),
            (pl.col("stats.passesSuccessful") / pl.col("stats.passesAttempted"))
            .apply(lambda percent: f"{100 * percent:.1f}%")
            .alias("stats.passSuccess"),
            treat_stat(
                pl.col("stats.shots"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.shotsTarget"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.touches"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.kicks"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.secondaryAssists"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ).alias("assists_2"),
            treat_stat(
                pl.col("stats.tertiaryAssists"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ).alias("assists_3"),
            treat_stat(
                pl.col("stats.reboundDribbles"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ).alias("rebounds"),
            treat_stat(
                pl.col("stats.duels"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.interceptions"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            treat_stat(
                pl.col("stats.clears"),
                normalized,
                pl.col("stats.gametime").floor().cast(pl.Int64),
            ),
            pl.col("stats.averagePosX"),
        ]
    ).filter(
        pl.when(filter_players)
        .then(pl.col("stats.gametime") >= 14 * 60)
        .otherwise(True)
    )
    df = df.to_pandas()
    df.columns = df.columns.str.replace("player.|stats.", "", regex=True)

    st.caption(
        "Hover on the table and click the full screen icon to see all columns at once.\n\n"
        + "Click on the header to sort by a statistic."
    )

    st.dataframe(
        (
            df.style.format(
                subset=[
                    "goals",
                    "assists",
                    "cs",
                    "saves",
                    "ownGoals",
                    "passes",
                    "shots",
                    "shotsTarget",
                    "touches",
                    "kicks",
                    "assists_2",
                    "assists_3",
                    "rebounds",
                    "duels",
                    "interceptions",
                    "clears",
                ],
                formatter=display_stat,
            ).format(
                subset=["gametime"],
                formatter=display_gametime,
            )
        )
    )
    st.download_button(
        label="Download data as Excel",
        data=download_stats(df),
        file_name="BFF_stats.xlsx",
        mime="application/vnd.ms-excel",
    )


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

    st.write("# Season 4 statistics")

    div_select, team_name_select = get_div_team_select(divisions_list, teams_list)
    matchdays_options_div = matchday_options[div_select.id]

    matchday_stats_max = get_max_matchday_stats(matches_list, div_select)
    matchdays_select = st.slider(
        "Matchdays",
        min_value=min(matchdays_options_div),
        max_value=max(matchdays_options_div),
        value=(
            min(matchdays_options_div),
            matchday_stats_max,
        ),
    )

    match_list_filter = filter_matches(
        matches_list, team_name_select, div_select.name, matchdays_select
    )

    stats_players = get_stats(
        match_list_filter,
        teams_list,
        players_list,
        div_select,
        team_name_select,
    )

    normalize, filter_players = display_options_stats()
    display_stats(stats_players, normalize, filter_players)


if __name__ == "__main__":
    main()
