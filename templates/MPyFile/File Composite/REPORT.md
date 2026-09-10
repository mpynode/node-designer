# MPyFile_File_Composite -- compile report

Generated 2026-09-09 15:33

| node | status | assist | optimize | detail |
|---|---|---|---|---|
| `compositeTexture` | compiled | -- | **138.44x** | [report](build/stages/compositeTexture/REPORT.md) |

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
