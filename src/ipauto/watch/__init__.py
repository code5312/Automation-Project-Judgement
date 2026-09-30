"""Premise watching and review-request generation.

Not implemented yet — phase 4 (docs/PIPELINE.md 단계 4). Will periodically
re-check each stored Premise's expected value against its source (KIPRIS
re-lookup by 출원번호, GitHub commit, Jira field, document hash) using set
comparison for list-like fields, and create a ReviewRequest that routes back
to the judgment card when a premise changes, its source disappears, a new
similar patent appears, or its review deadline passes.
"""
