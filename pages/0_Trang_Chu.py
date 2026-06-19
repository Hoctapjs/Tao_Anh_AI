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

c1, c2, c3 = st.columns(3)

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

with c3:
    st.markdown("### 🌈 Đổi màu tóc móc lai")
    st.markdown("""
Upload **ảnh người mẫu đã có lọn móc lai** + **ảnh swatch màu mới**.

AI sẽ nhận diện các lọn móc lai có sẵn và đổi sang đúng màu swatch, giữ nguyên tóc tự nhiên và khuôn mặt.

**Phù hợp khi:** bạn có 1 ảnh mẫu móc lai và muốn nhân ra nhiều phiên bản màu khác nhau.
    """)
    st.page_link("pages/3_Toc_Moc_Lai.py", label="Đến trang Đổi màu tóc móc lai →", icon="🌈")

st.divider()
st.caption("Quota 50 lần dùng chung cho cả 3 tính năng.")
