import streamlit as st

# Configure the page
st.set_page_config(
    page_title="AI Calendar Assistant",
    layout="wide"
)

# Title
st.title("AI Calendar Assistant")

st.write("Welcome to your AI-powered scheduling assistant")

# Test that Streamlit works
if st.button("Test Button"):
    st.success("✅ Streamlit is working!")
