"""Read-only probe: how much of Viber's window does UI Automation expose? Prints counts, no message text."""
import collections

import uiautomation as auto

win = auto.WindowControl(searchDepth=1, Name="Rakuten Viber")
print("exists:", win.Exists(3, 1))
counts = collections.Counter()
named = 0
total = 0


def walk(ctrl, depth=0, limit=7):
    global named, total
    if depth > limit:
        return
    for c in ctrl.GetChildren():
        total += 1
        counts[c.ControlTypeName] += 1
        if c.Name:
            named += 1
        walk(c, depth + 1, limit)


walk(win)
print("total controls:", total, "with names:", named)
print(counts.most_common(12))
