# Handout Generator

[English](README.md) | 简体中文

一条基于 LLM 的 pipeline：把参考资料 PDF 转换成排版好的高中数学讲义（LaTeX → PDF），同时生成**教师版**（含完整解答）和**学生版**（解答替换为留白作答区）。

本项目是为一家辅导机构客户做的外包项目，已用于制作解析几何与概率统计方向 30 多个专题的讲义。讲义内容为中文。

## 要解决的问题

让 LLM 一次性写出整份 LaTeX 讲义，文字部分没问题，但有两类可预见的失败：

1. **图形。** 模型自由编写的 TikZ 代码经常编译不通过，或者几何上是错的（例如焦点位置不对、渐近线斜率不对）。
2. **编译。** 一些细小的 LaTeX 错误（`tcolorbox` 标题括号不匹配、使用了不支持的宏包、节点里多余的换行）就会导致整份文档编译失败。

## 解决方法

**图形：用结构化描述代替自由代码。** 不允许模型直接写 TikZ。模型只为每张图输出一段简短的 JSON 描述，再由 Python 通过参数化模板（`tikz_templates.py`）渲染成 TikZ。这样每张图在语法上一定合法，在数学上也一定与参数一致：

```json
{
  "fig_type": "hyperbola_x",
  "a": 1, "b": 1.732,
  "show_asymptotes": true, "show_foci": true,
  "lines": [{"slope": 0.5, "intercept": 1}],
  "extra_points": [{"label": "A", "x": 2, "y": 1.5, "pos": "above right"}]
}
```

支持的图形类型：椭圆、双曲线、抛物线（各两种朝向）、直线与圆、直线与圆锥曲线叠加。

**编译：先做确定性清理，再进入修复循环。** 模型输出先经过一个基于规则的 sanitizer，修复已知的出错模式，然后用 XeLaTeX 编译。编译失败时，把解析出的报错和源码发回给模型修复，最多尝试 3 次，每一步都保留备份。

## Pipeline

```
参考 PDF ──► 文本提取（PyMuPDF；高考真题优先）
                  │
大纲条目 ──► prompt 构建 ──► DeepSeek API
                                  │
              提取 LaTeX ◄────────┘
                  │
              sanitize（规则修复）
                  │
              JSON 图形描述 ──► TikZ 模板
                  │
     [学生版模式：去掉解答]
                  │
              XeLaTeX 编译 ──失败──► LLM 修复（≤3 次）
                  │
                 PDF
```

## 结果

- 加入图形描述系统和修复循环后，一批 35 个专题全部编译成功，**零失败**。
- 仍存在的局限：**编译通过不等于内容正确。** 模型仍可能写出数学上错误的结论或解答，这类错误目前无法自动检测，需要人工审核。

## 使用方法

```bash
pip install -r requirements.txt
# 需要安装带 XeLaTeX 和中文字体的 TeX 发行版（如 TeX Live、MacTeX、MiKTeX）

# .env
DEEPSEEK_API_KEY=your_key
# XELATEX_PATH=/path/to/xelatex   # 可选，xelatex 不在 PATH 中时填写

python generate_handout.py                         # 列出所有专题
python generate_handout.py "椭圆方程" --mode both    # 单个专题，同时生成教师版和学生版
python generate_handout.py --all --mode both        # 生成整个大纲
```

参考 PDF 放在 `data/gaokao/`（高考真题，优先使用）和 `data/raw_pdfs/`。出于版权原因，这些文件**不包含**在本仓库中。输出文件写入 `output/tex/` 和 `output/pdf/`。

## 文件说明

| 文件 | 作用 |
|------|------|
| `generate_handout.py` | 主流程：大纲、prompt、LLM 调用、sanitizer、学生版处理、编译与修复 |
| `tikz_templates.py` | JSON 图形描述 → TikZ 渲染器 |

## 后续工作

- 对数学内容做自动检查（例如对计算题的答案做数值验证）。
- 支持更多图形类型（立体几何、统计图表）。
