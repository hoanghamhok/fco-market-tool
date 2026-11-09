# Phát hành và cập nhật FCO Market

Bản 4.2.0 bổ sung cập nhật trong ứng dụng qua GitHub Releases của
`hoanghamhok/fco-market-tool`. Người dùng bản cũ tải 4.2.0 thủ công một lần.
Repo phát hành phải công khai; ứng dụng không chứa GitHub token.

## Phát hành một bản mới

### Tự động trên GitHub

Tăng `VERSION` trong `fco/__init__.py` rồi đẩy thay đổi lên nhánh `main`.
Workflow **Publish Windows release** tự cài môi trường Windows/Python 3.13,
chạy bộ kiểm thử, đóng gói và kiểm tra EXE/giao diện, thử cập nhật/khôi phục,
rồi tạo Release kèm EXE và SHA256SUMS.txt. Chỉ công bố sau khi tất cả kiểm tra
thành công. Xem tiến độ trong tab Actions. Có thể chạy lại bằng Run workflow;
workflow không ghi đè Release đã tồn tại với cùng phiên bản.

Workflow chỉ dùng quyền ghi nội dung của chính repo để tạo Release;
không cần thêm token cá nhân vào mã nguồn hay ứng dụng.

### Thực hiện thủ công

1. Đổi `VERSION` trong `fco/__init__.py`, ví dụ `4.2.1`. Luôn tăng phiên bản
   theo dạng `major.minor.patch`; không ghi đè bản cũ với cùng số phiên bản.
2. Chạy `build.bat`. Chỉ dùng file sau khi build và tự kiểm tra thành công.
3. Trong GitHub → Releases → Draft a new release, tạo tag đúng phiên bản,
   ví dụ `v4.2.1`, ghi nội dung thay đổi.
4. Đính kèm **cả hai file** từ `release/`:
   - `FCO-Market-4.2.1.exe`
   - `SHA256SUMS.txt`
5. Phát hành bản chính thức, đánh dấu là Latest; không chọn Pre-release.

Chỉ push mã nguồn hoặc tạo tag sẽ chưa cung cấp file để cập nhật.
SHA256SUMS.txt được build tự sinh từ đúng EXE đã kiểm tra. Không lấy checksum
của một lần build khác. Trình cập nhật ưu tiên digest SHA-256 do GitHub cung cấp;
nếu digest chưa có, nó dùng SHA256SUMS.txt trong cùng Release.

## Người dùng cập nhật

- Bản EXE tự kiểm tra khi khởi động; cũng có nút **Kiểm tra cập nhật** ở góc trái.
- Khi có bản mới, chọn **Tải bản cập nhật**; tiến độ tải hiện trong ứng dụng.
- Sau khi tải xong, chọn **Khởi động lại để cập nhật**. Dừng phiên canh giá
  trước khi tải hoặc khởi động lại.
- Có thể chọn **Để sau** và tiếp tục dùng bản hiện tại. Nếu đóng ứng dụng
  trước khi chọn khởi động lại, lần sau kiểm tra/tải lại để cập nhật.
- Chạy mã nguồn chỉ cho phép kiểm tra phiên bản; không thay thế Python đang chạy.

## EXE và dữ liệu

Bộ cập nhật tải vào `FCO-Market-3-data/updates/<mã>/`. Chỉ thay file EXE đang
chạy, giữ nguyên tên/vị trí EXE để shortcut cũ tiếp tục hoạt động. Vì vậy tên file
có thể vẫn là `FCO-Market-4.2.0.exe` sau khi cập nhật: phiên bản thực hiển thị
trong ứng dụng. Mọi cài đặt và lịch sử vẫn nằm trong `FCO-Market-3-data` cạnh EXE.

Không cập nhật trong thư mục chỉ đọc. Nếu có nhiều cửa sổ cùng chạy một EXE,
đóng các cửa sổ còn lại trước khi khởi động lại để cập nhật.

File tải được kiểm tra kích thước và SHA-256 trước khi cho cài. Một bản sao
EXE hiện tại chạy riêng làm bộ cập nhật, chờ ứng dụng đóng và chờ Windows nhả
file. Dữ liệu và hàng đợi lưu giao diện được giữ trong luồng đóng bình thường.

Bản cũ được giữ tại `updates/<mã>/previous.exe`; nếu thay file hoặc mở tiến
trình mới thất bại, bộ cập nhật cố khôi phục EXE cũ. Đây là khôi phục lỗi thay
file/khởi chạy tiến trình, không phải tự phát hiện mọi lỗi nghiệp vụ của bản mới.
Kết quả gần nhất nằm ở `updates/result.json`. Có thể xóa các thư mục mã cũ
khi đã xác nhận bản mới hoạt động tốt và không có cập nhật đang chạy.

## Kiểm tra trước khi phát hành

Chạy bộ kiểm thử và build có tự kiểm tra OCR/giao diện. Trước khi công bố
Release, xác nhận hai file EXE và `SHA256SUMS.txt` đúng cùng một bản build.
Chạy `.venv\Scripts\python.exe scripts\verify_updater.py release\FCO-Market-4.2.1.exe`
để kiểm tra thực tế bộ cập nhật đóng gói: cập nhật thành công, từ chối file sai
checksum và khôi phục sau lỗi khởi chạy. Phép kiểm tra dùng thư mục tạm trong
`reports/`, giữ nguyên dữ liệu thật, không kết nối mạng.

Từ 4.2.1, bộ cập nhật còn thử khởi chạy EXE vừa tải bằng chế độ kiểm tra ẩn,
kiểm tra phiên bản bên trong và tài nguyên giao diện trước khi cho cài.

Để kiểm tra trực tiếp qua GitHub, cài một bản có bộ cập nhật, phát hành bản
cao hơn kèm đủ hai file, rồi thử tải/khởi động lại trong ứng dụng. Đường này
chỉ hoạt động sau khi có Release công khai hợp lệ.
