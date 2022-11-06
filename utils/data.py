import os

import streamlit as st
from prisma import Prisma


@st.experimental_singleton
def init_connection():
    url = os.environ["DATABASE_URL"]
    db = Prisma(
        datasource={
            "url": url,
        }
    )
    db.connect()
    return db


@st.experimental_singleton
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


@st.experimental_singleton
def get_divisions(_db: Prisma):
    divisions = _db.leaguedivision.find_many(
        order={"id": "asc"},
    )
    return divisions


@st.experimental_singleton
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


@st.experimental_singleton
def get_players(_db: Prisma):
    players = _db.leagueplayer.find_many(
        order={"id": "asc"},
    )
    return players


@st.experimental_singleton
def get_periods(_db: Prisma):
    periods = _db.period.find_many(
        order={"id": "asc"},
    )
    return periods
