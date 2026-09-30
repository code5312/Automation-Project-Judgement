"""Human judgment storage: load, validate, save, and compare against history.

Storage is still the append-only JSON file in this phase. Phase 1
(docs/PIPELINE.md 단계 1) replaces the file with a SQLite ``Judgment`` table
keyed on (출원번호, 검토 기술), adds required reason/premise validation at
the schema level, and provides ``migrate_json.py`` to move this file's rows
across losslessly.
"""
