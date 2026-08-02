# Task Delegation Reference (docs)
- Orchestration: orchekz model fan-out/get-converge.
- Child contract: sau khi finish -> report summary, status, error, artifacts.
- Context handoff: đừng đẩy raw history, đẩy goal+invariant+result template nhỏ.
- Aggregation: merge child outputs lần lượt; nếu có conflict -> mặc định master decide.
- Bound concurrency: Hermes default.
- Cancellation: propagate cancel flag; no hard kill unless watchdog.
- Results: trả về handle / URL / path kiểm chứng được, không trả guess.
- Timeout policy: nếu child quá hạn -> raise error về master.
