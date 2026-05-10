"""
generate_handout.py — v4 (高考真题文件夹支持)
"""
import fitz
import logging
import re
import subprocess
import shutil
import sys
import argparse
import time as _time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from tikz_templates import FIGURE_JSON_INSTRUCTION, inject_figures_into_latex
import os

load_dotenv()

BASE_DIR    = Path(__file__).parent
PDF_DIR     = BASE_DIR / "data" / "raw_pdfs"
GAOKAO_DIR  = BASE_DIR / "data" / "gaokao"      # 高考真题专用文件夹
TEX_DIR     = BASE_DIR / "output" / "tex"
PDF_OUT_DIR = BASE_DIR / "output" / "pdf"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL       = "deepseek-v4-pro"
MAX_TOKENS  = 40000
LATEX_CMD   = r"C:\Users\Kevin\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe"
LATEX_OPTS  = ["-interaction=nonstopmode", "-halt-on-error"]
MAX_RETRIES = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

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
    "解析几何": {"key_points": ["椭圆综合", "双曲线综合", "解析几何难题综合"], "module": "解析几何"},
    "圆锥曲线定值定点问题": {"key_points": ["定值问题的转化", "设点法与向量法", "参数消去", "定点坐标求法"], "module": "解析几何"},
    "圆锥曲线范围最值问题": {"key_points": ["参数范围讨论", "基本不等式应用", "判别式法", "导数辅助"], "module": "解析几何"},
    "圆锥曲线非对称韦达定理": {"key_points": ["非对称韦达定理", "弦中点问题", "斜率乘积定值", "综合应用"], "module": "解析几何"},
    "暑期测验": {"key_points": ["解析几何综合", "概率统计综合", "压轴题训练", "限时模拟"], "module": "综合测验"},
    "寒假测验": {"key_points": ["解析几何综合", "概率统计综合", "压轴题训练", "限时模拟"], "module": "综合测验"},
}

TIKZ_TOPICS = {
        "椭圆方程","双曲线方程","抛物线方程","椭圆的几何性质",
        "双曲线的几何性质","抛物线的几何性质","直线与椭圆",
        "直线与抛物线","圆锥曲线综合","直线与圆","直线方程综合",
        "曲线与方程","解析几何","圆锥曲线定值定点问题",
        "圆锥曲线范围最值问题","圆锥曲线非对称韦达定理"
}

# ── LaTeX模板 ─────────────────────────────────────────────────────────────────
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
\usepackage{makecell}
\usepackage{enumitem}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{needspace}
\usepackage{graphicx}
\usepackage{tikz}
\usepackage{pgfplots}
% forest removed - using tikz child syntax instead
\pgfplotsset{compat=1.18}
\usetikzlibrary{patterns, arrows.meta, positioning, calc, decorations.pathreplacing}
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
\allowdisplaybreaks
\emergencystretch 2em
\begin{document}
\everymath{\displaystyle}

\begin{center}
    {\LARGE\textbf{高中数学·直线方程}}
    \vspace{0.3cm}
    {\normalsize 解析几何模块 \quad|\quad 课时：60 min}
\end{center}
\vspace{0.2cm}\hrule\vspace{0.5cm}

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

\begin{center}
\begin{tikzpicture}[
  grow=right,
  every node/.style={draw, rounded corners, align=center, font=\small, text width=2.6cm},
  level 1/.style={sibling distance=60mm, level distance=52mm,
                  every node/.style={draw,rounded corners,align=center,font=\small,fill=midgray!30,text width=2.6cm,minimum height=8mm}},
  level 2/.style={sibling distance=22mm, level distance=46mm,
                  every node/.style={draw,rounded corners,align=center,font=\small,fill=lightgray,text width=2.4cm,minimum height=7mm}},
  edge from parent/.style={draw, ->, thick}
]
\node[fill=darkgray!80, text=white, font=\bfseries\small, text width=2.4cm] {直线方程}
  child { node {倾斜角与斜率}
    child { node {$\alpha\in[0^\circ,180^\circ)$} }
    child { node {$k=\tan\alpha$} }
  }
  child { node {方程五种形式}
    child { node {点斜式} }
    child { node {一般式} }
  }
  child { node {位置关系}
    child { node {平行$k_1=k_2$} }
    child { node {垂直$k_1k_2=-1$} }
  };
\end{tikzpicture}
\end{center}

\renewcommand{\arraystretch}{1.8}
\begin{table}[h]
\centering
\rowcolors{2}{lightgray}{white}
\begin{tabular}{p{2.5cm}p{5cm}p{3cm}p{3.5cm}}
\toprule
\textbf{形式} & \textbf{方程} & \textbf{条件} & \textbf{局限} \\
\midrule
点斜式 & $y-y_0=k(x-x_0)$ & 一点+斜率 & 斜率不存在时不适用 \\
一般式 & $Ax+By+C=0$ & 通用 & 无局限 \\
\bottomrule
\end{tabular}
\end{table}

\newpage
\section*{三、知识点精讲 + 分类例题}

\subsection*{3.1 直线的倾斜角与斜率}
\begin{tcolorbox}[theorybox, title={核心要点}]
\begin{itemize}[leftmargin=*]
    \item 倾斜角$\alpha$范围：$0^\circ\le\alpha<180^\circ$；$\alpha=90^\circ$时斜率不存在.
    \item 斜率$k=\tan\alpha$（$\alpha\neq 90^\circ$），$k\in\mathbb{R}$.
\end{itemize}
\end{tcolorbox}

\needspace{12\baselineskip}
\noindent\textbf{例题 1——倾斜角范围}\\
\textbf{【题目】}（2023年全国乙卷）若直线$l$的斜率$k\in[-\sqrt{3}, 1]$，求倾斜角$\alpha$的取值范围.
\begin{tcolorbox}[answerbox, title={【解题过程】}]
分两段讨论. $k\in[0,1]$：$\alpha\in[0^\circ,45^\circ]$. $k\in[-\sqrt{3},0)$：$\alpha\in(90^\circ,120^\circ]$. 综合：$\alpha\in[0^\circ,45^\circ]\cup(90^\circ,120^\circ]$.
\end{tcolorbox}
\begin{tcolorbox}[tipbox, title={【易错点】}]
$\Rightarrow$ 斜率范围$\neq$直接取$\arctan$！需分段讨论再取并集.
\end{tcolorbox}

\needspace{8\baselineskip}
\noindent\textbf{【选讲】例题 2——选讲加练题}\\
\textbf{【题目】} 选讲题目内容...
\begin{tcolorbox}[answerbox, title={【解题过程】}]
解题步骤...
\end{tcolorbox}

\newpage
\section*{四、本章综合例题}

% ===== 高考大题标准答案格式示范（所有综合例题必须严格参照此格式）=====
\needspace{15\baselineskip}
\noindent\textbf{综合例题 X——焦点三角形（此为格式示范，生成时替换为真实题目）}\\
\textbf{【题目】}已知双曲线$C:\frac{x^2}{4}-\frac{y^2}{12}=1$的左、右焦点分别为$F_1$、$F_2$，点$P$在双曲线右支上，$PF_1\perp PF_2$，求$\triangle PF_1F_2$的面积.
\begin{tcolorbox}[answerbox, title={【解题过程】}]
由双曲线方程得$a^2=4$，$b^2=12$，故$a=2$，$c=\sqrt{a^2+b^2}=\sqrt{16}=4$，$|F_1F_2|=2c=8$.

由于点$P$在双曲线右支上，由双曲线定义得：
\begin{align*}
|PF_1|-|PF_2|=2a=4.
\end{align*}

设$|PF_2|=t$（$t>c-a=2$，即$t>2$），则$|PF_1|=t+4$.

由$PF_1\perp PF_2$，在直角$\triangle PF_1F_2$中，由勾股定理：
\begin{align*}
|PF_1|^2+|PF_2|^2&=|F_1F_2|^2\\
(t+4)^2+t^2&=64\\
2t^2+8t+16&=64\\
t^2+4t-24&=0\\
(t-4)(t+??)&=0\quad\text{（判别式}\ \Delta=16+96=112\text{）}\\
t&=\frac{-4+\sqrt{112}}{2}=\frac{-4+4\sqrt{7}}{2}=2\sqrt{7}-2.
\end{align*}

验证：$t=2\sqrt{7}-2\approx3.29>2$，满足$t>2$，合法.

故$|PF_2|=2\sqrt{7}-2$，$|PF_1|=2\sqrt{7}+2$.

$\triangle PF_1F_2$的面积为：
\begin{align*}
S&=\frac{1}{2}|PF_1|\cdot|PF_2|\\
&=\frac{1}{2}(2\sqrt{7}+2)(2\sqrt{7}-2)\\
&=\frac{1}{2}(28-4)\\
&=12.
\end{align*}

故$\triangle PF_1F_2$的面积为$\boldsymbol{12}$.
\end{tcolorbox}
% ===== 格式示范结束。要点：①设辅助变量并注明范围；②每步align*展开；
%       ③验证合法性；④结论加粗单独成句；⑤禁止"过程略"或跳步 =====

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

def _collect_from_dir(topic: str, pdf_dir: Path, max_chars: int) -> str:
    """从指定文件夹收集PDF文本，按topic关键词优先排序。"""
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
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
    collected, total_chars = [], 0
    for pdf in priority + rest:
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
    return "\n\n".join(collected)

def collect_reference_texts(topic: str, pdf_dir: Path, max_chars: int = 600_000) -> str:
    """
    收集参考资料。优先加载 data/gaokao/ 中的高考真题，
    再加载 data/raw_pdfs/ 中的普通参考资料。
    两部分在prompt中用标题隔开，让LLM知道哪些是真题。
    """
    half = max_chars // 2

    # 1. 高考真题文件夹
    gaokao_text = ""
    if GAOKAO_DIR.exists() and any(GAOKAO_DIR.glob("*.pdf")):
        log.info("  加载高考真题...")
        gaokao_text = _collect_from_dir(topic, GAOKAO_DIR, half)

    # 2. 普通参考资料
    log.info("  加载普通参考资料...")
    normal_text = _collect_from_dir(topic, pdf_dir, half if gaokao_text else max_chars)

    # 拼接，真题优先且有明显标注
    parts = []
    if gaokao_text:
        parts.append("=== 【高考真题资料】优先从此部分选取真题，注意核对年份 ===\n" + gaokao_text)
    if normal_text:
        parts.append("=== 【普通参考资料】===\n" + normal_text)

    result = "\n\n".join(parts)
    log.info(f"  参考资料总计 {len(result)} 字符（真题{'有' if gaokao_text else '无'}）")
    return result

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是一位顶尖的高中数学教师，专门编写高质量的课时讲义。
你的讲义以逻辑清晰、内容充实、例题精选、易错点准确著称。
你将根据参考资料和格式要求，输出完整的LaTeX讲义代码。"""

def build_prompt(topic: str, module: str, key_points: list[str], reference: str) -> str:

    need_tikz = topic in TIKZ_TOPICS

    figure_rule = """
   - 【配图规则——必须执行】每道例题解题过程结束后，立即判断：
     ① 若题目中曲线的a、b均为已知具体数值（解题完成后能确定），必须紧接着输出一个```json图形描述块
     ② 若题目最终求的是离心率、渐近线斜率等抽象量（a、b解完仍是字母），不输出JSON块
     ③ JSON块必须紧跟在\\end{tcolorbox}之后，不得遗漏
""" if need_tikz else ""

    figure_format = ("\n" + FIGURE_JSON_INSTRUCTION) if need_tikz else ""

    return f"""请为「{topic}」编写一份60分钟高中数学课时讲义（LaTeX格式）。{figure_format}

【讲义要求】
- 模块：{module}
- 核心知识点：{'、'.join(key_points)}
- 课时：60分钟；对象：高中生
- 整份讲义内容充实，例题和解题过程要详细，预计12-16页均可

【讲义结构】（必须严格按此顺序）
一、牛刀小试（5 min）：4-5道填空/选择，附答案速查
二、本章知识框架：
   ① 用tikz的child语法画树状思维导图（严格参照格式模板中的tikz树状图示例，节点样式与示例完全一致，禁止使用forest包）
   ② 再附1-2个知识速查表格
三、知识点精讲+分类例题：4-5个子节，每节含：
   - 核心要点box（theorybox）
   - 2-3道普通例题（含解题过程+易错点），例题要详细完整{figure_rule}   - 1道【选讲】例题（标题前加"【选讲】"，根据课堂进度选用，难度略高）
四、本章综合例题：3-4道压轴题，含完整详细解题过程，每道题解答不能简略{figure_rule}五、易错点&考点速查：表格，至少8条

【高考真题要求——重要】
- 参考资料中标注"【高考真题资料】"的部分是真实高考题，优先从这里选取
- 每个知识点子节至少有1道高考真题，格式："（XXXX年XX卷）"，如"（2023年新高考全国卷I）"
- 综合例题里至少有1道高考真题
- 若找不到合适真题，直接出题即可，不需要任何标注，禁止编造年份
- 真题文字可能有OCR错误，使用时请根据数学逻辑自行修正

【题目要求】
- 从参考资料中选取合适题目，质量优先
- 例题编号从"例题 1"开始，不沿用参考资料编号
- 难度梯度：牛刀小试→精讲例题→选讲例题→综合例题，由易到难
- 解题过程只写最终正确解法，不写探索过程
- 每一步推导必须数学严格，前后结论不能矛盾，不能出现"重新考虑""等等""检验发现"等字样
- 每道例题的解题过程必须完整，禁止输出"略"或"留作练习"；如果发现题目描述不完整，请更换或修正题目后再撰写解答
- 解题过程用句点（.）而非中文句号（。）结尾
- 解题过程书写标准参照高考评分标准：每一个得分点单独成句，关键步骤不跳跃，中间推导完整写出；禁止"过程略"、"类似可得"、"计算可得"等替代语，所有计算结果必须显式推导到位
- 综合例题解题过程必须严格参照【格式模板】中"综合例题X——焦点三角形"的格式示范：①设辅助变量时注明取值范围；②每步计算用align*环境逐行展开，不得跳步；③对解出的值验证合法性；④最终结论加粗单独成句以句点结尾
- 如果某道综合题无法写出每步都正确的完整推导，必须立即换题，不得保留任何残缺解答，不需要说明换题原因
- 涉及等腰三角形、对称性、分情况讨论的题目，必须在内部确定唯一正确
  的情况后，直接以该情况开始解题，其余情况若需排除则用一句话说明矛盾
  原因即可，不展开错误路径的计算
- 若某道题在生成过程中发现自己的推导出现矛盾或需要"重新考虑"，
  立即停止并换题，不得修补后继续输出
- 任何例题的解题过程中，禁止出现对题目数据的质疑、
  对自身推导的否定、或"题目有误"等表述。
  若代入验证失败，直接输出换题后的新题目和完整解答，
  不解释换题原因，不保留任何失败推导片段。
- 优先使用参考资料中的真题或改编题；
  若实在无题可用，只允许对已有真题修改数据后使用，
  禁止从零自编全新题目。
- 如果某道题完整写出需要超过20行推导，换一道计算量适中、能完整给出满分答案的题

【LaTeX格式要求】
- 严格参照格式模板，导言区与模板完全一致（含needspace、makecell，禁止使用forest包）
- 知识框架必须用tikz child语法画树状图，节点样式与模板示例完全一致，grow=right方向
- tikz child树状图最多两层（根→一级→二级），严禁三层child嵌套，否则节点重叠
- 每个一级节点最多2个二级子节点，超过2个会导致重叠
- 数学公式：行内$...$，行间用align*环境分行，禁止长公式溢出页面
- tcolorbox全部加breakable选项
- 表格列宽用p{{Xcm}}指定，禁止l列
- 例题前加\\needspace{{12\\baselineskip}}，综合例题前加\\needspace{{15\\baselineskip}}
- \\needspace禁止紧跟\\section*或\\subsection*之后
- 禁止\\multirow；禁止在章节标题后立即\\newpage
- 输出完整LaTeX代码，从\\documentclass到\\end{{document}}，不要任何解释

【格式模板】
{LATEX_FORMAT_EXAMPLE}

【参考资料】
{reference if reference else "（未找到相关PDF，请基于知识点自行编写高质量题目）"}
"""

# ── LLM ──────────────────────────────────────────────────────────────────────
def call_llm(prompt: str) -> str:
    log.info("  调用 DeepSeek-V4-Pro 生成讲义...")
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
    )
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        log.warning("  ⚠️ 输出被token限制截断！考虑增大MAX_TOKENS或缩短参考资料")
    return choice.message.content.strip()

def extract_latex(raw: str) -> str:
    # 直接提取\documentclass到\end{document}之间的内容
    # 保留中间的```json```块，inject_figures_into_latex会处理它们
    start = raw.find("\\documentclass")
    end = raw.rfind("\\end{document}")
    if start != -1 and end != -1:
        return raw[start:end + len("\\end{document}")].strip()
    elif start != -1:
        return raw[start:].strip()
    # 兜底：去掉外层markdown代码块标记
    raw = re.sub(r'^```[a-z]*\n', '', raw.strip())
    raw = re.sub(r'\n```$', '', raw)
    return raw.strip()

# ── sanitize ─────────────────────────────────────────────────────────────────
def sanitize_latex(tex: str) -> str:
    tex = re.sub(r'(title=\{[^}]*)【([^}]*)】([^}]*\})', 
             r'\1\2\3', tex)
    # -1. 删除forest环境
    tex = re.sub(r'\\begin\{forest\}.*?\\end\{forest\}',
                 r'% [forest removed]', tex, flags=re.DOTALL)
    # 0. 注入缺失宏包
    for _pkg in ['makecell', 'subfigure']:
        if f'\\usepackage{{{_pkg}}}' not in tex and f'\\{_pkg}' in tex:
            tex = tex.replace(r'\begin{document}',
                              f'\\usepackage{{{_pkg}}}\n\\begin{{document}}', 1)
    # -0.5 修复 \degree 为 ^\circ
    tex = tex.replace(r'\degree', r'^\circ')
    # 0.5 tcolorbox title多余右括号
    tex = re.sub(r'(\\begin\{tcolorbox\}\[[^\]]*title=\{[^}]*)\}\}', r'\1}', tex)
    # 1-5. tcolorbox括号修复
    tex = re.sub(r'(\\begin\{tcolorbox\}\[[^\]]*\])\）', r'\1]', tex)
    tex = re.sub(r'(\\begin\{tcolorbox\})（([^）]*?)】\)', r'\1[\2】]', tex)
    tex = tex.replace('】）', '】]')
    tex = tex.replace(r'\end{tcolorbox}）', r'\end{tcolorbox}')
    tex = re.sub(r'(\\end\{[^}]+\})[）\)]', r'\1', tex)
    # 6. 空usepackage
    tex = re.sub(r'^\s*\\usepackage\{\}\s*$', '', tex, flags=re.MULTILINE)
    # 7-8. 删除section后的needspace
    tex = re.sub(
        r'(\\section\*\{[^}]*\}|\\subsection\*\{[^}]*\})\s*\\needspace\{[^}]*\}',
        r'\1', tex)
    tex = re.sub(
        r'(\\section\*\{[^}]*\}|\\subsection\*\{[^}]*\})\s*\n\s*\\needspace\{[^}]*\}',
        r'\1', tex, flags=re.MULTILINE)
    # 9. needspace值限制
    lines = tex.split("\n")
    new_lines = []
    for l in lines:
        m = re.search(r'\\needspace\{(\d+)\\baselineskip\}', l)
        if m:
            val = int(m.group(1))
            if val >= 20:
                lookback = " ".join(new_lines[-10:] if len(new_lines) >= 10 else new_lines)
                new_val = 15 if "综合例题" in lookback else 12
                l = l.replace(f"\\needspace{{{val}\\baselineskip}}",
                               f"\\needspace{{{new_val}\\baselineskip}}")
        new_lines.append(l)
    tex = "\n".join(new_lines)
    # 10. tikz circle修复
    tex = re.sub(r'(circle\s*\()([a-z]+)(\s*\()', r'\1{\2\3', tex, flags=re.IGNORECASE)
    tex = re.sub(r'(circle\s*\{[a-z]+\()([^)]*)\)\s*\)', r'\1\2)}', tex)
    # 11. resizebox包裹tikzpicture（不包裹child树）
    tex = tex.replace(r'\resizebox{\textwidth}', r'\resizebox{0.55\textwidth}')
    tex = re.sub(
        r'(\\begin\{center\}\s*)(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})(\s*\\end\{center\})',
        lambda m: m.group(1) + (
            r'\resizebox{0.55\textwidth}{!}{' + m.group(2) + '}'
            if 'child {' not in m.group(2) and 'child{' not in m.group(2)
            else m.group(2)
        ) + m.group(3),
        tex, flags=re.DOTALL
    )
    # 12. 删除grid网格
    tex = re.sub(r'^\s*\\draw\[.*?grid.*?\].*?;\s*$', '', tex, flags=re.MULTILINE)
    # 12.5 删除非right的grow方向
    tex = re.sub(r'grow\s*=\s*(down|up|left|west|north|south)\s*,?\s*', '', tex)
    tex = re.sub(r',\s*grow\s*=\s*(down|up|left|west|north|south)', '', tex)
    # 13. 黑白化
    def _bw(m):
        s = m.group(0)
        for c in ['blue','red','green!60','green','cyan','magenta',
                  'yellow','orange','violet','purple','teal']:
            s = s.replace(c, 'black')
        return s
    tex = re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
                 _bw, tex, flags=re.DOTALL)
    # 14. \tikzpicture裸命令修复
    tex = tex.replace(r'\begin{tikzpicture}', '<<<BEG>>>')
    tex = tex.replace(r'\end{tikzpicture}',   '<<<END>>>')
    tex = tex.replace(r'\tikzpicture', '点')
    tex = tex.replace('点点', '点')
    tex = tex.replace('<<<BEG>>>', r'\begin{tikzpicture}')
    tex = tex.replace('<<<END>>>', r'\end{tikzpicture}')
    # 14.5 修复截断文件
    _end_doc = '\\end{document}'
    if _end_doc not in tex:
        for _env, _close in [('tcolorbox', '\\end{tcolorbox}'),
                               ('tikzpicture', ';\n\\end{tikzpicture}\n\\end{center}'),
                               ('enumerate', '\\end{enumerate}'),
                               ('itemize', '\\end{itemize}')]:
            _nb = tex.count(f'\\begin{{{_env}}}')
            _ne = tex.count(f'\\end{{{_env}}}')
            for _ in range(_nb - _ne):
                tex = tex.rstrip() + '\n' + _close + '\n'
        tex = tex.rstrip() + '\n\\end{document}\n'
    else:
        _last = tex.rindex(_end_doc)
        tex = tex[:_last + len(_end_doc)] + '\n'
    # 15. 删除含反引号的非法\node
    tex = re.sub(r'\\node[^;\n]*`[^;\n]*;', '', tex)
    # 16. tikz plot缺\x修复
    tex = re.sub(
        r'(plot\[domain[^\]]*\]\s*)\((\{)(?![^}]*\\x)',
        lambda m: m.group(1) + '({\\x},' + m.group(2), tex)
    # 17.5 tikzpicture环境配对检查
    if tex.count(r'\begin{tikzpicture}') != tex.count(r'\end{tikzpicture}'):
        tex = re.sub(
            r'\\begin\{tikzpicture\}(?:(?!\\end\{tikzpicture\}).)*$',
            '% [unclosed tikzpicture removed]',
            tex, flags=re.DOTALL | re.MULTILINE)
    # 17.6 child节点\\换行修复
    # 在tikz child节点里，把换行命令替换为斜杠分隔
    def _fix_node_newline(m):
        s = m.group(0)
        # 替换节点文本中所有换行为斜杠
        s = re.sub(
            r'(node\s*\{[^}]*?)\\\\([^}]*?\})',
            lambda x: x.group(1) + '/' + x.group(2),
            s
        )
        s = re.sub(
        r'(node\s*\{[^}]*?)\\newline\s*([^}]*?\})',
        lambda x: x.group(1) + '/' + x.group(2),
        s
        )
        return s

    tex = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        _fix_node_newline,
        tex,
        flags=re.DOTALL
    )
    # 18. 修复tcolorbox title中的数学命令（\triangle等在\csname中非法）
    _title_replacements = {
        r'\triangle': '△',
        r'\angle':    '∠',
        r'\perp':     '⊥',
        r'\parallel': '∥',
        r'\cdot':     '·',
        r'\times':    '×',
        r'\leq':      '≤',
        r'\geq':      '≥',
        r'\neq':      '≠',
        r'\infty':    '∞',
        r'\pi':       'π',
        r'\alpha':    'α',
        r'\beta':     'β',
        r'\gamma':    'γ',
        r'\theta':    'θ',
        r'\lambda':   'λ',
        r'\mu':       'μ',
        r'\sigma':    'σ',
        r'\omega':    'ω',
        r'\sqrt':     '√',
        r'\pm':       '±',
    }
    def _fix_tcolorbox_title(m):
        full = m.group(0)
        title_m = re.search(r'(title=\{)([^}]*?)(\})', full)
        if not title_m:
            return full
        content = title_m.group(2)
        for cmd, uni in _title_replacements.items():
            content = content.replace(cmd, uni)
        # 删除剩余未处理的\命令（兜底，避免遗漏）
        content = re.sub(r'\\[a-zA-Z]+\*?', '', content)
        # 删除残留的$符号
        content = content.replace('$', '')
        return full[:title_m.start(2)] + content + full[title_m.end(2):]

    tex = re.sub(
        r'\\begin\{tcolorbox\}\[[^\[\]]*title=\{[^}]*\}[^\[\]]*\]',
        _fix_tcolorbox_title, tex
    )
    return tex

# ── 学生版 ────────────────────────────────────────────────────────────────────
def strip_answers_for_student(tex: str) -> str:
    def _replace(match):
        full = match.group(0)
        title_m = re.search(r'title=\{([^}]*)\}', full[:300])
        title = title_m.group(1) if title_m else ""
        if "答案速查" in title or "参考答案" in title:
            return ""
        elif "解题过程" in title or "解题" in title:
            return (r"\begin{tcolorbox}[blankbox, title={" + title + r"}]"
                    "\n\\vspace{8cm}\n" r"\end{tcolorbox}")
        else:
            return (r"\begin{tcolorbox}[blankbox, title={" + title + r"}]"
                    "\n\\vspace{6cm}\n" r"\end{tcolorbox}")
    pattern = r'\\begin\{tcolorbox\}\[answerbox[^\]]*\].*?\\end\{tcolorbox\}'
    tex = re.sub(pattern, _replace, tex, flags=re.DOTALL)
    tex = tex.replace(r"高中数学·", r"高中数学·学生版·")
    return tex

# ── 编译 ──────────────────────────────────────────────────────────────────────
FIX_PROMPT = """\
以下LaTeX代码使用xelatex编译时报错，请修复后输出完整代码。

【错误信息】：
{error}

【原代码】：
{tex}

只输出完整LaTeX代码，不要任何解释，不要markdown代码块。
修复方向：未转义特殊字符、不匹配括号/环境、缺失宏包（makecell）、tcolorbox参数错误。注意：禁止使用forest包，树状图用tikz child语法。
"""

def parse_error(log_text: str) -> str:
    lines = log_text.split("\n")
    error_lines = []
    for i, line in enumerate(lines):
        if line.startswith("!") or "Error" in line or "Undefined" in line:
            error_lines.extend(lines[max(0, i-1):i+4])
    error = "\n".join(error_lines)
    return error[:600] if error else log_text[-600:]

def compile_once(tex_path: Path, out_dir: Path) -> tuple[bool, str]:
    pdf_path = out_dir / tex_path.with_suffix(".pdf").name
    if pdf_path.exists():
        for retry in range(4):
            try:
                pdf_path.unlink()
                break
            except PermissionError:
                if retry < 3:
                    _time.sleep(1)
    try:
        result = subprocess.run(
            [LATEX_CMD] + LATEX_OPTS + [f"-output-directory={out_dir}", str(tex_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=tex_path.parent
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    except FileNotFoundError:
        return False, f"未找到命令: {LATEX_CMD}"
    except Exception as e:
        return False, str(e)

def compile_latex(tex_path: Path) -> Path | None:
    PDF_OUT_DIR.mkdir(parents=True, exist_ok=True)
    tex_path = tex_path.resolve()
    if not shutil.which(LATEX_CMD):
        log.warning("  [skip] 未找到xelatex，跳过编译")
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
            log.info(f"  [ok] 编译成功: {pdf_path}")
            for bak in tex_path.parent.glob(tex_path.stem + ".bak*.tex"):
                bak.unlink(missing_ok=True)
            return pdf_path
        error = parse_error(log_text)
        log.warning(f"  [fail] 编译失败:\n{error}")
        if attempt < MAX_RETRIES:
            log.info("  🔧 调用DeepSeek修复LaTeX...")
            try:
                resp = client.chat.completions.create(
                    model=MODEL, max_tokens=MAX_TOKENS,
                    messages=[{"role": "user", "content": FIX_PROMPT.format(
                        error=error, tex=tex_path.read_text(encoding="utf-8"))}]
                )
                fixed = sanitize_latex(extract_latex(resp.choices[0].message.content))
                shutil.copy(tex_path, tex_path.with_suffix(f".bak{attempt}.tex"))
                tex_path.write_text(fixed, encoding="utf-8")
            except Exception as e:
                log.warning(f"  LLM修复失败: {e}")
        else:
            log.error(f"  [abort] 请手动检查: {tex_path}")
    return None

def clean_aux(stem: str):
    for ext in [".aux", ".log", ".out", ".toc"]:
        f = PDF_OUT_DIR / (stem + ext)
        if f.exists():
            f.unlink()

# ── 主流程 ────────────────────────────────────────────────────────────────────
def generate(topic: str, mode: str = "teacher") -> list[Path]:
    need_tikz = topic in TIKZ_TOPICS
    if topic not in SYLLABUS:
        log.error(f"topic '{topic}' 不在课程大纲中")
        for t in SYLLABUS:
            print(f"  {t}")
        return []
    info = SYLLABUS[topic]
    log.info(f"{'='*60}")
    log.info(f"生成讲义: {topic} [{info['module']}] (模式: {mode})")
    log.info(f"{'='*60}")
    reference = collect_reference_texts(topic, PDF_DIR)
    prompt = build_prompt(topic, info["module"], info["key_points"], reference)
    raw   = call_llm(prompt)
    latex = sanitize_latex(extract_latex(raw))
    if need_tikz:
        latex = inject_figures_into_latex(latex)   # ← 加这一行
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    safe = topic.replace("/", "_").replace("\\", "_")
    results = []
    if mode in ("teacher", "both"):
        tex_path = TEX_DIR / f"{safe}.tex"
        tex_path.write_text(latex, encoding="utf-8")
        log.info(f"  LaTeX: {tex_path} ({len(latex)}字符)")
        results.append(tex_path)
        pdf = compile_latex(tex_path)
        if pdf:
            clean_aux(safe)
            results.append(pdf)
    if mode in ("student", "both"):
        stex = strip_answers_for_student(latex)
        sp = TEX_DIR / f"{safe}_学生版.tex"
        sp.write_text(stex, encoding="utf-8")
        log.info(f"  学生版LaTeX: {sp}")
        results.append(sp)
        pdf = compile_latex(sp)
        if pdf:
            clean_aux(f"{safe}_学生版")
            results.append(pdf)
    return results

def main():
    parser = argparse.ArgumentParser(description="高中数学讲义生成器 v4")
    parser.add_argument("topic", nargs="?")
    parser.add_argument("--mode", choices=["teacher","student","both"], default="teacher")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        results = []
        for topic in SYLLABUS:
            pdfs = generate(topic, mode=args.mode)
            results.append((topic, "OK" if pdfs else "FAIL",
                            ", ".join(str(p) for p in pdfs)))
            print()
        print("\n" + "="*60)
        for t, s, p in results:
            print(f"  {s} {t:<25} -> {p}")
    elif args.topic:
        pdfs = generate(args.topic, mode=args.mode)
        if pdfs:
            print("\n完成：")
            for p in pdfs:
                print(f"   {p}")
        else:
            print(f"\n失败，请检查 output/tex/{args.topic}.tex")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()