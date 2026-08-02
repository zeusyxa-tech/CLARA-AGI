# CLI Shell Reference (docs)
CLARA run shell mode thiết kế an toàn.
- spawn: dùng subprocess với cwd ràng buộc workspace, không shell=True.
- PTY: Hermes cấp terminal nếu tool cần; output streaming text vẫn capture được.
- Exit-codes: rõ phân biệt thành công / lỗi / timeout.
- Pager aware: disable pager bằng environment nếu tool tự gọi interactive CLI.
- Limit: stdout cap 50KB; báo khi vượt gợi ý --no-resume.
- Interactive: không cấp stdin cho background job trừ khi explicit.
- Noiste: strip ANSI nếu có, decode utf-8 with replace.
