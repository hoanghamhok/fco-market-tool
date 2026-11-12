# FCO Market 4.2.6

## Thay đổi 4.2.6

- Khi nhận diện lần đầu, ưu tiên OCR tiếng Việt cho tiêu đề Mua/Bán và đọc lại ảnh mới trong thời gian ngắn nếu khung hình đang vẽ dở.
- Ở cửa sổ game nhỏ, mở rộng vùng kiểm tra gạch chân tab vài pixel, ưu tiên nét số gốc trước ảnh nhị phân để tránh đọc nhầm mức cộng, và đọc nút Đăng ký lại với ngưỡng phù hợp cho chữ nhỏ nhưng vẫn yêu cầu đúng toàn bộ nhãn.
- Kiểm thử ảnh ở 67%, 85%, 100%, 115% và 150% kích thước gốc; giữ kiểm tra đúng cầu thủ, mức cộng, số lượng, tab và giá BP đầy đủ.

## Thay đổi 4.2.5

- Sửa lỗi dừng sau vài vòng trên máy khác khi tiêu đề hộp Mua/Bán bị OCR mờ lúc game vẽ lại. Sau lần nhận diện đầu, các vòng canh dùng loại hộp đã khóa và tiếp tục kiểm tra tab đang chọn, tên, mức cộng, ảnh thẻ, số lượng và MIN/MAX trước khi Esc hoặc mở lại.
- Thêm kiểm thử ảnh hộp có tiêu đề bị che: nhận diện ban đầu vẫn từ chối, còn vòng đã khóa đúng cầu thủ tiếp tục đọc được mà không bỏ các điều kiện xác minh còn lại.

## Thay đổi 4.2.4

- Ô giá mua tối đa / giá bán tối thiểu tự thêm dấu chấm phân tách hàng nghìn ngay khi nhập và giữ vị trí con trỏ.
- Thêm năm mốc chọn nhanh: 1 triệu, 10 triệu, 100 triệu, 1 tỷ và 10 tỷ BP; chọn mốc sẽ điền và lưu số BP đầy đủ.
- Tự kiểm tra giao diện WebView2 xác nhận định dạng, lưu giá, trạng thái nút và bố cục ở hai kích thước cửa sổ.

## Thay đổi 4.2.3

- Dùng ảnh chẩn đoán lỗi thật của huy hiệu +4 nền cam để sửa OCR: tách phần nét số tối khỏi nền màu và viền trước khi đọc. Ảnh lỗi nay nhận đúng +4 ở ba tỷ lệ; thử thêm +1, +2, +3 trên nền màu tương tự.
- Giữ các bước đọc lại ngắn khi hộp hoặc dòng lệnh đang vẽ dở như bản 4.2.2.

## Thay đổi 4.2.2

- Ưu tiên tách chữ số khỏi viền và mũi tên khi đọc mức cộng; thử nhận dạng chỉ chữ số nếu lượt đầu chưa rõ. Cải thiện trường hợp thẻ mức cộng thấp và giảm lượt OCR lặp trên vùng đã rõ.
- Khi hộp hoặc dòng lệnh vừa vẽ lại, thử đọc thêm từ ảnh mới trong thời gian ngắn trước khi kết luận lỗi. Không bấm Esc, rê chuột hay mở lại khi chưa xác minh đúng cầu thủ; ảnh sai thẻ kéo dài vẫn dừng.
- Kiểm thử hồi quy cho lỗi OCR thoáng qua trước Esc, dòng lệnh hiện chậm, thẻ vẽ dở sau mở lại và trường hợp sai thẻ kéo dài.

## Thay đổi 4.0.0 — Giao diện desktop mới

- Chuyển giao diện chính sang HTML/CSS/JavaScript trong cửa sổ WebView2; Python tiếp tục xử lý tính toán chính xác, OCR và điều khiển game.
- Thiết kế thể thao tối giản: nền than, xanh cỏ, thanh điều hướng bên trái, các biểu tượng đồng bộ và trạng thái lưu dữ liệu.
- **Đội hình:** nhập ngay trên sân, tổng cập nhật tức thì, phân bổ lương theo tuyến, đổi sơ đồ giữ dữ liệu riêng; có hoàn tác khi xóa lương.
- **Tính thuế:** bố cục giá bán/quyền lợi bên trái, bảng kê BP thực nhận bên phải. Tính bằng số nguyên ở Python để không mất độ chính xác với số BP lớn.
- **Canh giá:** tách cầu thủ theo dõi, điều kiện canh và nhật ký phiên. Giữ chạy thử mặc định, F8 để dừng, nhận diện đúng thẻ/số lượng/tab và giới hạn một lần gửi.
- Dùng lại `FCO-Market-3-data`, không cần nhập lại dữ liệu. Các tài nguyên giao diện nằm trong EXE, không tải font hoặc giao diện từ Internet.
- Cần Microsoft Edge WebView2 Runtime trên Windows. Máy hiện tại đã có; EXE tự kiểm tra cả WebView2, giao diện và OCR trước khi xuất bản.
- Tự kiểm tra UI ở 1200×860 và 980×720; kiểm tra nhập lương, chuyển sơ đồ, xóa/hoàn tác, lưu dữ liệu, tính thuế và khóa điều khiển khi phiên đang chạy. Không thực hiện giao dịch trong game khi tự kiểm tra.

### Cấu trúc giao diện

`ui/` chứa HTML/CSS/JavaScript; `fco/web_app.py` mở cửa sổ desktop; `fco/controller.py` nối giao diện với nghiệp vụ. `fco/window.py`, `salary_ui.py` và `tax_ui.py` là giao diện Tk cũ được giữ làm tham chiếu; ứng dụng chính không sử dụng chúng.

## Thay đổi 3.3.0 — Tính lương đội hình

- Tab **Tính lương** có hai sơ đồ theo ảnh tham chiếu: **4-3-3 · 2 CDM** (LW, ST, RW, CM, LDM, RDM, LB, LCB, RCB, RB, GK) và **4-1-4-1** (ST, LM, RM, LCM, RCM, CDM, LB, LCB, RCB, RB, GK).
- Nhập số lương nguyên không âm trực tiếp vào từng vị trí trên sân; tổng của 11 cầu thủ cập nhật ngay. Ô trống tính là 0.
- Mỗi sơ đồ lưu riêng, tự khôi phục khi mở lại. **Xóa lương sơ đồ** chỉ xóa sơ đồ đang chọn.
- Dữ liệu nằm trong `salary-settings.json` cùng thư mục dữ liệu hiện có. Tính lương không cần mở game hoặc nhận diện cầu thủ.

## Thư mục source và dọn build

Source cố định: `C:\Users\dkfbr\Downloads\fco-market-tool`. Sửa tại đây, không tạo thư mục source theo từng phiên bản.

`build.bat` build vào vùng tạm, chạy tự kiểm tra EXE, rồi xuất bản vào `release/` và Downloads. Khi hai bản EXE mới đã được xác minh, script tự xóa các EXE FCO cũ và thư mục build/cache tạm. Nếu build hoặc tự kiểm tra thất bại, giữ bản EXE trước. Dữ liệu `FCO-Market-3-data` được giữ nguyên. `build.bat -Plan` chỉ hiển thị phạm vi thực hiện, không build hay xóa file.

`setup.bat` chuẩn bị cả thư viện ứng dụng và PyInstaller cho lần build tiếp theo.

Ứng dụng Windows 64-bit: Canh reset, Tính thuế TTCN và Tính lương đội hình. Python, OCR tiếng Anh và tiếng Việt đã tích hợp trong EXE. Dữ liệu giữ trong `FCO-Market-3-data` cạnh EXE; bản nguồn dùng `data-v3/`.

## Thay đổi 3.2.5

- Nhận nút gửi theo loại hộp: mua là đỏ/cam, bán là xanh. Nút xám hoặc màu của loại giao dịch khác không được gửi.
- Sau khi hai lần đọc xác nhận giá đổi và đạt ngưỡng, dùng ngay ảnh vừa xác nhận để bấm MAX khi mua / MIN khi bán; không chụp lại hoặc đóng/mở thêm trước thao tác này.
- Sau click giá, đọc sớm theo từng nhịp ngắn thay vì chờ cố định 100 ms. Chỉ bấm MAX/MIN một lần; ô giá chưa cập nhật thì đọc lại có giới hạn. Vẫn cần hai lần đọc BP đầy đủ trùng nhau, đúng ngưỡng, thẻ và số lượng trước một lần gửi.
- Đã kiểm thử toàn luồng bằng ảnh nút mua đỏ Zambrotta: refresh → xác nhận giá đổi → MAX → kiểm tra BP → gửi đúng tọa độ nút đỏ một lần. Đây là kiểm thử mô phỏng thao tác, không gửi lệnh thật vào game.

- Tái hiện lỗi tab Mua thường trên ảnh PNG thật 191×35 px: OCR tiếng Anh đọc từ thường chỉ 31% tin cậy, tiếng Việt đạt 96%. Hai tab trong hộp mua/bán nay ưu tiên OCR tiếng Việt, kiểm tra chính xác tên tab và giữ điều kiện gạch chân đang chọn.
- Đối chiếu ảnh đầy đủ G. Zambrotta +5, MIN 630M, MAX/ô giá 770.000.000 BP, số lượng 1, ở ba tỷ lệ ảnh.
- Thêm hồi quy ảnh tab thực tế ở 85%, 100%, 115%, toàn bộ hộp mua, tab trái loại lệnh và nhãn rõ nhưng thiếu gạch chân. Không hạ ngưỡng giá hoặc bỏ kiểm tra tab.

- Sửa nguyên nhân lệch nhận diện tab trên cửa sổ phóng to: `GetWindowRect` gồm viền ẩn 8 px ở mỗi cạnh (1936×1048), trong khi game hiển thị 1920×1032. Chụp ảnh và click nay cùng dùng DWM extended frame bounds để loại viền ẩn.
- Đã tái hiện bằng ảnh thêm viền 8 px: nhận diện tab cũ từ chối, sau khi loại viền nhận đúng. Kiểm tra cả capture và click dùng cùng gốc tọa độ.
- F9 trong cửa sổ tool: sau 4 giây đọc tab từ ảnh chụp thật và lưu chẩn đoán cục bộ; không mua/bán. Khi đọc tab thất bại, tự lưu hai vùng tab/gạch chân và `diagnostics/parent-tab.json` với chữ OCR, độ tin cậy, kích thước ảnh, tỷ lệ gạch chân.

- Chờ bảng/tab DS của bạn hiện ổn định sau Esc; kết quả OCR tạm thời chưa rõ không còn làm rẽ nhầm sang luồng mua mới.
- Với giờ bắt đầu trống, thời gian canh bắt đầu sau 4 giây chuyển cửa sổ, không bị trừ vào khoảng chờ.

- Sửa phiên Canh reset dừng ngay khi đang ở bảng TTCN phía sau: sau khi Nhận diện, có thể bắt đầu từ hộp đang mở hoặc bảng TTCN. Tool xác minh bảng và mở lại trước; không Esc mù khi không có hộp.
- Hiện từng bước Esc / tìm nút / mở lại / kiểm tra giá. Nhật ký ghi mỗi vòng hoàn tất, kèm MIN/MAX.
- Chờ nút Đăng ký lại hiện sau hover; chỉ bấm một lần sau khi nhận diện chắc. Lỗi ghi rõ bước bị dừng.

- Canh trong một khung giờ Việt Nam do bạn đặt; tự Esc và mở lại hộp để lấy MIN/MAX mới nhất.
- Với lệnh đang treo: tìm đúng tên, mức cộng và trạng thái trong **DS của bạn**, rê chuột hiện **Đăng ký lại**, nhận diện nút rồi mở lại. Không bấm Hủy lệnh.
- Với mua mới từ bảng TTCN: mở lại bằng **Mua cầu thủ**. Sau khi mở, kiểm tra lại đúng thẻ, mức cộng và tab mua/bán đã nhận diện.
- Thêm OCR tiếng Việt cho nút nhỏ trên bảng. Giữ kiểm tra đúng tab, số lượng 1, thẻ cầu thủ và giá BP đầy đủ trước gửi.
- Báo rõ khi game chạy quyền cao hơn tool; người dùng chọn **Run as administrator** nếu cần.
- 64 kiểm thử, gồm ảnh hộp và bảng lệnh thực tế, Esc không phản hồi, nhầm thẻ, dòng trùng, khung giờ hết hạn và không gửi ở chế độ chạy thử.

## Cách dùng

1. Nếu FCO chạy quyền quản trị, mở EXE bằng chuột phải → **Run as administrator**.
2. Mở đúng hộp **Mua thường** hoặc **Bán từng cá nhân**, số lượng **1**. Khi đăng ký lại lệnh, mở từ nút **Đăng ký lại** trong **DS của bạn**. Giữ dòng cầu thủ nằm trong vùng danh sách đang thấy.
3. Bấm **Nhận diện · 4 giây**, chuyển lại game nếu cần. Kiểm tra ảnh thẻ, tên, mức cộng và MIN/MAX trên tool.
4. Nhập **giá mua tối đa** hoặc **giá bán tối thiểu** bằng số BP đầy đủ.
5. Nhập giờ bắt đầu dạng `HH:MM` hoặc `HH:MM:SS`, ví dụ `20:01:00`; để trống để bắt đầu ngay. Nhập thời gian canh từ **5–1.800 giây**, mặc định **120 giây**. Giờ dùng UTC+7. Nếu giờ đã qua và khung đó đã hết, lịch chuyển sang ngày hôm sau; trạng thái hiển thị cả ngày chạy.
6. Sau Nhận diện, có thể giữ hộp mở hoặc trở về bảng TTCN phía sau. Bật **Esc → mở lại bảng để lấy giá mới**, bấm **Canh reset**, giữ game ở phía trước. Tool chỉ đóng/mở trong khung giờ đã chọn. Giá đổi và đạt ngưỡng thì mua MAX / bán MIN; hết giờ thì dừng.

Mặc định bật **Chạy thử**: có Esc và mở lại bảng, nhưng không chọn giá hoặc gửi lệnh. Bỏ chọn để thực hiện lệnh thật. Mỗi phiên tối đa một lần gửi. **F8**, nút Dừng hoặc chuyển sang cửa sổ khác sẽ dừng thao tác.

Nút **Thử chọn MAX / MIN** là phép thử riêng: bấm giá tương ứng và đọc lại ô BP, không gửi lệnh.

## Cơ chế và phạm vi

- Mốc so sánh là MIN/MAX lúc Nhận diện. Mỗi vòng đóng/mở xong, đọc lại giá hai lần để xác nhận thay đổi. Mua bấm chữ MAX, bán bấm chữ MIN; không gõ giá.
- Giá K/M/B/T chỉ dùng phát hiện và kiểm tra sơ bộ. Trước gửi phải đọc số BP đầy đủ trong ô giá, khớp MIN/MAX và đạt ngưỡng cấu hình. Reset không đổi số hiển thị rút gọn sẽ không được phát hiện.
- Tốc độ phụ thuộc game, chụp ảnh và OCR. Có khoảng nghỉ giữa vòng để kiểm tra trạng thái; không cam kết slot đầu tiên hay độ trễ cố định.
- Vòng mở lại bảng hiện dùng bố cục cửa sổ TTCN đã quan sát. Hộp mua/bán tự tìm khung; bảng phía sau dùng vùng tương đối theo cửa sổ. Thay bố cục, độ phân giải, font hoặc cuộn danh sách có thể làm nhận diện dừng. Không tìm được duy nhất một dòng đúng tên và mức cộng thì dừng.
- Chưa duyệt nhiều cầu thủ hoặc tự tìm thời điểm reset từ máy chủ. Bán mới từ kho cầu thủ chưa có vòng mở lại; dùng luồng đăng ký lại trong DS của bạn. Mua mới và đăng ký lại mua có sẵn nhánh xử lý, nhưng đăng ký lại mua chưa được đối chiếu ảnh bảng lệnh mua thực tế.
- Nếu Esc không đóng được hộp, nút chưa đọc rõ hoặc mở nhầm thẻ, dừng và báo lỗi. Không tự bấm tiếp để đoán.
- Ghi nhật ký xuống đĩa trước lần gửi duy nhất. Nếu chưa xác minh được thông báo thành công, ghi `unverified`; kiểm tra DS của bạn rồi mới dùng **Đã kiểm tra lệnh trước**. Chưa tự xử lý hộp xác nhận bổ sung của game.
- Lỗi OCR nêu rõ trường đọc lỗi; ảnh vùng lỗi lưu cục bộ ở `diagnostics/last-field.png`. Kiểm thử ảnh và mô phỏng luồng không xác nhận giao dịch thành công trong game.

## Tính thuế

Nhập giá bán, chọn Không VIP/VIP/SVIP, coupon và quyền lợi PC. Ví dụ 7.600.000.000.000 BP, SVIP + coupon 30%, không PC → 6.384.000.000.000 BP. Phép tính cơ bản chưa xét giới hạn hoặc điều kiện mùa thẻ của coupon. Nguồn đối chiếu: https://fifaaddict.com/vn/fotax-calculator

## Nguồn và build

Dùng Python 3.13 64-bit. Chạy `setup.bat` để tạo môi trường và cài thư viện; sau đó `start.bat`. Cài thêm PyInstaller vào môi trường trước khi chạy `build.bat`; kết quả `release/FCO-Market-4.0.0.exe`.

```powershell
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe app.py --self-test self-test.json
```

EXE cũng nhận `--self-test <đường dẫn JSON>`; phép tự kiểm tra không chụp hoặc thao tác trong game. Ảnh kiểm thử đã che phần thông tin tài khoản ngoài vùng cần đọc. Nguồn và mã băm OCR ở `vendor/ocr-sources.json`, giấy phép ở `vendor/licenses/`.
