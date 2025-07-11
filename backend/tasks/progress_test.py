from backend.api_types import TaskContext

def progress_test_task(ctx: TaskContext, args: dict):
    total = int(args.get('total', 5))
    for i in range(1, total + 1):
        ctx.emit_progress(i, total)
        if i == total // 2:
            ctx.emit_warning("You're halfway there!")
        eventlet.sleep(1)
    return {"message": "Progress test complete"}