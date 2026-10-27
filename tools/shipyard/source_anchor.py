"""Exact-once anchor replacement for CPU source projections."""


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('CPU source anchor drift: ' + before[:80])
    return source.replace(before, after, 1)
