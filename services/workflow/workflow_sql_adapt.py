"""
Translate common Postgres SQL patterns to SQLite for workflow cursors.
"""

from __future__ import annotations

import re
from typing import Any, List, Sequence, Tuple


def adapt_sql(sql: str, params: Sequence[Any]) -> Tuple[str, Tuple[Any, ...]]:
    """
    - %s → ?
    - strip ::jsonb, ::uuid, ::text
    - expand = ANY(?) with a list parameter to IN (?,?,?)
    """
    sql = sql.replace("%s", "?")
    for pat in (
        r"::jsonb\b",
        r"::uuid\b",
        r"::text\b",
        r"::int\b",
    ):
        sql = re.sub(pat, "", sql)

    params_list: List[Any] = list(params)
    while True:
        m = re.search(r"=\s*ANY\(\?\)", sql)
        if not m:
            break
        idx = next(
            (i for i, p in enumerate(params_list) if isinstance(p, (list, tuple))),
            None,
        )
        if idx is None:
            break
        seq = list(params_list[idx])
        params_list.pop(idx)
        if not seq:
            repl = " IN (NULL) AND 1=0"
            sql = sql[: m.start()] + repl + sql[m.end() :]
            continue
        placeholders = ",".join("?" * len(seq))
        repl = f" IN ({placeholders})"
        for j, v in enumerate(seq):
            params_list.insert(idx + j, v)
        sql = sql[: m.start()] + repl + sql[m.end() :]

    return sql, tuple(params_list)
