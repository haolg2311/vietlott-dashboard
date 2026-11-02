# Bảng phân tích Vietlott

Trang tĩnh chấm giá trị vé Mega 6/45 và Power 6/55 mỗi ngày. Trang không dự đoán số trúng.

- `scripts/build.py`: tải kết quả, tính toán, ghi `data/dashboard.json`.
- `data/history.json`: toàn bộ dãy số đã quay, do `build.py` tạo.
- `data/jackpots.json`: jackpot và số người trúng từng kỳ.
- `data/commentary.json`: nhận định trong ngày.
- `data/portfolio.json`: sổ danh mục giả lập, chỉ ghi thêm.
