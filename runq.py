import sqlite3, sys
con = sqlite3.connect("study.db"); con.row_factory = sqlite3.Row
q = open(sys.argv[1]).read() if len(sys.argv)>1 else sys.stdin.read()
try:
    rows = con.execute(q).fetchall()
    if not rows: print("(no rows)")
    else:
        cols = rows[0].keys()
        w = [max(len(c), max(len(str(r[c])) for r in rows)) for c in cols]
        print("  ".join(c.ljust(x) for c,x in zip(cols,w)))
        print("  ".join("-"*x for x in w))
        for r in rows: print("  ".join(str(r[c]).ljust(x) for c,x in zip(cols,w)))
except Exception as e:
    print("ERROR:", e)
