import streamlit as st


def hide_streamlit_elements() -> st._DeltaGenerator:
    hide_st_style = """
              <style>
              footer {visibility: hidden;}
              </style>
              """
    return st.markdown(hide_st_style, unsafe_allow_html=True)
