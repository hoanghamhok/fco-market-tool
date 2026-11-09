# FCO Market

Ứng dụng desktop Windows x64 cho FC Online: tính lương đội hình, tính thuế chuyển nhượng và canh giá. Giao diện HTML/CSS/JavaScript chạy trong WebView2; Python xử lý nghiệp vụ và OCR.

## Bắt đầu

- **Người sử dụng:** đọc [hướng dẫn](docs/HUONG-DAN.html) và [cách mở ứng dụng](docs/DOC-TRUOC.txt).
- **Phát triển:** Python 3.13 x64; chạy `setup.bat`, sau đó `start.bat`.
- **Build EXE:** `build.bat` kiểm tra EXE trước khi xuất vào `release/` và Downloads.
- **Phát hành/cập nhật:** [hướng dẫn GitHub Releases và cập nhật trong ứng dụng](docs/CAP-NHAT.md).
- **Trách nhiệm từng phần:** xem [kiến trúc](docs/ARCHITECTURE.md).

## Cấu trúc

```text
app.py                 Điểm chạy ứng dụng
fco/                   Mã Python đang sử dụng
  calculators/         Tính lương và thuế
  diagnostics/         Tự kiểm tra OCR và giao diện EXE
ui/                    HTML, CSS, JavaScript của giao diện
tests/                 Kiểm thử hồi quy
assets/                Biểu tượng và ảnh kiểm thử OCR
scripts/               Công cụ build
docs/                  Hướng dẫn, kiến trúc và lịch sử
legacy/tkinter/        Giao diện cũ để tham khảo
vendor/                OCR models, giấy phép và nguồn thư viện
```

`.venv/`, `node_modules/`, `reports/`, `release/` và dữ liệu chạy được bỏ qua trong Git. `data-v3/` chứa dữ liệu khi chạy mã nguồn; EXE giữ dữ liệu trong `FCO-Market-3-data/` cạnh EXE.

## Kiểm tra

Tối ưu tốc độ 4.1.0 và cách đo: xem [PERFORMANCE.md](docs/PERFORMANCE.md).

Chạy từ thư mục dự án:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py --self-test reports/source-self-test.json
```

Kiểm tra đóng gói, giữ nguyên bản phát hành đang dùng:

```powershell
.\build.bat -VerifyOnly
```

`build.bat -Plan` chỉ hiển thị phạm vi build/dọn dẹp. Khi build hoặc tự kiểm tra thất bại, giữ EXE trước và thư mục tạm để chẩn đoán. Không xóa dữ liệu người dùng.

## Định dạng mã

Công cụ phát triển tách khỏi thư viện chạy ứng dụng:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm ci
.\.venv\Scripts\python.exe -m black app.py fco tests legacy
npm run format
```

Dùng Black với `--check` hoặc `npm run format:check` để kiểm tra định dạng. Node.js chỉ cần cho công cụ định dạng; người dùng EXE không phải cài Node.js hoặc Python.

Giao diện Tk cũ được giữ tại `legacy/tkinter/`. [HISTORY.md](docs/HISTORY.md) lưu tài liệu trước khi tổ chức lại; các đường dẫn/lệnh cũ trong đó chỉ để tra cứu.
