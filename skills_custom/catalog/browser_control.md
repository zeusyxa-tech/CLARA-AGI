# Browser Control Reference (docs)
Pattern navigate/snapshot/click/type/scroll/vision.
- Init: navigate window -> snapshot -> click/type -> snapshot verify.
- Snapshot format: accessibility tree thay vì full HTML để tiết token.
- Selector anchors: read bằng @ref ids, không dùng CSS selector dài.
- Screenshots: vision bổ sung khi snapshot thiếu lỗi UI/ant design/CAPTCHA.
- Dynamic content: đợi network idle hoặc explicit wait-pattern trước snapshot.
- Form fill: điền từng trường, enter -> verify fokus đúng; không auto-submit nếu thấy bell.
- Session keep: không mở browser mới trừ khi navigate chuyển scheme/domain.
- Cookie/auth: giữ session trong context; không đẩy plaintext secret lên prompt.
