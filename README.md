# Handout Generator

English | [简体中文](README.zh-CN.md)

An LLM-driven pipeline that turns reference PDFs into typeset high-school math handouts (LaTeX → PDF), in a **teacher edition** (with full solutions) and a **student edition** (solutions replaced by blank answer space).

Built as a freelance project for a tutoring client; used to produce handouts for 30+ topics in analytic geometry and probability & statistics. Handout content is in Chinese.

## The problem

Asking an LLM to write a complete LaTeX handout in one shot works for text but fails in two predictable ways:

1. **Figures.** Free-form TikZ written by the model is frequently broken (does not compile) or geometrically wrong (e.g., foci in the wrong place, asymptotes with the wrong slope).
2. **Compilation.** Small LaTeX errors (unbalanced braces in `tcolorbox` titles, unsupported packages, stray newlines in nodes) cause the whole document to fail.

## The approach

**Figures: structured specs instead of free-form code.** The model is not allowed to write TikZ. It outputs a small JSON description of each figure, and Python renders it through parameterized templates (`tikz_templates.py`), so every figure is syntactically valid and mathematically consistent with its parameters:

```json
{
  "fig_type": "hyperbola_x",
  "a": 1, "b": 1.732,
  "show_asymptotes": true, "show_foci": true,
  "lines": [{"slope": 0.5, "intercept": 1}],
  "extra_points": [{"label": "A", "x": 2, "y": 1.5, "pos": "above right"}]
}
```

Supported figure types: ellipse, hyperbola, parabola (two orientations each), line–circle, and line–conic overlays.

**Compilation: deterministic cleanup, then a repair loop.** Model output is passed through a rule-based sanitizer for known failure patterns, then compiled with XeLaTeX. If compilation fails, the parsed error and the source are sent back to the model for a fix, up to 3 attempts, with a backup kept at each step.

## Pipeline

```
reference PDFs ──► text extraction (PyMuPDF; exam papers prioritized)
                         │
syllabus entry ──► prompt builder ──► DeepSeek API
                                          │
                     extract LaTeX ◄──────┘
                          │
                     sanitize (rule-based fixes)
                          │
                     JSON figure specs ──► TikZ templates
                          │
            [student mode: strip solutions]
                          │
                     XeLaTeX compile ──fail──► LLM repair (≤3 tries)
                          │
                         PDF
```

## Results

- A 35-topic batch compiled with **zero failures** after the figure-spec system and repair loop were added.
- Remaining limitation: **compiling is not the same as being correct.** The model can still produce mathematically wrong statements or solutions; these are not detected automatically and require human review.

## Usage

```bash
pip install -r requirements.txt
# requires a TeX distribution with XeLaTeX and CJK fonts (e.g., TeX Live, MacTeX, MiKTeX)

# .env
DEEPSEEK_API_KEY=your_key
# XELATEX_PATH=/path/to/xelatex   # optional, if xelatex is not on PATH

python generate_handout.py                         # list available topics
python generate_handout.py "椭圆方程" --mode both    # one topic, teacher + student
python generate_handout.py --all --mode both        # whole syllabus
```

Reference PDFs go in `data/gaokao/` (past exam papers, used first) and `data/raw_pdfs/`. They are **not included** in this repository for copyright reasons. Outputs are written to `output/tex/` and `output/pdf/`.

## Files

| File | Role |
|------|------|
| `generate_handout.py` | Orchestration: syllabus, prompt, LLM calls, sanitizer, student mode, compile + repair |
| `tikz_templates.py` | JSON figure spec → TikZ renderer |

## Future work

- Automatic checks on mathematical content (e.g., numerically verifying answers to computational problems).
- More figure types (3D geometry, statistical charts).
