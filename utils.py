"""工具函数：单纯形表渲染、分数格式化等"""

from fractions import Fraction
from simplex_core import Snapshot, BIG_M


def frac_display(f: Fraction, use_latex: bool = True) -> str:
    if f is None:
        return "—"
    f = Fraction(f).limit_denominator(10**8)

    if abs(f) >= BIG_M // 2:
        coeff = f / BIG_M
        coeff = Fraction(coeff).limit_denominator(1000)
        remainder = f - coeff * BIG_M
        remainder = Fraction(remainder).limit_denominator(1000)
        parts = []
        if coeff != 0:
            if coeff == 1:
                parts.append("M")
            elif coeff == -1:
                parts.append("-M")
            else:
                parts.append(f"{_simple_frac(coeff, use_latex)}M")
        if remainder != 0:
            sign = "+" if remainder > 0 else ""
            parts.append(f"{sign}{_simple_frac(remainder, use_latex)}")
        return "".join(parts) if parts else "0"

    return _simple_frac(f, use_latex)


def _simple_frac(f: Fraction, use_latex: bool) -> str:
    f = Fraction(f).limit_denominator(10**8)
    if f.denominator == 1:
        return str(f.numerator)
    if use_latex:
        sign = "-" if f < 0 else ""
        return f"{sign}\\dfrac{{{abs(f.numerator)}}}{{{f.denominator}}}"
    else:
        return f"{f.numerator}/{f.denominator}"


def snapshot_to_latex_table(snap: Snapshot, highlight: bool = True) -> str:
    tab = snap.tableau
    m = len(tab) - 1
    n = len(tab[0]) - 1

    var_names = snap.var_names
    basis = snap.basis

    headers = ["基变量"] + [f"${name}$" for name in var_names] + ["$b$"]
    sep = "|".join(["---"] * len(headers))

    rows = []
    rows.append("|" + "|".join(headers) + "|")
    rows.append("|" + sep + "|")

    for i in range(m):
        bv_name = f"${var_names[basis[i]]}$"
        cells = [bv_name]
        for j in range(n):
            val_str = frac_display(tab[i][j])
            if highlight and i == snap.pivot_row and j == snap.pivot_col:
                cells.append(f"**🔴 ${val_str}$**")
            elif highlight and j == snap.pivot_col:
                cells.append(f"🔵 ${val_str}$")
            elif highlight and i == snap.pivot_row:
                cells.append(f"🟢 ${val_str}$")
            else:
                cells.append(f"${val_str}$")
        cells.append(f"${frac_display(tab[i][-1])}$")
        rows.append("|" + "|".join(cells) + "|")

    # 目标行标签：根据阶段显示 σ(z) 或 σ(w)
    obj_label = snap.obj_name
    cells = [f"$\\sigma$（{obj_label}）"]
    for j in range(n):
        val_str = frac_display(tab[m][j])
        if highlight and j == snap.pivot_col:
            cells.append(f"**🔵 ${val_str}$**")
        else:
            cells.append(f"${val_str}$")
    cells.append(f"${frac_display(tab[m][-1])}$")
    rows.append("|" + "|".join(cells) + "|")

    return "\n".join(rows)
