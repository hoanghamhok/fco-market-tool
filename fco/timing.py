"""Short initial polling steps while retaining the full readiness wait budget."""


def readiness_delays(budget, initial=0.02, maximum=0.08):
    delay = initial
    while budget > 1e-9:
        step = min(delay, budget)
        yield step
        budget -= step
        delay = min(delay * 2, maximum)
