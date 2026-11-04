# Bảng phân tích Vietlott

Trang tĩnh chấm giá trị vé Mega 6/45, Power 6/55 và Lotto 5/35 mỗi ngày. Trang không dự đoán số trúng.

- `scripts/fetch_results.py`: GitHub Actions lấy jackpot và số giải từng hạng, không dùng Claude.
- `scripts/build.py`: tải kết quả, tính toán, ghi `data/dashboard.json`.
- `data/history.json`: toàn bộ dãy số đã quay, do `build.py` tạo.
- `data/jackpots.json`: jackpot và số người trúng từng kỳ.
- `data/lotto.json`: Độc đắc, số giải từng hạng và các kỳ chia giải của Lotto 5/35.
- `data/commentary.json`: nhận định trong ngày.
- `data/forecast_log.json`: sổ dự báo từng lượt chạy, kết quả thật và sai số, chỉ ghi thêm.
- `data/portfolio.json`: sổ danh mục giả lập, chỉ ghi thêm.
