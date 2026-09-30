"""Event/candidate triage (무관 / 관련 / 애매 라우팅).

Not implemented yet — phase 3 (docs/PIPELINE.md 단계 3). Will take an Event
and candidate IPAssets, apply the IPC/keyword/embedding/LLM signals described
in docs/DESIGN.md 트리아지, and route to auto-close, judgment-card
generation, or 게이트 A for human triage. See docs/PIPELINE.md for the five
ambiguous-routing rules this module must implement.
"""
