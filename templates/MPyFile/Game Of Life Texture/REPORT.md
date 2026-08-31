# MPyFile_Game_Of_Life_Texture -- compile report

Generated 2026-08-28 17:57

| node | status | assist | optimize | detail |
|---|---|---|---|---|
| `gameOfLifeTex` | compiled | -- | **1.95x** | [report](build/stages/gameOfLifeTex/REPORT.md) |

## Layout

```
<Plugin>.bundle              the plug-in you load
build/source/                the C++ that was compiled -- and only that
build/stages/<Type>/         how it got there (kept; never swept)
  1_transpiled.cpp             deterministic, no AI
  2_assisted.cpp               AI filled the unported region(s)
  3_optimized/NN_<slug>.cpp    one file per optimize round, rejects included
  rounds.json                  machine-readable ledger
  REPORT.md                    this node's full story
```
