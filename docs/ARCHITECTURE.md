# Kiến trúc và quy ước

## Luồng chạy

`app.py` → `fco/web_app.py` → giao diện `ui/` → `fco/controller.py` → các module nghiệp vụ.

| Thành phần | Trách nhiệm |
| --- | --- |
| `fco/web_app.py` | Mở WebView2, nạp giao diện cục bộ. |
| `fco/controller.py` | API JavaScript/Python, trạng thái phiên, lưu dữ liệu và điều phối tác vụ. |
| `fco/calculators/` | Tính lương và thuế độc lập với giao diện và game. |
| `fco/desktop.py`, `bounds.py`, `privileges.py` | Chụp ảnh, tọa độ và thao tác cửa sổ Windows. |
| `fco/ocr.py`, `dialog.py`, `refresh.py` | OCR, nhận diện hộp và mở lại bảng TTCN. |
| `fco/engine.py`, `pricing.py`, `schedule.py` | Canh giá, điều kiện giá, khung giờ Việt Nam. |
| `fco/storage.py` | JSON nguyên tử, khóa phiên, nhật ký lệnh. |
| `fco/paths.py` | Đường dẫn tài nguyên và dữ liệu của mã nguồn/EXE. |
| `fco/updater.py` | Kiểm tra GitHub Releases, tải/kiểm tra EXE và thay file bằng tiến trình riêng. |
| `fco/diagnostics/` | Tự kiểm tra OCR và WebView2 trong cả mã nguồn lẫn EXE. |
| `tests/` | Kiểm thử hồi quy nghiệp vụ, OCR, giao dịch và lưu dữ liệu. |
| `legacy/tkinter/` | Giao diện cũ để tra cứu; không tham gia luồng chạy chính. |

## Quy ước sửa mã

- Import từ package `fco`; không thêm đường dẫn thủ công vào `sys.path`.
- Thêm phép tính độc lập vào `fco/calculators/`, nối giao diện qua `controller.py`.
- Giữ nghiệp vụ ở Python. BP được tính bằng số nguyên, trả về JavaScript dưới dạng chuỗi.
- Giữ các điều kiện xác minh cầu thủ, loại lệnh, số lượng, giá và giới hạn một lần gửi trong luồng giao dịch.
- Ảnh kiểm thử nằm trong `assets/fixtures/`, cũng được đóng gói để EXE tự kiểm tra.
- Báo cáo sinh ra đặt ở `reports/`, EXE ở `release/`; không đưa dữ liệu người dùng vào gói chia sẻ.
- Dùng Black cho Python và Prettier cho HTML/CSS/JavaScript; không rút gọn mã nguồn giao diện thành một dòng.

## Dữ liệu và build

`RESOURCE_ROOT` là gốc dự án khi chạy mã nguồn, thư mục tài nguyên PyInstaller khi chạy EXE. `APP_ROOT` là `data-v3/` ở gốc dự án hoặc `FCO-Market-3-data/` cạnh EXE. Tổ chức lại module không đổi vị trí dữ liệu đã có.

`build.bat` gọi `scripts/build.ps1`. Script xác định gốc dự án từ vị trí của nó, không phụ thuộc thư mục hiện hành. EXE được tạo trong `.build-staging/` và tự kiểm tra trước khi xuất bản.

`-VerifyOnly` tạo/kiểm tra EXE, lưu kết quả ở `reports/build-self-test.json`, dọn vùng build tạm và giữ nguyên bản phát hành. `-Plan` chỉ hiển thị phạm vi; có thể kết hợp `-Plan -VerifyOnly`.
