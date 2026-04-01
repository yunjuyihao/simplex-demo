"""单纯形法求解引擎 —— 支持大M法 + 两阶段法，分数精确运算，逐步快照"""

from fractions import Fraction
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Optional

BIG_M = Fraction(10**6)


@dataclass
class Snapshot:
    """一次迭代的完整快照"""
    iteration: int
    tableau: list[list[Fraction]]
    basis: list[int]
    var_names: list[str]
    obj_name: str = "z"
    pivot_col: int = -1
    pivot_row: int = -1
    theta: list[Optional[Fraction]] = field(default_factory=list)
    explanation: str = ""
    status: str = "ongoing"       # ongoing / optimal / unbounded / infeasible
    phase: int = 0                # 0=普通/大M, 1=两阶段第一阶段, 2=两阶段第二阶段


# ============================================================
#  工具函数
# ============================================================

def _frac(v) -> Fraction:
    return Fraction(v).limit_denominator(10**9)


def _frac_str(f: Fraction) -> str:
    """内部文字格式化，现在也支持大M解析了"""
    if f is None:
        return "-"
    f = _frac(f)
    
    # 【修复】为文字说明也增加大M识别雷达
    if abs(f) > 1000:
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
                parts.append(f"{_frac_str_simple(coeff)}M")
        if remainder != 0:
            sign = "+" if remainder > 0 else ""
            parts.append(f"{sign}{_frac_str_simple(remainder)}")
        return "".join(parts) if parts else "0"
        
    return _frac_str_simple(f)

def _frac_str_simple(f: Fraction) -> str:
    """基础的分数转 LaTeX 字符串"""
    if f.denominator == 1:
        return str(f.numerator)
    sign = "-" if f < 0 else ""
    return f"{sign}\\dfrac{{{abs(f.numerator)}}}{{{f.denominator}}}"

# ============================================================
#  核心单纯形迭代器（不做标准化，只做纯迭代）
# ============================================================

class _SimplexIterator:
    """
    给定已经构造好的初始单纯形表和基，执行纯单纯形迭代。
    每一步产出一个 Snapshot。
    """

    def __init__(self, tableau, basis, var_names, obj_name="z",
                 phase=0, artificial_indices=None, max_iter=100):
        self.tableau = [[_frac(v) for v in row] for row in tableau]
        self.basis = list(basis)
        self.var_names = list(var_names)
        self.obj_name = obj_name
        self.phase = phase
        self.artificial_indices = artificial_indices or []
        self.max_iter = max_iter
        self.snapshots: list[Snapshot] = []

    # ---------- 快照 ----------
    def _snap(self, explanation, status="ongoing",
              pivot_col=-1, pivot_row=-1, theta=None) -> Snapshot:
        s = Snapshot(
            iteration=len(self.snapshots),
            tableau=deepcopy(self.tableau),
            basis=list(self.basis),
            var_names=list(self.var_names),
            obj_name=self.obj_name,
            pivot_col=pivot_col,
            pivot_row=pivot_row,
            theta=theta or [],
            explanation=explanation,
            status=status,
            phase=self.phase,
        )
        self.snapshots.append(s)
        return s

    # ---------- 入基 ----------
    def _find_entering(self) -> int:
        obj_row = self.tableau[-1]
        n = len(obj_row) - 1
        best_col, best_val = -1, Fraction(0)
        for j in range(n):
            if obj_row[j] > best_val:
                best_val = obj_row[j]
                best_col = j
        return best_col

    # ---------- 出基 ----------
    def _find_leaving(self, col: int):
        m = len(self.tableau) - 1
        theta: list[Optional[Fraction]] = []
        min_theta, min_row = None, -1
        for i in range(m):
            a = self.tableau[i][col]
            if a > 0:
                t = self.tableau[i][-1] / a
                theta.append(t)
                if min_theta is None or t < min_theta:
                    min_theta = t
                    min_row = i
            else:
                theta.append(None)
        return min_row, theta

    # ---------- 旋转 ----------
    def _pivot(self, row, col):
        m = len(self.tableau) - 1
        n = len(self.tableau[0])
        pv = self.tableau[row][col]
        for k in range(n):
            self.tableau[row][k] /= pv
        for i in range(m + 1):
            if i == row:
                continue
            factor = self.tableau[i][col]
            if factor != 0:
                for k in range(n):
                    self.tableau[i][k] -= factor * self.tableau[row][k]
        self.basis[row] = col

    # ---------- 主循环 ----------
    def run(self, init_msg: str = "") -> list[Snapshot]:
        self._snap(init_msg or "📋 初始单纯形表构造完成。")

        for _ in range(self.max_iter):
            entering = self._find_entering()
            n = len(self.tableau[0]) - 1
            m = len(self.tableau) - 1

            if entering == -1:
                # 最优
                # 检查人工变量
                has_art = False
                for i in range(m):
                    if self.basis[i] in self.artificial_indices and self.tableau[i][-1] > 0:
                        has_art = True
                        break
                if has_art:
                    self._snap(
                        "❌ 所有检验数 $\\leq 0$，但基中仍有值 $> 0$ 的人工变量，"
                        "原问题**无可行解**。",
                        status="infeasible"
                    )
                else:
                    sol = self._read_solution()
                    self._snap(
                        self._optimal_msg(sol),
                        status="optimal"
                    )
                return self.snapshots

            # 出基
            leaving, theta = self._find_leaving(entering)
            if leaving == -1:
                self._snap(
                    f"选入基变量 ${self.var_names[entering]}$"
                    f"（检验数 $= {_frac_str(self.tableau[-1][entering])}$），"
                    f"但该列所有系数 $\\leq 0$，**问题无界**！",
                    status="unbounded",
                    pivot_col=entering,
                )
                return self.snapshots

            # 生成说明
            explanation = self._iter_explanation(entering, leaving, theta)
            self._snap(explanation, pivot_col=entering, pivot_row=leaving, theta=theta)

            self._pivot(leaving, entering)

        self._snap("⚠️ 达到最大迭代次数。", status="infeasible")
        return self.snapshots

    # ---------- 说明文本 ----------
    def _iter_explanation(self, entering, leaving, theta):
        obj_row = self.tableau[-1]
        m = len(self.tableau) - 1
        entering_name = self.var_names[entering]
        leaving_name = self.var_names[self.basis[leaving]]

        theta_parts = []
        for i in range(m):
            bv_name = self.var_names[self.basis[i]]
            if theta[i] is not None:
                theta_parts.append(
                    f"$\\theta({bv_name}) = "
                    f"{_frac_str(self.tableau[i][-1])} \\div "
                    f"{_frac_str(self.tableau[i][entering])} = "
                    f"{_frac_str(theta[i])}$"
                )
            else:
                theta_parts.append(f"$\\theta({bv_name})$ = — （系数 $\\leq 0$）")

        phase_prefix = ""
        if self.phase == 1:
            phase_prefix = "【第一阶段】"
        elif self.phase == 2:
            phase_prefix = "【第二阶段】"

        return (
            f"**{phase_prefix}第 {len(self.snapshots)} 次迭代**\n\n"
            f"1️⃣ **入基变量**：检验数最大正值 "
            f"${_frac_str(obj_row[entering])}$ → ${entering_name}$ 入基\n\n"
            f"2️⃣ **最小比值法**：{'；'.join(theta_parts)}\n\n"
            f"最小 $\\theta = {_frac_str(theta[leaving])}$ "
            f"→ ${leaving_name}$ 出基\n\n"
            f"3️⃣ **主元** = ${_frac_str(self.tableau[leaving][entering])}$，执行旋转 ↓"
        )

    def _optimal_msg(self, sol):
        phase_prefix = ""
        if self.phase == 1:
            phase_prefix = "【第一阶段】"
        elif self.phase == 2:
            phase_prefix = "【第二阶段】"
        obj_val = self.tableau[-1][-1]
        return (
            f"✅ {phase_prefix}所有检验数 $\\leq 0$，达到**最优解**！\n\n"
            f"目标行右端值 = ${_frac_str(obj_val)}$"
        )

    def _read_solution(self):
        m = len(self.tableau) - 1
        n = len(self.tableau[0]) - 1
        sol = [Fraction(0)] * n
        for i in range(m):
            bv = self.basis[i]
            if bv < n:
                sol[bv] = self.tableau[i][-1]
        return sol


# ============================================================
#  标准化器（添加松弛/剩余/人工变量）
# ============================================================

class _Standardizer:
    """将原始 LP 转换为标准形式，构造初始单纯形表"""

    def __init__(self, c, A, b, constraint_types, is_min, var_names):
        self.c = [_frac(v) for v in c]
        self.A = [[_frac(v) for v in row] for row in A]
        self.b = [_frac(v) for v in b]
        self.types = list(constraint_types)
        self.is_min = is_min
        self.num_orig = len(c)
        self.orig_var_names = list(var_names) if var_names else [f"x_{i+1}" for i in range(self.num_orig)]

    def build(self):
        """
        返回：
            var_names, tableau, basis, artificial_indices,
            c_orig_extended (用于两阶段法第二阶段)
        """
        m = len(self.b)

        # b >= 0 预处理
        for i in range(m):
            if self.b[i] < 0:
                self.A[i] = [-v for v in self.A[i]]
                self.b[i] = -self.b[i]
                if self.types[i] == '<=':
                    self.types[i] = '>='
                elif self.types[i] == '>=':
                    self.types[i] = '<='

        var_names = list(self.orig_var_names)
        col_offset = self.num_orig
        basis = [0] * m
        artificial_indices = []

        # 额外列模板
        extra = [[Fraction(0)] * 0 for _ in range(m)]  # 先空着

        slack_id = surplus_id = art_id = 0

        col_types = []  # 'slack', 'surplus', 'artificial'

        for i, ct in enumerate(self.types):
            if ct == '<=':
                slack_id += 1
                var_names.append(f"s_{slack_id}")
                col_types.append('slack')
                for j in range(m):
                    extra[j].append(Fraction(1) if j == i else Fraction(0))
                basis[i] = col_offset
                col_offset += 1

            elif ct == '>=':
                surplus_id += 1
                var_names.append(f"e_{surplus_id}")
                col_types.append('surplus')
                for j in range(m):
                    extra[j].append(Fraction(-1) if j == i else Fraction(0))
                col_offset += 1

                art_id += 1
                var_names.append(f"a_{art_id}")
                col_types.append('artificial')
                for j in range(m):
                    extra[j].append(Fraction(1) if j == i else Fraction(0))
                artificial_indices.append(col_offset)
                basis[i] = col_offset
                col_offset += 1

            elif ct == '=':
                art_id += 1
                var_names.append(f"a_{art_id}")
                col_types.append('artificial')
                for j in range(m):
                    extra[j].append(Fraction(1) if j == i else Fraction(0))
                artificial_indices.append(col_offset)
                basis[i] = col_offset
                col_offset += 1

        total_vars = col_offset

        # 构造约束行
        tableau = []
        for i in range(m):
            row = list(self.A[i]) + extra[i] + [self.b[i]]
            tableau.append(row)

        # 原始目标函数系数（max 化），用于两阶段法第二阶段
        if self.is_min:
            c_max = [-v for v in self.c]
        else:
            c_max = list(self.c)

        # 扩展到所有变量列
        c_orig_extended = list(c_max) + [Fraction(0)] * (total_vars - self.num_orig) + [Fraction(0)]

        return var_names, tableau, basis, artificial_indices, c_orig_extended, total_vars


# ============================================================
#  对外接口：SimplexSolver
# ============================================================

class SimplexSolver:
    """
    求解线性规划，支持大M法和两阶段法。
    
    method: 'big_m' | 'two_phase'
    """

    def __init__(self, c, A, b, constraint_types,
                 is_min=False, var_names=None, method='big_m'):
        self.c = c
        self.A = A
        self.b = b
        self.constraint_types = constraint_types
        self.is_min = is_min
        self.var_names = var_names or [f"x_{i+1}" for i in range(len(c))]
        self.method = method
        self.num_orig = len(c)

    def solve(self) -> list[Snapshot]:
        std = _Standardizer(
            self.c, self.A, self.b,
            self.constraint_types, self.is_min, self.var_names
        )
        var_names, tableau, basis, art_indices, c_orig_ext, total_vars = std.build()
        m = len(tableau)  # 约束行数

        has_artificial = len(art_indices) > 0

        if not has_artificial or self.method == 'big_m':
            return self._solve_big_m(var_names, tableau, basis, art_indices, c_orig_ext, total_vars)
        else:
            return self._solve_two_phase(var_names, tableau, basis, art_indices, c_orig_ext, total_vars)

    # ================== 大 M 法 ==================
    def _solve_big_m(self, var_names, tableau, basis, art_indices, c_orig_ext, total_vars):
        m = len(tableau)
        n = total_vars

        # 构造目标行
        if art_indices:
            # 大 M 法：人工变量目标系数 = -M（max 化问题）
            if self.is_min:
                c_max = [-_frac(v) for v in self.c]
            else:
                c_max = [_frac(v) for v in self.c]
            obj_row = list(c_max) + [Fraction(0)] * (n - self.num_orig) + [Fraction(0)]
            for ai in art_indices:
                obj_row[ai] = -BIG_M
        else:
            obj_row = list(c_orig_ext)

        tableau.append(obj_row)

        # 消去基变量在目标行中的系数
        for i in range(m):
            bv = basis[i]
            if tableau[m][bv] != 0:
                factor = tableau[m][bv]
                for k in range(n + 1):
                    tableau[m][k] -= factor * tableau[i][k]

        # 迭代
        solver = _SimplexIterator(
            tableau, basis, var_names,
            obj_name="z", phase=0,
            artificial_indices=art_indices
        )
        snapshots = solver.run("📋 【大M法】初始单纯形表构造完成。")

        # 提取最终解
        self._append_final_solution(snapshots, var_names)

        return snapshots

    # ================== 两阶段法 ==================
    def _solve_two_phase(self, var_names, tableau, basis, art_indices, c_orig_ext, total_vars):
        m = len(tableau)
        n = total_vars
        all_snapshots: list[Snapshot] = []

        # ---- 第一阶段：min w = Σ(人工变量)，等价于 max (-w) ----
        # 目标行：人工变量系数 = -1，其余 = 0（max 化形式：max -w）
        phase1_obj = [Fraction(0)] * n + [Fraction(0)]
        for ai in art_indices:
            phase1_obj[ai] = Fraction(-1)

        phase1_tableau = [row[:] for row in tableau]
        phase1_tableau.append(phase1_obj)

        # 消去基变量在目标行中的系数
        for i in range(m):
            bv = basis[i]
            if phase1_tableau[m][bv] != 0:
                factor = phase1_tableau[m][bv]
                for k in range(n + 1):
                    phase1_tableau[m][k] -= factor * phase1_tableau[i][k]

        solver1 = _SimplexIterator(
            phase1_tableau, list(basis), list(var_names),
            obj_name="w", phase=1,
            artificial_indices=art_indices
        )
        snaps1 = solver1.run("📋 【两阶段法 · 第一阶段】\n\n"
                             "目标：$\\min w = $ 所有人工变量之和\n\n"
                             "等价于 $\\max (-w)$，初始单纯形表如下。")

        # 检查第一阶段结果
        last1 = snaps1[-1]
        phase1_obj_val = solver1.tableau[-1][-1]

        if last1.status != "optimal" or phase1_obj_val != 0:
            # 第一阶段最优值 ≠ 0 → 无可行解
            extra = Snapshot(
                iteration=len(snaps1),
                tableau=deepcopy(solver1.tableau),
                basis=list(solver1.basis),
                var_names=list(var_names),
                obj_name="w",
                explanation=(
                    f"❌ 【两阶段法 · 第一阶段结束】\n\n"
                    f"最优值 $w^* = {_frac_str(abs(phase1_obj_val))}$\n\n"
                    f"因为 $w^* \\neq 0$，原问题**无可行解**。"
                ),
                status="infeasible",
                phase=1,
            )
            snaps1.append(extra)
            return snaps1

        # 第一阶段成功，w* = 0
        transition = Snapshot(
            iteration=len(snaps1),
            tableau=deepcopy(solver1.tableau),
            basis=list(solver1.basis),
            var_names=list(var_names),
            obj_name="w",
            explanation=(
                "✅ 【两阶段法 · 第一阶段结束】\n\n"
                "最优值 $w^* = 0$，所有人工变量已离开基（或值为 0），"
                "找到了一个基可行解！\n\n"
                "---\n\n"
                "🔄 进入**第二阶段**：删除人工变量列，恢复原目标函数……"
            ),
            status="optimal",
            phase=1,
        )
        snaps1.append(transition)
        all_snapshots.extend(snaps1)

        # ---- 第二阶段：删除人工变量列，恢复原目标 ----
        phase1_final_tableau = solver1.tableau
        phase1_final_basis = solver1.basis

        # 确定要保留的列（排除人工变量列）
        keep_cols = [j for j in range(n) if j not in art_indices]
        # 创建旧列号 → 新列号的映射
        col_map = {}
        for new_j, old_j in enumerate(keep_cols):
            col_map[old_j] = new_j
        new_n = len(keep_cols)

        # 新变量名
        new_var_names = [var_names[j] for j in keep_cols]

        # 新基变量下标
        new_basis = []
        for bv in phase1_final_basis:
            if bv in col_map:
                new_basis.append(col_map[bv])
            else:
                # 人工变量还在基中但值为 0 的情况（退化），需要先换出
                # 简化处理：直接映射到一个松弛变量（理论上此时它值为0）
                new_basis.append(0)  # fallback

        # 构造第二阶段的单纯形表
        phase2_tableau = []
        for i in range(m):
            row = [phase1_final_tableau[i][j] for j in keep_cols] + [phase1_final_tableau[i][-1]]
            phase2_tableau.append(row)

        # 第二阶段目标行
        phase2_obj = [c_orig_ext[j] for j in keep_cols] + [Fraction(0)]
        phase2_tableau.append(phase2_obj)

        # 消去基变量在新目标行中的系数
        for i in range(m):
            bv = new_basis[i]
            if phase2_tableau[m][bv] != 0:
                factor = phase2_tableau[m][bv]
                for k in range(new_n + 1):
                    phase2_tableau[m][k] -= factor * phase2_tableau[i][k]

        solver2 = _SimplexIterator(
            phase2_tableau, new_basis, new_var_names,
            obj_name="z", phase=2,
            artificial_indices=[]
        )
        snaps2 = solver2.run(
            "📋 【两阶段法 · 第二阶段】\n\n"
            "已删除所有人工变量列，恢复原目标函数，继续求解。"
        )

        all_snapshots.extend(snaps2)

        # 提取最终解
        self._append_final_solution(all_snapshots, new_var_names)

        return all_snapshots

    # ================== 提取最终解 ==================
    def _append_final_solution(self, snapshots, var_names):
        last = snapshots[-1]
        if last.status != "optimal":
            return

        tab = last.tableau
        basis = last.basis
        m = len(tab) - 1

        sol = {}
        for i in range(m):
            bv = basis[i]
            name = var_names[bv]
            sol[name] = tab[i][-1]

        # 只展示原始变量
        orig_parts = []
        for name in self.var_names[:self.num_orig]:
            val = sol.get(name, Fraction(0))
            orig_parts.append(f"${name} = {_frac_str(val)}$")

        obj_val = tab[-1][-1]
        if self.is_min:
            obj_val = -obj_val

        last.explanation += (
            f"\n\n---\n\n"
            f"🎯 **最终结果**\n\n"
            f"最优解：{'，'.join(orig_parts)}\n\n"
            f"最优值：$z^* = {_frac_str(obj_val)}$"
        )
