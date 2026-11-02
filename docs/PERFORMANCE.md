# Tối ưu tốc độ 4.1.0

## Thay đổi

- Giảm nghỉ giữa vòng Esc/mở lại từ 350 ms xuống 50 ms; chế độ chỉ đọc hộp từ 120 ms xuống 40 ms.
- Hộp vẫn giữ nguyên giá không cần lượt xác nhận thứ hai. Khi phát hiện giá đổi, vẫn đọc lại từ ảnh mới trước khi xử lý; giảm nghỉ giữa hai lượt đọc này từ 60 xuống 20 ms.
- Các bước chờ đóng hộp, hiện nút sau hover và mở hộp dùng nhịp 20 → 40 → 80 ms thay vì luôn đợi 80 ms. Tổng ngân sách chờ được giữ nguyên.
- Cache tối đa 32 vùng ảnh của bảng TTCN. Chỉ dùng lại OCR khi loại vùng, kích thước, chế độ ảnh và toàn bộ pixel trùng chính xác. Ảnh đổi hoặc OCR lỗi phải đọc lại.
- Bỏ khoảng nghỉ mặc định sau các thao tác PyAutoGUI đã có bước kiểm tra/chờ riêng. Giữ fail-safe, F8, kiểm tra cửa sổ và thời gian giữ Esc.
- Trạng thái ngay trước chọn MAX/MIN cập nhật qua sự kiện phase; số đo và ghi log diễn ra sau click gửi. Nhật ký pending vẫn phải ghi bền vững trước click gửi.

## Phép đo ngoại tuyến

Chạy tại gốc dự án:

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark
```

Dùng ảnh `sample-orders-hover.png`, đọc tiêu đề TTCN, tab, đúng dòng cầu thủ/mức cộng/trạng thái và nút Đăng ký lại. Mỗi lần đo 8 vòng; trung vị 7 vòng sau lần đầu trên máy phát triển:

| Phiên bản | Trung vị |
| --- | ---: |
| Trước tối ưu | 131,43 ms |
| Sau tối ưu | 20,30 ms |

Kết quả trên ảnh không đổi thể hiện lợi ích cache, không đại diện cho toàn bộ giao dịch. Chưa bao gồm chụp màn hình, thời gian game vẽ lại, đường truyền, xếp hàng và xử lý ở máy chủ. Ảnh đổi thường xuyên có thể giảm lợi ích cache. Không suy ra xác suất đứng trước người chơi khác từ số đo này.

## Số đo khi dùng thật

Sau click gửi, Nhật ký phiên có dòng **Hiệu năng cục bộ**, gồm thời gian làm mới/đọc giá, thời gian chọn và xác minh BP, và thời gian từ xác nhận giá đổi đến khi hàm click gửi trả về. Đây không phải thời điểm máy chủ nhận hoặc xếp thứ tự lệnh. Chế độ Chạy thử không bấm gửi nên không có số đo click gửi.

Trước gửi vẫn yêu cầu đúng cầu thủ, mức cộng, loại hộp/tab, số lượng 1, hai lượt giá BP đầy đủ trùng nhau, ngưỡng và nút đang bật. Mỗi phiên tối đa một lần gửi. Kiểm thử dùng ảnh/mô phỏng, không thực hiện giao dịch thật trong game.
