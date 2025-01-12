# == Concurrency ==
INTERRUPTED_BY_ABORT_SIGNAL = 'Work interrupted by a celery task abort signal.'


def proxy_wall_results(filename: str) -> str:
    return f'The results are stored in {filename}'


# == API Requests Flow ==
REQUEST_BEING_PROCESSED = 'Your request is being processed. Check back later.'
