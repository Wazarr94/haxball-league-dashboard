# streamlit_app.py

import streamlit as st
from prisma import Prisma


@st.experimental_singleton
def init_connection():
    url = st.secrets["DATABASE_URL"]
    db = Prisma(
        datasource={
            "url": url,
        }
    )
    db.connect()
    return db


def main():
    db = init_connection()
    st.session_state["db"] = db

    st.write("# Home page")
    st.write("#### Welcome to the BFF dashboard")


if __name__ == "__main__":
    main()
