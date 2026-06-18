import streamlit as st
from utils import render_quota_bar, render_sidebar

render_sidebar()
render_quota_bar()

st.title("✂️ AI Tạo Ảnh Tóc")
st.markdown("""
Chào mừng bạn đến với hệ thống tạo ảnh tóc bằng AI!

Chọn tính năng từ **sidebar bên trái** để bắt đầu:
""")

st.divider()

c1, c2 = st.columns(2)

with c1:
    st.markdown("### 💇 Đổi màu tóc")
    st.markdown("""
Upload **ảnh người mẫu** + **ảnh swatch màu tóc**.

AI sẽ đổi màu tóc trong khi giữ nguyên khuôn mặt, da và bố cục ảnh gốc.

**Phù hợp khi:** bạn có sẵn ảnh người mẫu cố định và muốn thử nhiều màu tóc khác nhau.
    """)
    st.page_link("pages/1_Doi_Mau_Toc.py", label="Đến trang Đổi màu tóc →", icon="💇")

with c2:
    st.markdown("### 🧑 Tạo người mẫu mới")
    st.markdown("""
Chỉ cần upload **ảnh swatch màu tóc**.

AI sẽ tự sinh ra người mẫu hoàn toàn mới với màu tóc, chủng tộc, giới tính và kiểu tóc bạn chọn.

**Phù hợp khi:** bạn muốn tạo đa dạng người mẫu mà không cần ảnh đầu vào.
    """)
    st.page_link("pages/2_Tao_Nguoi_Mau.py", label="Đến trang Tạo người mẫu mới →", icon="🧑")

st.divider()
st.caption("Quota 50 lần dùng chung cho cả 2 tính năng.")
