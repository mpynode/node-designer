# MPyDeformer_RBF_Wrap_Deformer -- compile report

Generated 2026-09-09 14:57

| node | status | assist | optimize | detail |
|---|---|---|---|---|
| `rbfWrapDeformer` | compiled | -- | **6616.12x** | [report](build/stages/rbfWrapDeformer/REPORT.md) |

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
