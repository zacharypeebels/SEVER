from main import ActionJob, ActionMode, JobStatus, WorkerQueue, drain, process_job


def test_cancel_reclaims_full_monthly():
    job = process_job(ActionJob(1, "Netflix", 15.49, "mo", ActionMode.CANCEL))
    assert job.status == JobStatus.DONE
    assert job.reclaimed_monthly == 15.49
    assert "canceled" in job.result_message


def test_pause_yearly_reclaims_monthly_equivalent():
    job = process_job(ActionJob(8, "Calm", 69.99, "yr", ActionMode.PAUSE))
    assert job.status == JobStatus.DONE
    assert job.reclaimed_monthly == 5.83


def test_haggle_reduces_price():
    job = process_job(ActionJob(4, "Adobe", 59.99, "mo", ActionMode.HAGGLE))
    assert job.new_price == 37.19
    assert job.reclaimed_monthly == 22.8


def test_processing_is_idempotent():
    job = process_job(ActionJob(1, "Netflix", 15.49, "mo", ActionMode.CANCEL))
    first_reclaimed = job.reclaimed_monthly
    process_job(job)
    assert job.reclaimed_monthly == first_reclaimed


def test_drain_processes_all_pending():
    queue = WorkerQueue()
    queue.enqueue(ActionJob(1, "Netflix", 15.49, "mo", ActionMode.CANCEL))
    queue.enqueue(ActionJob(7, "Spotify Premium", 11.99, "mo", ActionMode.PAUSE))
    done, reclaimed = drain(queue)
    assert done == 2
    assert reclaimed == 27.48
    assert queue.pending() == []
