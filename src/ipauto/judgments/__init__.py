"""Human judgment storage: validate, save (append-only), and compare against history.

Storage is SQLite (``ipauto.db``), keyed on (출원번호, 검토 기술). A
re-judgment for the same key is chained via ``previous_judgment_id``, never
an UPDATE. ``migrate_json.py`` moves the legacy ``data/judgments.json``
prototype file's rows across losslessly and idempotently.
"""
