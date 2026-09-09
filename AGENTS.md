# AGENTS.md

The working context for this repository lives in [CLAUDE.md](CLAUDE.md), which
is written for any coding agent rather than one in particular. Read it first.

The two things most likely to trip an agent up, in short:

1. **The published bytes are an interface.** Key order, `True` rather than
   `true`, CRLF row endings, and integer `25` beside float `22.5` are all
   load-bearing and all pinned by `tests/test_baseline.py`.
2. **Several roadmap items are policy, not bugs.** Whether a bot's commits
   count, and whether missing contributor data is penalised maximally or not
   at all, are decisions to raise rather than settle.
