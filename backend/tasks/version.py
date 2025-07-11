from backend.api_types import TaskContext

def version_task(ctx: TaskContext, args: dict):
    return {"version": "1.0.0"}