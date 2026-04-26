"""
generate_handout.py — 主程序 (v2: 教师版+学生版)

流程：
  1. 读取 data/raw_pdfs/ 下与topic相关的PDF全文
  2. 连同格式模板一起喂给 DeepSeek-V4-Pro
  3. LLM直接输出完整的教师版LaTeX（含答案）
  4. 若需要学生版，后处理去掉答案，替换为空白答题区
  5. xelatex编译为PDF
"""
import fitz
import logging
import re
import subprocess
import shutil
import sys
import argparse
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# ── 配置 ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
PDF_DIR     = BASE_DIR / "data" / "raw_pdfs"
TEX_DIR     = BASE_DIR / "output" / "tex"
PDF_OUT_DIR = BASE_DIR / "output" / "pdf"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL            = "deepseek-v4-pro"
MAX_TOKENS       = 163840
LATEX_CMD        = r"C:\Users\Kevin\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe"
LATEX_OPTS       = ["-interaction=nonstopmode", "-halt-on-error"]
MAX_RETRIES      = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# ── 课程大纲 ──────────────────────────────────────────────────────────────────
SYLLABUS = {
    "直线方程": {"key_points": ["倾斜角与斜率", "五种直线方程形式", "点到直线距离", "两直线位置关系"], "module": "解析几何"},
    "直线方程综合": {"key_points": ["直线系方程", "对称问题", "最值问题", "综合应用"], "module": "解析几何"},
    "圆方程": {"key_points": ["标准方程与一般方程", "圆的方程求法", "圆的几何要素"], "module": "解析几何"},
    "直线与圆": {"key_points": ["直线与圆的位置关系", "切线方程", "弦长公式"], "module": "解析几何"},
    "曲线与方程": {"key_points": ["曲线方程的概念", "参数方程初步", "轨迹求法"], "module": "解析几何"},
    "椭圆方程": {"key_points": ["标准方程", "焦点坐标", "a/b/c关系", "椭圆定义"], "module": "解析几何"},
    "椭圆的几何性质": {"key_points": ["顶点与轴", "离心率", "焦点三角形", "焦半径公式"], "module": "解析几何"},
    "直线与椭圆": {"key_points": ["弦中点问题", "切线", "韦达定理应用", "焦点弦"], "module": "解析几何"},
    "双曲线方程": {"key_points": ["标准方程", "渐近线", "离心率", "双曲线定义"], "module": "解析几何"},
    "双曲线的几何性质": {"key_points": ["顶点焦点", "渐近线方程", "焦半径", "焦点三角形"], "module": "解析几何"},
    "双曲线": {"key_points": ["直线与双曲线位置关系", "弦中点", "综合应用"], "module": "解析几何"},
    "抛物线方程": {"key_points": ["四种标准方程", "焦点准线", "抛物线定义"], "module": "解析几何"},
    "抛物线的几何性质": {"key_points": ["焦半径公式", "焦点弦", "切线", "光学性质"], "module": "解析几何"},
    "直线与抛物线": {"key_points": ["弦中点", "韦达定理", "焦点弦性质", "综合"], "module": "解析几何"},
    "圆锥曲线综合": {"key_points": ["综合判别", "定值问题", "范围最值", "非对称韦达定理"], "module": "解析几何"},
    "随机抽样": {"key_points": ["简单随机抽样", "系统抽样", "分层抽样", "样本与总体"], "module": "概率统计"},
    "样本估计总体": {"key_points": ["频率分布直方图", "茎叶图", "箱线图", "均值方差"], "module": "概率统计"},
    "古典概型": {"key_points": ["等可能事件", "古典概型公式", "几何概型"], "module": "概率统计"},
    "概率的基本性质与独立性": {"key_points": ["概率公理", "加法公式", "互斥事件", "独立事件乘法"], "module": "概率统计"},
    "计数原理": {"key_points": ["分类加法", "分步乘法", "实际应用"], "module": "概率统计"},
    "排列组合": {"key_points": ["排列数公式", "组合数公式", "常见模型", "隔板法"], "module": "概率统计"},
    "排列组合与二项式定理": {"key_points": ["二项式定理", "二项展开式通项", "系数与各项"], "module": "概率统计"},
    "条件概率": {"key_points": ["条件概率公式", "乘法公式", "全概率公式初步"], "module": "概率统计"},
    "全概率公式": {"key_points": ["全概率公式", "贝叶斯公式", "综合应用"], "module": "概率统计"},
    "排列组合和概率综合": {"key_points": ["排列组合在概率中的应用", "综合题"], "module": "概率统计"},
    "离散型随机变量的概念与分布列": {"key_points": ["分布列", "期望", "方差", "常见分布"], "module": "概率统计"},
    "离散型随机变量的均值与方差": {"key_points": ["期望公式", "方差公式", "线性变换"], "module": "概率统计"},
    "二项分布、超几何分布、正态分布": {"key_points": ["B(n,p)", "超几何分布", "N(μ,σ²)", "标准正态"], "module": "概率统计"},
    "相关性与回归模型": {"key_points": ["散点图", "相关系数", "回归方程", "最小二乘法"], "module": "概率统计"},
    "列联表与独立性检验": {"key_points": ["列联表", "χ²统计量", "独立性检验步骤"], "module": "概率统计"},
    "AI_Agent": {"key_points": ["Prompt Engineering", "LangChain & LangGraph", "How to build a AI Agent yourself"], "module": "AI"},
}

# ── LaTeX格式模板 ─────────────────────────────────────────────────────────────
LATEX_FORMAT_EXAMPLE = r"""
\documentclass[a4paper,11pt]{article}
\usepackage{geometry}
\geometry{left=2cm,right=2cm,top=2.5cm,bottom=2.5cm}
\usepackage{amsmath, amssymb}
\usepackage{fontspec}
\usepackage{xeCJK}
\setmainfont{Noto Serif SC}
\setsansfont{Noto Sans SC}
\setCJKmainfont{Noto Serif SC}
\setCJKsansfont{Noto Sans SC}
\usepackage[table]{xcolor}
\usepackage[most]{tcolorbox}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{enumitem}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{needspace}
\setstretch{1.6}
\definecolor{lightgray}{gray}{0.95}
\definecolor{midgray}{gray}{0.6}
\definecolor{darkgray}{gray}{0.3}
\definecolor{blankgray}{gray}{0.98}
\tcbset{
    answerbox/.style={colback=lightgray, colframe=midgray, coltitle=black,
                      fonttitle=\bfseries, boxsep=2mm, breakable},
    blankbox/.style={colback=blankgray, colframe=midgray, coltitle=black,
                     fonttitle=\bfseries, boxsep=2mm, breakable,
                     borderline={0.5pt}{0pt}{midgray,dashed}},
    tipbox/.style={colback=white, colframe=black, boxrule=0.8pt,
                   fonttitle=\bfseries, boxsep=2mm, breakable},
    theorybox/.style={colback=white, colframe=darkgray, boxrule=0.5pt,
                      fonttitle=\bfseries, arc=0mm, boxsep=2mm, breakable}
}
\titleformat{\section}[block]{\large\bfseries}{}{0em}{}[\vspace{-0.3em}\hrule\vspace{0.3em}]
\titleformat{\subsection}[block]{\normalsize\bfseries}{}{0em}{}
% ── 页面溢出防护 ────────────────────────────────────────────────────────────
\allowdisplaybreaks          % 允许align*等公式环境跨页
\emergencystretch 2em        % 自动拉伸字间距防止溢出
\setlength{\textwidth}{16cm}
\setlength{\textheight}{24cm}
\begin{document}
\everymath{\displaystyle}

\begin{center}
    {\LARGE\textbf{高中数学·直线方程}}
    \vspace{0.3cm}

    {\normalsize 解析几何模块 \quad|\quad 课时：60 min}
\end{center}
\vspace{0.2cm}
\hrule
\vspace{0.5cm}

\section*{一、牛刀小试（5 min，先独立完成再对答案）}
\begin{enumerate}[label=(\arabic*), itemsep=0.3cm]
    \item 直线倾斜角$\alpha$的取值范围是\underline{\hspace{2cm}}；斜率$k$的取值范围是\underline{\hspace{2cm}}
    \item 已知直线$l$过点$A(1, 2)$，斜率$k=3$，写出$l$的点斜式方程：\underline{\hspace{3cm}}
\end{enumerate}
\begin{tcolorbox}[answerbox, title={【答案速查】}]
(1) $0^\circ\le\alpha<180^\circ$；$k\in\mathbb{R}$.\\
(2) $y-2=3(x-1)$，整理得$3x-y-1=0$.
\end{tcolorbox}

\newpage
\section*{二、本章知识框架}
\renewcommand{\arraystretch}{1.8}
\begin{table}[h]
\centering
\rowcolors{2}{lightgray}{white}
\begin{tabular}{p{2cm}p{5cm}p{3cm}p{4cm}}
\toprule
\textbf{形式} & \textbf{方程} & \textbf{已知条件} & \textbf{局限性} \\
\midrule
点斜式 & $y-y_0=k(x-x_0)$ & 一点+斜率$k$ & 斜率不存在时不适用 \\
一般式 & $Ax+By+C=0$ & 通用 & 无局限 \\
\bottomrule
\end{tabular}
\end{table}

\newpage
\section*{三、知识点精讲 + 分类例题（由易到难）}
\subsection*{3.1 直线的倾斜角与斜率}
\begin{tcolorbox}[theorybox, title={核心要点}]
\begin{itemize}[leftmargin=*]
    \item 倾斜角$\alpha$范围：$0^\circ\le\alpha<180^\circ$；$\alpha=90^\circ$时斜率不存在.
    \item 斜率$k=\tan\alpha$（$\alpha\neq 90^\circ$），$k\in\mathbb{R}$.
\end{itemize}
\end{tcolorbox}

\needspace{20\baselineskip}
\noindent\textbf{例题 1——倾斜角范围}\\
\textbf{【题目】} 若直线$l$的斜率$k\in[-\sqrt{3}, 1]$，求倾斜角$\alpha$的取值范围.
\begin{tcolorbox}[answerbox, title={【解题过程】}]
分两段讨论...综合：$\alpha\in[0^\circ, 45^\circ]\cup(90^\circ, 120^\circ]$.
\end{tcolorbox}
\begin{tcolorbox}[tipbox, title={【易错点】}]
$\Rightarrow$ 斜率范围$\neq$直接取$\arctan$！
\end{tcolorbox}

\newpage
\section*{四、本章综合例题}

\needspace{25\baselineskip}
\noindent\textbf{综合例题 1——题型名}\\
\textbf{【题目】} 题目内容...
\begin{tcolorbox}[answerbox, title={【解题过程】}]
解题步骤...
\end{tcolorbox}

\newpage
\section*{五、易错点 \& 考点速查}
\renewcommand{\arraystretch}{1.6}
\begin{table}[h]
\centering
\rowcolors{2}{lightgray}{white}
\begin{tabular}{cp{5.5cm}p{6.5cm}}
\toprule
\textbf{编号} & \textbf{易错点} & \textbf{正确做法} \\
\midrule
① & 平行判定忘记排除重合 & 验证常数项不同 \\
\bottomrule
\end{tabular}
\end{table}

\newpage
\section*{六、课堂练习（约 10 min，调节时间用）}
\begin{enumerate}[label=(\arabic*), itemsep=0.4cm]
    \item 练习题...
\end{enumerate}
\begin{tcolorbox}[answerbox, title={【练习参考答案】}]
(1) 答案...
\end{tcolorbox}

\vspace{1cm}
\begin{center}
    \color{midgray}\small 《直线方程》讲义 \(\cdot\) 解析几何模块 \(\cdot\) Author: 杨皓瑜
\end{center}
\end{document}
"""

# ── PDF读取 ───────────────────────────────────────────────────────────────────

def read_pdf_text(pdf_path: Path) -> str:
    try:
        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            text = page.get_text("text").strip()
            if text:
                pages.append(text)
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        log.warning(f"  读取PDF失败: {pdf_path.name} — {e}")
        return ""

def collect_reference_texts(topic: str, pdf_dir: Path, max_chars: int = 800_000) -> str:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        log.warning(f"在 {pdf_dir} 中未找到PDF文件")
        return ""

    keywords = re.split(r"[与和的及综合、\s]", topic)
    keywords = [k for k in keywords if len(k) >= 2]

    priority, rest = [], []
    for p in pdfs:
        name = p.stem
        if any(kw in name for kw in keywords):
            priority.append(p)
        else:
            rest.append(p)

    ordered = priority + rest
    collected, total_chars = [], 0

    for pdf in ordered:
        text = read_pdf_text(pdf)
        if not text:
            continue
        if total_chars + len(text) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 500:
                collected.append(f"=== {pdf.name} (截断) ===\n{text[:remaining]}")
            break
        collected.append(f"=== {pdf.name} ===\n{text}")
        total_chars += len(text)
        log.info(f"  已加载: {pdf.name} ({len(text)}字符)")

    log.info(f"  共加载 {len(collected)} 个PDF，总计 {total_chars} 字符")
    return "\n\n".join(collected)

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是一位顶尖的高中数学教师，专门编写高质量的课时讲义。
你的讲义以逻辑清晰、内容充实、例题精选、易错点准确著称。
你将根据参考资料和格式要求，输出完整的LaTeX讲义代码。"""

def build_prompt(topic: str, module: str, key_points: list[str], reference: str) -> str:
    return f"""请为「{topic}」编写一份内容丰富的60分钟高中数学课时讲义（LaTeX格式）。注意：讲义必须内容充实、题量充足。

【讲义要求】
- 模块：{module}
- 核心知识点：{'、'.join(key_points)}
- 课时：60分钟
- 对象：高中生

【讲义结构】（必须严格按此顺序，内容要充实）
一、牛刀小试（5 min）：5-6道填空/选择，覆盖基础概念，附答案速查
二、本章知识框架：用表格呈现核心公式、条件、注意事项（至少2个表格，内容完整）
三、知识点精讲+分类例题（由易到难）：4-5个子节，每节含核心要点box + 至少2道例题（例题+解题过程+易错点）
四、本章综合例题：3-4道压轴综合题，含完整解题过程，难度逐步上升
五、易错点&考点速查：表格形式，至少8条易错点
六、课堂练习（10 min）：8-10道练习题，覆盖各知识点，附参考答案

【题目要求】
- 从下方【参考资料】中选取合适的题目，原题如果你认为出的好那就照搬原题，如果不好那么你可以适当修改但务必保证正确性
- 题目质量优先，宁缺毋滥
- 例题编号必须从"例题 1"开始重新编号，不要沿用参考资料里的原始编号
- 难度梯度：牛刀小试→精讲例题→综合例题→练习题，由易到难
- 解题过程只写最终正确的解法，不要写探索过程、不要出现"重新考虑""改用构造""不妨设"等思考痕迹
- 解题过程必须详细，每步都要有
- 解题过程中全程使用句点（.）而非中文句号（。）结尾

【内容量要求】
- 整份讲义应足够充实，例题和练习题要尽可能多，保证课堂容量
- 每道例题的解题过程要详细完整，不能过于简略
- 不要害怕页面变多，一份60min的讲义完全可以是10-15页甚至更多

【LaTeX格式要求】
- 严格参照【格式模板】，导言区必须与模板完全一致（包含needspace、multirow宏包和blankbox样式）
- 数学公式：行内$...$，行间用align*环境并手动用\\\\在合适位置换行，禁止出现整行公式超出页面右边界
- 中文文本和行内公式之间不要有额外空格，xeCJK会自动处理间距，无需手动用\\quad或空格隔开
- 大段数学推导使用align*环境分行展示，每行一个等号对齐，禁止把长公式全部写在一行align*内
- 使用 tcolorbox 的三种样式：answerbox（答案/解题过程）、theorybox（要点）、tipbox（易错），全部加breakable选项
- 表格列宽一律用p{{Xcm}}指定，禁止用l列放无限长内容
- tcolorbox内中文句子中夹杂的变量名（如"P在直线AF上"）不要单独用$...$包裹，直接写成普通文字或改用\\textit{{}}，避免产生异常字间距
- 每道例题（题目行+解答box）前必须加\\needspace{{20\\baselineskip}}；综合例题前加\\needspace{{25\\baselineskip}}
- 若例题解答特别长（超过半页），在例题标题行前改用\\newpage强制换页
- 各章节之间的\\newpage只用一次（放在章节标题之前）。禁止在章节标题之后紧接着又放一个\\newpage，否则会造成"只有标题的空白页"
- 禁止使用\\multirow命令，因为需要额外宏包容易引发编译错误。表格有多行合并需求时改用空白行替代
- 输出完整可编译的LaTeX代码，从\\documentclass开始到\\end{{document}}结束
- 不要任何解释，只输出LaTeX代码

【格式模板】
{LATEX_FORMAT_EXAMPLE}

【参考资料】
{reference if reference else "（未找到相关PDF，请基于知识点自行编写高质量题目）"}
"""

# ── LLM调用 ───────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    log.info("  调用 DeepSeek-V4-Pro 生成讲义...")
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()

def extract_latex(raw: str) -> str:
    if "```" in raw:
        parts = raw.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                code = part
                if code.startswith("latex") or code.startswith("tex"):
                    code = code[code.index("\n")+1:]
                raw = code
                break
    if "\\documentclass" in raw:
        raw = raw[raw.index("\\documentclass"):]
    return raw.strip()


def sanitize_latex(tex: str) -> str:
    r"""自动修复 LLM 输出的 LaTeX 中常见低级错误。

    修复项：
      - 全角右括号 `)` 代替半角 `]` 关闭 tcolorbox option（最常见）
      - 全角左括号 `（` 代替半角 `[` 开启 tcolorbox option
      - 空白的 \usepackage 行

      - \begin{enumerate} 后跟空白参数等
    """
    # 1. 修复 tcolorbox: \begin{tcolorbox}[...]） → \begin{tcolorbox}[...]
    tex = re.sub(
        r'(\\begin\{tcolorbox\}\[[^\]]*\])\）',
        r'\1]',
        tex
    )

    # 2. 修复全角左括号：\begin{tcolorbox}（...】) → \begin{tcolorbox}[...】]
    tex = re.sub(
        r'(\\begin\{tcolorbox\})（([^）]*?)】\)',
        r'\1[\2】]',
        tex
    )


    # 3. 修复全角左括号：】） → 】]
    tex = tex.replace('】）', '】]')

    # 4. \end{tcolorbox}）→ \end{tcolorbox} （行尾有多余全角括号）
    tex = tex.replace(r'\end{tcolorbox}）', r'\end{tcolorbox}')

    # 5. 修复\end{...}后有全角括号杂质的
    tex = re.sub(r'(\\end\{[^}]+\})[）\)]', r'\1', tex)

    # 6. 修复空白的无用行：只有 \usepackage{} 没有宏包名
    tex = re.sub(r'^\s*\\usepackage\{\}\s*$', '', tex, flags=re.MULTILINE)

    return tex


# ── 学生版后处理 ──────────────────────────────────────────────────────────────

def strip_answers_for_student(tex: str) -> str:
    """
    将教师版LaTeX（含答案）转换为学生版（无答案，留出答题区域）。

    规则：
    - answerbox 中的【答案速查】→ 直接删除整个 box
    - answerbox 中的【解题过程】→ 替换为 blankbox 空白答题区（虚线框 + vspace）
    - answerbox 中的【练习参考答案】→ 直接删除整个 box
    - 其他 answerbox → 替换为空白 box
    """

    def _replace_answerbox(match):
        full = match.group(0)
        # 提取标题
        title_m = re.search(r'title=\{([^}]*)\}', full[:300])
        title = title_m.group(1) if title_m else ""

        # 根据标题决定处理方式
        if "答案速查" in title or "参考答案" in title:
            # 直接删除
            return ""
        elif "解题过程" in title or "解题" in title:
            # 替换为空白答题区（虚线框）
            return (
                r"\begin{tcolorbox}[blankbox, title={" + title + r"}]"
                "\n\\vspace{8cm}\n"
                r"\end{tcolorbox}"
            )
        else:
            # 其他 answerbox → 通用空白框
            return (
                r"\begin{tcolorbox}[blankbox, title={" + title + r"}]"
                "\n\\vspace{6cm}\n"
                r"\end{tcolorbox}"
            )

    # 匹配完整的 answerbox 环境（从 \begin 到 \end，允许跨行）
    pattern = (
        r'\\begin\{tcolorbox\}\[answerbox[^\]]*\]'  # opening
        r'.*?'                                        # content (lazy)
        r'\\end\{tcolorbox\}'                         # closing
    )
    tex = re.sub(pattern, _replace_answerbox, tex, flags=re.DOTALL)

    # 标题标注"学生版"
    tex = tex.replace(
        r"高中数学·",
        r"高中数学·学生版·"
    )

    return tex

# ── LaTeX编译 ─────────────────────────────────────────────────────────────────

def parse_error(log_text: str) -> str:
    lines = log_text.split("\n")
    error_lines = []
    for i, line in enumerate(lines):
        if line.startswith("!") or "Error" in line or "Undefined" in line:
            error_lines.extend(lines[max(0, i-1):i+4])
    error = "\n".join(error_lines)
    return error[:600] if error else log_text[-600:]

def compile_once(tex_path: Path, out_dir: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [LATEX_CMD] + LATEX_OPTS + [f"-output-directory={out_dir}", str(tex_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=tex_path.parent
        )
        log_output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, log_output
    except FileNotFoundError:
        return False, f"未找到命令: {LATEX_CMD}"
    except Exception as e:
        return False, str(e)

def compile_latex(tex_path: Path) -> Path | None:
    """编译LaTeX为PDF。如果xelatex不可用，返回None并打印警告，不会抛出异常。"""
    PDF_OUT_DIR.mkdir(parents=True, exist_ok=True)
    tex_path = tex_path.resolve()

    # 检查xelatex是否可用
    if not shutil.which(LATEX_CMD):
        log.warning(f"  ⚠️ 未找到 '{LATEX_CMD}'，跳过PDF编译。TeX源文件已保存。")
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        log.info(f"  编译尝试 {attempt}/{MAX_RETRIES}")
        success, log_text = True, ""
        for _ in range(2):
            ok, lt = compile_once(tex_path, PDF_OUT_DIR)
            log_text = lt
            if not ok:
                success = False
                break

        pdf_path = PDF_OUT_DIR / tex_path.with_suffix(".pdf").name
        if success and pdf_path.exists():
            log.info(f"  ✅ 编译成功: {pdf_path}")
            # 清理本次编译过程中产生的备份文件
            for bak in tex_path.parent.glob(tex_path.stem + ".bak*.tex"):
                bak.unlink(missing_ok=True)
            return pdf_path

        error = parse_error(log_text)
        log.warning(f"  ❌ 编译失败:\n{error}")

        # 不再调用DeepSeek自动修复——费Token且很少成功
        # 直接report失败，用户可手动修改LaTeX
        log.error(f"  💀 编译失败，请手动检查: {tex_path}")
        return None

    return None

def clean_aux(stem: str):
    for ext in [".aux", ".log", ".out", ".toc"]:
        f = PDF_OUT_DIR / (stem + ext)
        if f.exists():
            f.unlink()

# ── 主流程 ────────────────────────────────────────────────────────────────────

def generate(topic: str, mode: str = "teacher") -> list[Path]:
    """
    生成讲义。
    
    mode: "teacher" | "student" | "both"
    返回生成的文件路径列表。
    """
    if topic not in SYLLABUS:
        log.error(f"topic '{topic}' 不在课程大纲中，可用topic：")
        for t in SYLLABUS:
            print(f"  {t}")
        return []

    info       = SYLLABUS[topic]
    module     = info["module"]
    key_points = info["key_points"]

    log.info(f"{'='*60}")
    log.info(f"生成讲义: {topic} [{module}] (模式: {mode})")
    log.info(f"{'='*60}")

    log.info("Step 1/3: 收集PDF参考资料")
    reference = collect_reference_texts(topic, PDF_DIR)

    log.info("Step 2/3: 生成LaTeX讲义（教师版）")
    prompt = build_prompt(topic, module, key_points, reference)
    raw    = call_llm(prompt)
    latex  = extract_latex(raw)
    latex  = sanitize_latex(latex)


    TEX_DIR.mkdir(parents=True, exist_ok=True)
    safe = topic.replace("/", "_").replace("\\", "_")

    results = []

    # ── 教师版 ──
    if mode in ("teacher", "both"):
        tex_path = TEX_DIR / f"{safe}.tex"
        tex_path.write_text(latex, encoding="utf-8")
        log.info(f"  LaTeX已写出: {tex_path} ({len(latex)}字符)")
        results.append(tex_path)

        log.info("Step 3/3: 编译教师版PDF")
        pdf_path = compile_latex(tex_path)
        if pdf_path:
            clean_aux(safe)
            results.append(pdf_path)

    # ── 学生版 ──
    if mode in ("student", "both"):
        student_tex = strip_answers_for_student(latex)
        student_tex_path = TEX_DIR / f"{safe}_学生版.tex"
        student_tex_path.write_text(student_tex, encoding="utf-8")
        log.info(f"  学生版LaTeX已写出: {student_tex_path} ({len(student_tex)}字符)")
        results.append(student_tex_path)

        log.info("  编译学生版PDF")
        pdf_path = compile_latex(student_tex_path)
        if pdf_path:
            clean_aux(f"{safe}_学生版")
            results.append(pdf_path)

    return results


def main():
    parser = argparse.ArgumentParser(description="生成高中数学课时讲义（教师版/学生版）")
    parser.add_argument("topic", nargs="?", help="讲义主题（如 抛物线方程）")
    parser.add_argument("--mode", choices=["teacher", "student", "both"], default="teacher",
                        help="生成模式：teacher（教师版）、student（学生版）、both（两者）")
    parser.add_argument("--all", action="store_true", help="生成所有主题的讲义")
    args = parser.parse_args()

    if args.all:
        results = []
        for topic in SYLLABUS:
            pdfs = generate(topic, mode=args.mode)
            status = "✅" if pdfs else "❌"
            files = ", ".join(str(p) for p in pdfs) if pdfs else "编译失败"
            results.append((topic, status, files))
            print()
        print("\n" + "=" * 60)
        print("生成结果汇总：")
        for t, s, p in results:
            print(f"  {s} {t:<25} → {p}")
    elif args.topic:
        pdfs = generate(args.topic, mode=args.mode)
        if pdfs:
            print(f"\n✅ 完成：")
            for p in pdfs:
                print(f"   {p}")
        else:
            print(f"\n❌ 失败，请检查 output/tex/{args.topic}.tex")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
