"""One history snapshot per run; never suppress an unexamined new job."""
_ids = set()

def seed(ids):
    _ids.clear()
    _ids.update(ids)

def seen(job_id):
    return job_id in _ids
