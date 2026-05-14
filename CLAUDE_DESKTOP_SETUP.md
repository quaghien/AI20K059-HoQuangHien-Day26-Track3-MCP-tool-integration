# Hướng Dẫn Kết Nối Claude Desktop Với MCP Server Của Lab

## Thông tin sinh viên

- Họ tên: Hồ Quang Hiển
- MSSV: 2A202600059

## Mục tiêu

Tài liệu này hướng dẫn từng bước để kết nối `Claude Desktop` với MCP server của repo này, theo cách phù hợp nhất cho bài lab:

- dùng local stdio MCP server
- cấu hình bằng `claude_desktop_config.json`
- verify được tools, resources và error handling
- bám sát yêu cầu demo `Claude Desktop` trong slide

Lưu ý quan trọng:

- trên máy của bạn, resource MCP trong Claude Desktop chat hoạt động ổn định nhất khi được thêm từ giao diện `Connectors`
- sau khi resource đã được đính kèm vào chat, Claude mới đọc và tóm tắt resource đó ổn định
- vì vậy, khi demo, không nên ưu tiên cách gõ tay `schema://...` nếu mục tiêu là làm bài chắc chắn

## Nguồn đã kiểm tra

Mình đã đối chiếu lại với các tài liệu sau:

- Anthropic Claude Code MCP docs: https://code.claude.com/docs/en/mcp
- Anthropic Help Center, “Getting Started with Local MCP Servers on Claude Desktop”, ngày `March 16, 2026`: https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop
- Model Context Protocol docs, “Connect to local MCP servers”: https://modelcontextprotocol.io/docs/develop/connect-local-servers

Các điểm chính đã xác minh:

- Claude Desktop local MCP dùng file `claude_desktop_config.json`
- Trong Claude Desktop, vào `Settings` → `Developer` → `Edit Config` để mở file config
- Sau khi sửa config, cần `quit` hẳn Claude Desktop rồi mở lại
- Có thể kiểm tra MCP server qua `Connectors` hoặc `Developer settings / logs`
- MCP docs ghi rõ vị trí config mặc định:
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`

## Điều cần hiểu trước

Repo này chạy MCP server bằng Python trong env conda `aitclab`.

Điểm dễ lỗi nhất là:

- bạn đang dùng `Claude Desktop` trên Windows
- nhưng repo và env `aitclab` lại nằm trong `WSL2`
- Claude Desktop spawn server như một process của Windows
- vì vậy nó không thể chạy trực tiếp executable Linux kiểu `/home/.../python`

Nếu config như sau thì rất dễ lỗi:

```text
command = /home/quanghien/miniconda3/envs/aitclab/bin/python
```

Lỗi thường thấy:

```text
spawn /home/quanghien/miniconda3/envs/aitclab/bin/python ENOENT
```

Cách đúng cho `Windows Claude Desktop + WSL2` là:

- `command` dùng executable Windows:

```text
C:\Windows\System32\wsl.exe
```

- còn lệnh Python thật sẽ chạy bên trong:

```text
bash -lc "source ... && conda activate aitclab && python /home/.../mcp_server.py ..."
```

Đây là khuyến nghị triển khai thực tế để tránh lỗi `ENOENT`, không phải câu trích nguyên văn từ Anthropic.

## Phân biệt 2 nơi dùng MCP

Đây là điểm rất dễ nhầm:

1. `Claude Desktop` chat app
   - dùng `claude_desktop_config.json`
   - kiểm tra qua `Connectors`

2. `Code` tab
   - không dùng cùng config ở trên
   - theo docs của Anthropic, `Code` tab dùng MCP config kiểu `~/.claude.json` hoặc `.mcp.json`

Vì vậy, file hướng dẫn này dành cho:

- chat app của Claude Desktop
- menu `+` → `Connectors`

không phải cho `Code` tab.

## Bước 1: Chuẩn bị database

Mở terminal trong repo:

```bash
cd /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration
eval "$(conda shell.bash hook)"
conda activate aitclab
python implementation/init_db.py
```

Kết quả mong đợi:

- tạo file `implementation/lab.db`

## Bước 2: Mở file config của Claude Desktop

Theo MCP docs, flow chuẩn là:

1. Mở `Claude Desktop`
2. Mở menu ứng dụng Claude
3. Chọn `Settings...`
4. Vào tab `Developer`
5. Bấm `Edit Config`

File mở ra sẽ là `claude_desktop_config.json`.

Nếu bạn muốn tự mở tay theo path mặc định:

- macOS:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

- Windows:

```text
%APPDATA%\Claude\claude_desktop_config.json
```

## Bước 3: Dán config cho lab này

Bạn có 2 lựa chọn trong repo:

- Mẫu tổng quát: [claude_desktop.mcp.json.example](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop.mcp.json.example)
- Mẫu đã điền sẵn đúng đường dẫn máy này: [claude_desktop_config.local.example.json](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop_config.local.example.json)

Nếu đang làm trực tiếp trên máy hiện tại, dùng nội dung này là nhanh nhất:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "C:\\Windows\\System32\\wsl.exe",
      "args": [
        "bash",
        "-lc",
        "source ~/miniconda3/etc/profile.d/conda.sh && conda activate aitclab && python /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/implementation/mcp_server.py --db-path /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/implementation/lab.db"
      ],
      "env": {}
    }
  }
}
```

Lưu ý:

- tất cả path phải là path tuyệt đối
- `command` là path Windows
- phần lệnh bên trong `bash -lc` dùng path Linux trong WSL
- không dùng path tương đối
- nếu file config đã có server khác, chỉ cần thêm block `sqlite-lab` vào trong `mcpServers`
- đừng đổi tên server thành `workspace` vì docs của Anthropic nói tên này là reserved trong Claude Code; để an toàn, cứ giữ `sqlite-lab`

## Bước 4: Restart Claude Desktop

Sau khi lưu `claude_desktop_config.json`:

1. Thoát hẳn Claude Desktop
2. Mở lại ứng dụng

Theo MCP docs, restart là cần thiết để app nạp config mới và start MCP server.

## Bước 5: Kiểm tra server đã lên chưa

Anthropic Help Center hiện hướng dẫn 2 cách xem:

### Cách 1: Qua Connectors

1. Mở một chat mới trong Claude Desktop
2. Bấm nút `+` ở gần ô chat
3. Chọn `Connectors`
4. Tìm server `sqlite-lab`

Bạn nên thấy:

- server đã connected
- danh sách tools hiện ra
- mục `Add from sqlite-lab`
- resource `Database schema`

### Cách 2: Qua Developer settings / logs

1. Vào `Settings`
2. Vào phần `Developer`
3. Xem connection status và logs

Nếu server có lỗi khởi động, đây là chỗ dễ thấy nhất.

## Bước 6: E2E test đúng tinh thần bài lab

Sau khi Claude Desktop thấy server `sqlite-lab`, bạn có thể test theo đúng yêu cầu chấm.

### Test 1: Tool discovery

Mục tiêu:

- chứng minh Claude Desktop nhận được 3 tools

Prompt gợi ý:

```text
Use the sqlite-lab MCP server and tell me which database tools are available.
```

Kỳ vọng:

- Claude thấy `search`
- Claude thấy `insert`
- Claude thấy `aggregate`

### Test 2: Đọc full schema resource

Thao tác đúng trên Claude Desktop chat:

1. Bấm `+`
2. Chọn `Connectors`
3. Chọn `Add from sqlite-lab`
4. Chọn `Database schema`
5. Sau khi resource được đính kèm, dùng prompt:

```text
Hãy tóm tắt schema database từ resource vừa được thêm.
```

Kỳ vọng:

- Claude đọc được resource
- nhắc tới `students`, `courses`, `enrollments`, `student_scores`

### Test 3: Đọc schema của một bảng

Prompt:

```text
Dựa trên resource vừa thêm, hãy cho tôi schema của bảng students.
```

Kỳ vọng:

- Claude đọc được schema riêng của `students`
- thấy `id`, `name`, `cohort`, `email`, `age`

### Test 4: Search hợp lệ

Prompt:

```text
Use sqlite-lab to show all students in cohort A1, ordered by name.
```

Kỳ vọng:

- Claude gọi tool `search`
- trả ra `An Nguyen`
- trả ra `Binh Tran`

### Test 5: Aggregate hợp lệ

Prompt:

```text
Use sqlite-lab to calculate the average score by cohort.
```

Kỳ vọng:

- Claude gọi `aggregate`
- có kết quả cho `A1`
- có kết quả cho `B2`

### Test 6: Insert hợp lệ

Prompt:

```text
Use sqlite-lab to insert a new student named Demo User in cohort C9 with email demo.user@example.com and age 22.
```

Kỳ vọng:

- Claude gọi `insert`
- trả lại payload vừa insert
- có `row_id`

### Test 7: Error handling

Prompt:

```text
Use sqlite-lab to search the table missing_table.
```

Kỳ vọng:

- Claude báo lỗi rõ ràng
- có nội dung kiểu `unknown table`

## Bước 7: Chụp ảnh hoặc quay video demo

Để khớp rubric và slide, nên lấy ít nhất các bằng chứng sau:

1. `Claude Desktop` đã connect `sqlite-lab`
2. danh sách tools
3. attach `Database schema` từ `Add from sqlite-lab`
4. Claude tóm tắt được schema từ resource đã đính kèm
5. một call `search` thành công
6. một call `aggregate` thành công
7. một call lỗi có chủ đích
8. nếu có thời gian, thêm một ảnh `insert` thành công

Nếu quay video khoảng 2 phút, flow ngắn gọn nên là:

1. terminal chạy `conda activate aitclab`
2. `python implementation/init_db.py`
3. mở `claude_desktop_config.json`
4. mở Claude Desktop
5. vào `Connectors`
6. chạy 3 prompt:
   - schema
   - search
   - invalid request

## Troubleshooting

### 1. Không thấy server `sqlite-lab`

Kiểm tra theo thứ tự:

1. đã restart Claude Desktop chưa
2. JSON có hợp lệ không
3. path trong `command` và `args` có phải absolute path không
4. file `implementation/lab.db` đã được tạo chưa
5. config có đang dùng `wsl.exe` để vào WSL không

### 2. Lỗi `ENOENT` hoặc spawn thất bại

Nguyên nhân thường là:

- `command` đang để path Linux trực tiếp như `/home/.../python`
- hoặc path script sai
- hoặc Claude Desktop đang chạy trên Windows nhưng config lại trỏ trực tiếp tới executable Linux

Sửa bằng cách:

- dùng đúng binary Windows:

```text
C:\Windows\System32\wsl.exe
```

- rồi bên trong `bash -lc` mới gọi Python trong WSL:

```text
source ~/miniconda3/etc/profile.d/conda.sh && conda activate aitclab && python /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/implementation/mcp_server.py --db-path /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/implementation/lab.db
```

### 3. Claude mở được server nhưng tool không chạy

Kiểm tra logs.

Theo MCP docs, log thường nằm ở:

- macOS: `~/Library/Logs/Claude`
- Windows: `%APPDATA%\\Claude\\logs`

File đáng xem:

- `mcp.log`
- `mcp-server-sqlite-lab.log`

### 4. Tool báo lỗi database

Chạy lại:

```bash
eval "$(conda shell.bash hook)"
conda activate aitclab
python implementation/init_db.py
```

### 5. Claude Desktop có giao diện Extensions thay vì flow cũ

Điểm này là bình thường.

Anthropic Help Center hiện đang đẩy mạnh `Desktop Extensions` cho local MCP servers. Tuy nhiên:

- bài lab của bạn yêu cầu config JSON
- local stdio config qua `claude_desktop_config.json` vẫn là một cơ chế được tài liệu MCP và Help Center nhắc tới

Vì vậy với bài này, cứ ưu tiên flow:

- `Settings`
- `Developer`
- `Edit Config`

## Checklist cuối trước khi nộp

- [ ] `implementation/lab.db` đã được tạo
- [ ] `claude_desktop_config.json` có server `sqlite-lab`
- [ ] `command` là `C:\Windows\System32\wsl.exe`
- [ ] bên trong `bash -lc` có `conda activate aitclab`
- [ ] Claude Desktop đã restart
- [ ] `sqlite-lab` xuất hiện trong `Connectors`
- [ ] test được `search`
- [ ] test được `insert`
- [ ] test được `aggregate`
- [ ] attach được `Database schema` từ `Connectors -> Add from sqlite-lab`
- [ ] Claude tóm tắt được schema từ resource đã đính kèm
- [ ] Claude trích được schema của bảng `students` từ resource đã đính kèm
- [ ] có ảnh hoặc video chứng minh error handling

## Gợi ý thao tác nhanh nhất trên đúng máy này

```bash
cd /home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration
eval "$(conda shell.bash hook)"
conda activate aitclab
python implementation/init_db.py
```

Sau đó:

1. Mở [claude_desktop_config.local.example.json](/home/quanghien/day26/AI20K059-HoQuangHien-Day26-Track3-MCP-tool-integration/claude_desktop_config.local.example.json)
2. Copy nội dung vào `claude_desktop_config.json`
3. Restart Claude Desktop
4. Vào `Connectors`
5. Attach `Database schema` từ `Add from sqlite-lab`
6. Chạy prompt demo
