import streamlit as st
import requests
from PIL import Image
from io import BytesIO

API_BASE = "http://localhost:8000"

st.title("Live AI — Camera Control & Code Analyzer")

user_id = st.text_input("User ID (used for rate limiting)", value="demo_user")

st.header("Camera")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Start"):
        requests.post(f"{API_BASE}/camera/start", headers={"x-user-id": user_id})
with col2:
    if st.button("Pause"):
        requests.post(f"{API_BASE}/camera/pause", headers={"x-user-id": user_id})
with col3:
    if st.button("Resume"):
        requests.post(f"{API_BASE}/camera/resume", headers={"x-user-id": user_id})

if st.button("Stop Camera"):
    requests.post(f"{API_BASE}/camera/stop", headers={"x-user-id": user_id})

if st.button("Get Frame"):
    r = requests.get(f"{API_BASE}/camera/frame", headers={"x-user-id": user_id})
    if r.status_code == 200:
        img = Image.open(BytesIO(r.content))
        st.image(img, caption="Latest frame")
    else:
        st.warning(r.text)

st.header("Code Analyzer")
code = st.text_area("Paste Python code to analyze", height=300)
if st.button("Analyze Code"):
    payload = {"user_id": user_id, "code": code}
    r = requests.post(f"{API_BASE}/analyze", json=payload, headers={"x-user-id": user_id})
    st.json(r.json())
