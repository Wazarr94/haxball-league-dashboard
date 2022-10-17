from enum import IntEnum
import streamlit as st


class GamePosition(IntEnum):
    unknown = 0
    GK = 1
    DM = 2
    AM = 3
    ST = 4


def hide_streamlit_elements() -> st._DeltaGenerator:
    hide_st_style = """
              <style>
              footer {visibility: hidden;}
              </style>
              """
    return st.markdown(hide_st_style, unsafe_allow_html=True)
