# 💇 Đổi màu tóc AI — FLUX Kontext

App Streamlit đổi màu tóc người mẫu theo ảnh mẫu tóc, dùng FLUX Kontext trên Replicate.

## Chạy local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Nhập Replicate API token vào ô bên trái (hoặc tạo file `.streamlit/secrets.toml`
từ mẫu `.streamlit/secrets.toml.example`).

## Deploy lên Streamlit Community Cloud (miễn phí)

1. **Đẩy code lên GitHub** (một repo mới). Nhờ `.gitignore`, các script chứa
   token và thư mục `outputs/` sẽ KHÔNG bị đẩy lên.
2. Vào **share.streamlit.io** → đăng nhập bằng GitHub → **New app**.
3. Chọn repo, branch, và file `app.py`.
4. Vào **Advanced settings → Secrets**, dán:
   ```toml
   REPLICATE_API_TOKEN = "r8_xxxxxxxxxxxxxxxx"
   ```
5. Bấm **Deploy**. Vài phút sau app có link công khai.

## Lưu ý

- Mỗi lần tạo ảnh tốn ~$0.04 trên Replicate (app deploy vẫn gọi API tính tiền).
- **Tuyệt đối không** hardcode token vào `app.py` rồi đẩy lên repo công khai.
- Đặt tên file swatch kiểu `2-dark-brown.png`, `23-golden-blonde.png` để app
  tự lấy tên màu.
