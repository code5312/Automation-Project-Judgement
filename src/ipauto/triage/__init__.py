"""Event/candidate triage (무관 / 관련 / 애매 라우팅).

``llm_classifier`` (단계 3) implements one of the four docs/DESIGN.md
트리아지 signals — LLM 구조화 판정. The other three (IPC 주신호, 개념
키워드, 임베딩 유사도) and the actual routing to auto-close, judgment-card
generation, or 게이트 A for human triage are not implemented yet. See
docs/PIPELINE.md for the five ambiguous-routing rules that combine these
signals, still to be built.
"""
