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

c3, c4 = st.columns(2)

with c3:
    st.markdown("### 🌈 Đổi màu tóc móc lai")
    st.markdown("""
Upload **ảnh người mẫu đã có lọn móc lai** + **ảnh swatch màu mới**.

AI sẽ nhận diện các lọn móc lai có sẵn và đổi sang đúng màu swatch, giữ nguyên tóc tự nhiên và khuôn mặt.

**Phù hợp khi:** bạn có 1 ảnh mẫu móc lai và muốn nhân ra nhiều phiên bản màu khác nhau.
    """)
    st.page_link("pages/3_Toc_Moc_Lai.py", label="Đến trang Đổi màu tóc móc lai →", icon="🌈")

with c4:
    st.markdown("### 📸 Bộ ảnh Highlight Clip-In")
    st.markdown("""
Tạo bộ **3 ảnh đồng nhất gương mặt**: Before → After → Lifestyle.

Upload ảnh model (hoặc để AI tự sinh) + swatch màu. Giữ nguyên tóc gốc, chỉ thêm vài line highlight mảnh.

**Phù hợp khi:** bạn cần bộ ảnh quảng bá sản phẩm kẹp highlight clip-in theo từng màu.
    """)
    st.page_link("pages/5_Bo_Anh_Clipin.py", label="Đến trang Bộ ảnh Clip-In →", icon="📸")

c5, _ = st.columns(2)
with c5:
    st.markdown("### 🪧 Tạo bảng hiệu quảng cáo")
    st.markdown("""
Nhập **thông tin cửa hàng** + chọn **kích thước & phong cách**.

AI sẽ thiết kế bảng hiệu với chữ tiếng Việt, theo các nguyên tắc thiết kế bảng hiệu cửa hàng.

**Phù hợp khi:** bạn cần mẫu bảng hiệu nhanh cho quán ăn, cà phê, cửa hàng buôn bán.
    """)
    st.page_link("pages/4_Bang_Hieu.py", label="Đến trang Tạo bảng hiệu →", icon="🪧")

st.divider()
st.caption("Quota 50 lần dùng chung cho cả 5 tính năng.")
