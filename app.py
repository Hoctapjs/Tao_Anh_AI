import streamlit as st

st.set_page_config(page_title="AI Tạo Ảnh Tóc", page_icon="✂️", layout="wide")

pg = st.navigation([
    st.Page("pages/0_Trang_Chu.py",     title="Trang chủ",       icon="🏠", default=True),
    st.Page("pages/1_Doi_Mau_Toc.py",   title="Đổi màu tóc",     icon="💇"),
    st.Page("pages/2_Tao_Nguoi_Mau.py", title="Tạo người mẫu",   icon="🧑"),
    st.Page("pages/3_Toc_Moc_Lai.py",   title="Đổi màu móc lai", icon="🌈"),
    st.Page("pages/4_Bang_Hieu.py",      title="Tạo bảng hiệu",   icon="🪧"),
])
pg.run()
