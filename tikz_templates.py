"""
tikz_templates.py — 参数化TikZ图形模板系统
用法：LLM只输出图形描述JSON，Python渲染为TikZ代码，完全避免LLM自由写TikZ

支持图形类型：
  ellipse_x      椭圆（焦点在x轴）
  ellipse_y      椭圆（焦点在y轴）
  hyperbola_x    双曲线（焦点在x轴）
  hyperbola_y    双曲线（焦点在y轴）
  parabola_right 抛物线（开口向右 x²=4py → y²=2px）
  parabola_up    抛物线（开口向上 x²=2py）
  line_circle    直线与圆
  line_conic     直线与圆锥曲线（在圆锥曲线图上叠加直线）
"""

import math
import json
import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FigureSpec:
    """LLM输出的图形描述，Python将其渲染为TikZ"""
    fig_type: str          # 见上方支持列表
    a: float = 0.0         # 椭圆/双曲线实半轴；抛物线焦准距p
    b: float = 0.0         # 椭圆/双曲线虚半轴
    # 可选叠加元素
    show_asymptotes: bool = True   # 双曲线渐近线
    show_directrix: bool = False   # 抛物线准线
    show_foci: bool = True         # 焦点
    show_vertices: bool = True     # 顶点
    extra_points: list = field(default_factory=list)   # 额外标注点 [{"label":"A","x":1,"y":2}, ...]
    lines: list = field(default_factory=list)          # 叠加直线 [{"slope":0.5,"intercept":1}, ...]
    # 圆（用于直线与圆题型）
    circle_center: tuple = (0, 0)
    circle_radius: float = 0.0
    # 图形尺寸（自动计算，一般不需手动设置）
    scale: float = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

VIEW = 3.5  # 所有图形统一坐标轴半径（单位：TikZ坐标），调此值控制图形大小

def _fmt(v: float) -> str:
    """格式化数值：整数不带小数点，否则保留4位有效数字"""
    if v == int(v):
        return str(int(v))
    return f"{v:.4f}".rstrip('0')

def _coord_label(x: float, y: float, label: str, pos: str = "below") -> str:
    if not label:
        return ""
    return f"  \\node[{pos}] at ({_fmt(x)},{_fmt(y)}) {{${label}$}};\n"

def _dot(x: float, y: float) -> str:
    return f"  \\fill ({_fmt(x)},{_fmt(y)}) circle (1.5pt);\n"

def _axis(xmin, xmax, ymin, ymax) -> str:
    return (
        f"  \\draw[->] ({_fmt(xmin)},0) -- ({_fmt(xmax)},0) node[right] {{$x$}};\n"
        f"  \\draw[->] (0,{_fmt(ymin)}) -- (0,{_fmt(ymax)}) node[above] {{$y$}};\n"
        f"  \\node[below left] at (0,0) {{$O$}};\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 椭圆模板
# ─────────────────────────────────────────────────────────────────────────────

def _render_ellipse(spec: FigureSpec, x_axis: bool) -> str:
    a, b = spec.a, spec.b
    c = math.sqrt(abs(a**2 - b**2))

    if x_axis:
        semi_x, semi_y = a, b
        f1x, f1y, f2x, f2y = -c, 0, c, 0
        f1_label, f2_label = "F_1", "F_2"
        v_labels = [(-a,0,"below",""), (a,0,"below",""),
                    (0,b,"left",""), (0,-b,"left","")]
    else:
        semi_x, semi_y = b, a
        f1x, f1y, f2x, f2y = 0, -c, 0, c
        f1_label, f2_label = "F_1", "F_2"
        v_labels = [(0,a,"right",""), (0,-a,"right",""),
                    (b,0,"below",""), (-b,0,"below","")]

    body = "\\begin{tikzpicture}[scale=1.0]\n"
    body += _axis(-VIEW, VIEW, -VIEW, VIEW)

    # 椭圆曲线（参数方程，避免ellipse命令）
    body += (f"  \\draw[thick] plot[domain=0:360,samples=120]"
             f"  ({{{_fmt(semi_x)}*cos(\\x)}},{{{_fmt(semi_y)}*sin(\\x)}});\n")

    if spec.show_vertices:
        for vx, vy, pos, lbl in v_labels:
            body += _dot(vx, vy)
            body += _coord_label(vx, vy, lbl, pos)

    if spec.show_foci:
        body += _dot(f1x, f1y)
        body += _dot(f2x, f2y)
        body += _coord_label(f1x, f1y, f1_label, "below left")
        body += _coord_label(f2x, f2y, f2_label, "below right")

    body += _extra_elements(spec, VIEW, VIEW)
    body += "\\end{tikzpicture}\n"
    return body


# ─────────────────────────────────────────────────────────────────────────────
# 双曲线模板
# ─────────────────────────────────────────────────────────────────────────────

def _render_hyperbola(spec: FigureSpec, x_axis: bool) -> str:
    a, b = spec.a, spec.b
    c = math.sqrt(a**2 + b**2)
    asym_slope = (b / a) if x_axis else (a / b)

    if x_axis:
        f1x, f1y, f2x, f2y = -c, 0, c, 0
        f1_lbl, f2_lbl = "F_1", "F_2"
    else:
        f1x, f1y, f2x, f2y = 0, -c, 0, c
        f1_lbl, f2_lbl = "F_1", "F_2"

    body = "\\begin{tikzpicture}[scale=1.0]\n"
    body += _axis(-VIEW, VIEW, -VIEW, VIEW)

    if x_axis:
        # 只画VIEW范围内的双曲线部分
        tmax = math.acosh(VIEW / a) + 0.1
        body += (f"  \\draw[thick] plot[domain={_fmt(-tmax)}:{_fmt(tmax)},samples=80]"
                 f"  ({{{_fmt(a)}*cosh(\\x)}},{{{_fmt(b)}*sinh(\\x)}});\n")
        body += (f"  \\draw[thick] plot[domain={_fmt(-tmax)}:{_fmt(tmax)},samples=80]"
                 f"  ({{{_fmt(-a)}*cosh(\\x)}},{{{_fmt(b)}*sinh(\\x)}});\n")
        if spec.show_vertices:
            body += _dot(a, 0);  body += _coord_label(a, 0, "", "below right")
            body += _dot(-a, 0); body += _coord_label(-a, 0, "", "below left")
    else:
        tmax = math.acosh(VIEW / a) + 0.1
        body += (f"  \\draw[thick] plot[domain={_fmt(-tmax)}:{_fmt(tmax)},samples=80]"
                 f"  ({{{_fmt(b)}*sinh(\\x)}},{{{_fmt(a)}*cosh(\\x)}});\n")
        body += (f"  \\draw[thick] plot[domain={_fmt(-tmax)}:{_fmt(tmax)},samples=80]"
                 f"  ({{{_fmt(b)}*sinh(\\x)}},{{{_fmt(-a)}*cosh(\\x)}});\n")
        if spec.show_vertices:
            body += _dot(0, a);  body += _coord_label(0, a,  "", "right")
            body += _dot(0, -a); body += _coord_label(0, -a, "", "right")

    # 渐近线（虚线，裁剪到VIEW范围）
    if spec.show_asymptotes:
        v = _fmt(VIEW)
        nv = _fmt(-VIEW)
        k = _fmt(asym_slope)
        nk = _fmt(-asym_slope)
        body += f"  \\draw[dashed,gray] ({nv},{{{nk}*{v}}}) -- ({v},{{{k}*{v}}});\n"
        body += f"  \\draw[dashed,gray] ({nv},{{{k}*{v}}}) -- ({v},{{{nk}*{v}}});\n"

    if spec.show_foci and c <= VIEW * 1.2:  # 焦点在合理范围内才标注
        body += _dot(f1x, f1y); body += _coord_label(f1x, f1y, f1_lbl, "below left")
        body += _dot(f2x, f2y); body += _coord_label(f2x, f2y, f2_lbl, "below right")

    body += _extra_elements(spec, VIEW, VIEW)
    body += "\\end{tikzpicture}\n"
    return body


# ─────────────────────────────────────────────────────────────────────────────
# 抛物线模板
# ─────────────────────────────────────────────────────────────────────────────

def _render_parabola(spec: FigureSpec, open_right: bool) -> str:
    p = spec.a
    fp = p / 2

    body = "\\begin{tikzpicture}[scale=1.0]\n"

    if open_right:
        # y²=2px，x轴起点稍微往左留出准线空间
        body += _axis(-fp - 0.5, VIEW, -VIEW, VIEW)
        body += (f"  \\draw[thick] plot[domain={_fmt(-VIEW)}:{_fmt(VIEW)},samples=100]"
                 f"  ({{\\x*\\x/{_fmt(2*p)}}},{{\\x}});\n")
        if spec.show_directrix:
            body += (f"  \\draw[dashed,gray] ({_fmt(-fp)},{_fmt(-VIEW)}) -- "
                     f"({_fmt(-fp)},{_fmt(VIEW)}) node[above]{{$x={_fmt(-fp)}$}};\n")
        if spec.show_foci:
            body += _dot(fp, 0)
            body += _coord_label(fp, 0, "F", "above right")
    else:
        body += _axis(-VIEW, VIEW, -fp - 0.5, VIEW)
        body += (f"  \\draw[thick] plot[domain={_fmt(-VIEW)}:{_fmt(VIEW)},samples=100]"
                 f"  ({{\\x}},{{\\x*\\x/{_fmt(2*p)}}});\n")
        if spec.show_directrix:
            body += (f"  \\draw[dashed,gray] ({_fmt(-VIEW)},{_fmt(-fp)}) -- "
                     f"({_fmt(VIEW)},{_fmt(-fp)}) node[right]{{$y={_fmt(-fp)}$}};\n")
        if spec.show_foci:
            body += _dot(0, fp)
            body += _coord_label(0, fp, "F", "above right")

    body += _extra_elements(spec, VIEW, VIEW)
    body += "\\end{tikzpicture}\n"
    return body


# ─────────────────────────────────────────────────────────────────────────────
# 直线与圆模板
# ─────────────────────────────────────────────────────────────────────────────

def _render_circle(spec: FigureSpec) -> str:
    cx, cy = spec.circle_center
    r = spec.circle_radius

    body = "\\begin{tikzpicture}[scale=1.0]\n"
    body += _axis(-VIEW, VIEW, -VIEW, VIEW)
    body += (f"  \\draw[thick] plot[domain=0:360,samples=120]"
             f"  ({{{_fmt(cx)}+{_fmt(r)}*cos(\\x)}},{{{_fmt(cy)}+{_fmt(r)}*sin(\\x)}});\n")
    body += _dot(cx, cy)
    body += _coord_label(cx, cy, "O" if (cx == 0 and cy == 0) else "C", "below left")

    body += _extra_elements(spec, VIEW, VIEW)
    body += "\\end{tikzpicture}\n"
    return body


# ─────────────────────────────────────────────────────────────────────────────
# 叠加元素（直线、额外标注点）——所有模板共用
# ─────────────────────────────────────────────────────────────────────────────

def _extra_elements(spec: FigureSpec, xmax: float, ymax: float) -> str:
    body = ""
    # 叠加直线
    for line in spec.lines:
        k = line.get("slope")
        b_intercept = line.get("intercept", 0)
        if k is None:
            # 垂直线 x=c
            xv = line.get("x", 0)
            body += (f"  \\draw[thick] ({_fmt(xv)},{_fmt(-ymax)}) -- "
                     f"({_fmt(xv)},{_fmt(ymax)});\n")
        else:
            x1, x2 = -xmax, xmax
            y1 = k * x1 + b_intercept
            y2 = k * x2 + b_intercept
            body += (f"  \\draw[thick] ({_fmt(x1)},{_fmt(y1)}) -- "
                     f"({_fmt(x2)},{_fmt(y2)});\n")
    # 额外标注点
    for pt in spec.extra_points:
        px, py = pt["x"], pt["y"]
        lbl = pt.get("label", "")
        pos = pt.get("pos", "above right")
        body += _dot(px, py)
        if lbl:
            body += _coord_label(px, py, lbl, pos)
    return body


# ─────────────────────────────────────────────────────────────────────────────
# 主入口：从FigureSpec渲染TikZ
# ─────────────────────────────────────────────────────────────────────────────

def render_tikz(spec: FigureSpec) -> str:
    """给定FigureSpec，返回完整TikZ环境字符串（含begin/end）"""
    t = spec.fig_type
    if t == "ellipse_x":
        return _render_ellipse(spec, x_axis=True)
    elif t == "ellipse_y":
        return _render_ellipse(spec, x_axis=False)
    elif t == "hyperbola_x":
        return _render_hyperbola(spec, x_axis=True)
    elif t == "hyperbola_y":
        return _render_hyperbola(spec, x_axis=False)
    elif t == "parabola_right":
        return _render_parabola(spec, open_right=True)
    elif t == "parabola_up":
        return _render_parabola(spec, open_right=False)
    elif t == "line_circle":
        return _render_circle(spec)
    elif t == "line_conic":
        # 根据子类型分发，lines字段叠加直线
        sub = spec.fig_type  # 调用者应设置正确子类型
        raise ValueError("line_conic请直接设置具体曲线类型再添加lines字段")
    else:
        raise ValueError(f"未知图形类型: {t}")


def render_tikz_centered(spec: FigureSpec) -> str:
    """带center环境包裹，适合插入LaTeX正文"""
    tikz = render_tikz(spec)
    return f"\\begin{{center}}\n{tikz}\\end{{center}}\n"


# ─────────────────────────────────────────────────────────────────────────────
# LLM JSON → FigureSpec 解析器
# ─────────────────────────────────────────────────────────────────────────────

def parse_figure_json(json_str: str) -> Optional[FigureSpec]:
    """
    解析LLM输出的图形描述JSON，返回FigureSpec。
    JSON格式示例：
    {
      "fig_type": "hyperbola_x",
      "a": 1,
      "b": 1.732,
      "show_asymptotes": true,
      "show_foci": true,
      "show_directrix": false,
      "lines": [{"slope": 0.5, "intercept": 1}],
      "extra_points": [{"label": "A", "x": 2, "y": 1.5, "pos": "above right"}]
    }
    """
    try:
        # 提取JSON块（LLM可能包裹在```json ... ```里）
        m = re.search(r'```json\s*(.*?)\s*```', json_str, re.DOTALL)
        if m:
            json_str = m.group(1)
        data = json.loads(json_str)
        spec = FigureSpec(
            fig_type=data["fig_type"],
            a=float(data.get("a", 0)),
            b=float(data.get("b", 0)),
            show_asymptotes=bool(data.get("show_asymptotes", True)),
            show_directrix=bool(data.get("show_directrix", False)),
            show_foci=bool(data.get("show_foci", True)),
            show_vertices=bool(data.get("show_vertices", True)),
            extra_points=data.get("extra_points", []),
            lines=data.get("lines", []),
            circle_center=tuple(data.get("circle_center", [0, 0])),
            circle_radius=float(data.get("circle_radius", 0)),
        )
        return spec
    except Exception as e:
        print(f"[tikz_templates] JSON解析失败: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LLM Prompt片段：告诉模型如何输出图形JSON
# ─────────────────────────────────────────────────────────────────────────────

FIGURE_JSON_INSTRUCTION = """
【图形描述规范】
每道需要配图的例题，在【解题过程】tcolorbox之后，输出一个如下格式的JSON块（用```json包裹），
Python将自动将其渲染为精确的TikZ图形，你不需要自己写TikZ代码：

```json
{
  "fig_type": "hyperbola_x",   // 必填，见下方类型表
  "a": 1,                       // 实半轴（椭圆/双曲线）或焦准距p（抛物线）
  "b": 1.732,                   // 虚半轴（椭圆/双曲线），抛物线不需要
  "show_asymptotes": true,      // 双曲线是否显示渐近线
  "show_directrix": false,      // 抛物线是否显示准线
  "show_foci": true,            // 是否标注焦点
  "show_vertices": true,        // 是否标注顶点
  "lines": [],                  // 叠加直线列表，每项{"slope":斜率,"intercept":截距}，垂直线用{"x":值}
  "extra_points": [],           // 额外标注点，每项{"label":"A","x":1,"y":2,"pos":"above right"}
  "circle_center": [0, 0],     // 仅line_circle类型使用
  "circle_radius": 0            // 仅line_circle类型使用
}
```

fig_type取值表：
  ellipse_x      椭圆，焦点在x轴（x²/a²+y²/b²=1，a>b）
  ellipse_y      椭圆，焦点在y轴（x²/b²+y²/a²=1，a>b）
  hyperbola_x    双曲线，焦点在x轴（x²/a²-y²/b²=1）
  hyperbola_y    双曲线，焦点在y轴（y²/a²-x²/b²=1）
  parabola_right 抛物线，开口向右（y²=2px，a填p值）
  parabola_up    抛物线，开口向上（x²=2py，a填p值）
  line_circle    直线与圆（需填circle_center和circle_radius）

注意：
- a和b必须是具体数值（如1.732），不能是符号
- 如果题目涉及直线与曲线，把直线信息填入lines字段，曲线用对应fig_type
- 不需要配图的例题（纯代数计算题）不要输出JSON块
- 若题目中的双曲线/椭圆/抛物线参数（a、b、c）本身是待求量，禁止配图（因为图形参数即为答案，配图会剧透解题结果）
- line_circle类型：circle_center填圆心坐标，circle_radius填半径，同时在lines字段里加入渐近线（用slope表示斜率）
"""

# ─────────────────────────────────────────────────────────────────────────────
# 将LaTeX正文中的JSON块替换为TikZ代码
# ─────────────────────────────────────────────────────────────────────────────

def inject_figures_into_latex(latex: str) -> str:
    """
    扫描LaTeX中所有```json...```块，
    尝试解析为FigureSpec并渲染为TikZ，替换原块。
    无法解析的块保留原样（不报错）。
    """
    def _replace(m):
        json_str = m.group(1).strip()
        spec = parse_figure_json(json_str)
        if spec is None:
            return ""  # 解析失败则删除，不留残留
        try:
            tikz = render_tikz_centered(spec)
            return tikz
        except Exception as e:
            print(f"[tikz_templates] 渲染失败: {e}")
            return ""

    # 匹配```json ... ```块
    result = re.sub(r'```json\s*(.*?)\s*```', _replace, latex, flags=re.DOTALL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 快速测试
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 测试1：双曲线 x²/1 - y²/3 = 1（a=1, b=√3, c=2）
    spec1 = FigureSpec(
        fig_type="hyperbola_x",
        a=1.0, b=1.732,
        show_asymptotes=True,
        show_foci=True,
    )
    print("=== 双曲线 x²-y²/3=1 ===")
    print(render_tikz(spec1))

    # 测试2：椭圆 x²/16 + y²/9 = 1（a=4, b=3）
    spec2 = FigureSpec(fig_type="ellipse_x", a=4.0, b=3.0)
    print("=== 椭圆 x²/16+y²/9=1 ===")
    print(render_tikz(spec2))

    # 测试3：抛物线 y²=4x（p=2）
    spec3 = FigureSpec(fig_type="parabola_right", a=2.0, show_directrix=True)
    print("=== 抛物线 y²=4x ===")
    print(render_tikz(spec3))

    # 测试4：JSON解析+渲染
    json_example = '''```json
{
  "fig_type": "hyperbola_x",
  "a": 1,
  "b": 1.732,
  "show_asymptotes": true,
  "show_foci": true,
  "lines": [{"slope": 0.5, "intercept": 1}],
  "extra_points": [{"label": "P", "x": 2, "y": 2, "pos": "above right"}]
}
```'''
    spec4 = parse_figure_json(json_example)
    print("=== JSON解析测试 ===")
    print(render_tikz(spec4))