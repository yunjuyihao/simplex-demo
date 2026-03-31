"""Streamlit 交互界面 —— 单纯形法教学演示系统（大M法 + 两阶段法）"""

import streamlit as st
from fractions import Fraction
from simplex_core import SimplexSolver
from utils import snapshot_to_latex_table, frac_display
from examples import EXAMPLES

# ========================================
#  页面配置
# ========================================
st.set_page_config(page_title="单纯形法教学演示", page_icon="📐", layout="wide")
st.title("📐 单纯形法教学演示系统")
st.caption("逐步演示单纯形法求解线性规划的完整过程 · 支持大M法 & 两阶段法")

# ========================================
#  侧边栏
# ========================================
with st.sidebar:
    st.header("📝 问题输入")

    input_mode = st.radio("输入方式", ["选择内置例题", "手动输入"])

    if input_mode == "选择内置例题":
        example_name = st.selectbox("选择例题", list(EXAMPLES.keys()))
        ex = EXAMPLES[example_name]
        st.markdown("**题目：**")
        st.markdown(ex["description"])
        c = ex["c"]
        A = ex["A"]
        b = ex["b"]
        types = ex["types"]
        is_min = ex["is_min"]
        num_vars = len(c)
        num_constraints = len(b)
        var_names = [f"x_{i+1}" for i in range(num_vars)]
    else:
        st.subheader("模型参数")
        is_min = st.checkbox("最小化问题（默认最大化）")
        num_vars = st.number_input("决策变量个数", min_value=1, max_value=10, value=2)
        num_constraints = st.number_input("约束条件个数", min_value=1, max_value=10, value=3)
        var_names = [f"x_{i+1}" for i in range(num_vars)]

        st.subheader("目标函数系数")
        c_cols = st.columns(num_vars)
        c = []
        for i in range(num_vars):
            with c_cols[i]:
                val = st.text_input(f"c_{i+1}", value="0", key=f"c_{i}")
                c.append(val)

        st.subheader("约束条件")
        A, b, types = [], [], []
        for i in range(num_constraints):
            st.markdown(f"**约束 {i+1}：**")
            cols = st.columns(num_vars + 2)
            row = []
            for j in range(num_vars):
                with cols[j]:
                    val = st.text_input(f"a_{i+1},{j+1}", value="0", key=f"a_{i}_{j}")
                    row.append(val)
            A.append(row)
            with cols[num_vars]:
                t = st.selectbox("类型", ["<=", ">=", "="], key=f"type_{i}")
                types.append(t)
            with cols[num_vars + 1]:
                bi = st.text_input(f"b_{i+1}", value="0", key=f"b_{i}")
                b.append(bi)

    st.divider()
    st.subheader("⚙️ 算法选择")

    # 判断是否需要人工变量
    needs_art = any(t in ('>=', '=') for t in types)

    if needs_art:
        method = st.radio(
            "处理人工变量的方法",
            ["big_m", "two_phase"],
            format_func=lambda x: {"big_m": "大M法", "two_phase": "两阶段法"}[x],
            help="当存在 ≥ 或 = 约束时，需要引入人工变量。可选择大M法或两阶段法来处理。"
        )
    else:
        method = "big_m"
        st.info("本题所有约束均为 ≤，无需人工变量，直接使用标准单纯形法。")

    run = st.button("🚀 开始求解", use_container_width=True)


# ========================================
#  解析与求解
# ========================================
def parse_value(v):
    v = str(v).strip()
    if '/' in v:
        parts = v.split('/')
        return Fraction(int(parts[0]), int(parts[1]))
    return Fraction(v)


if run:
    try:
        c_parsed = [parse_value(v) for v in c]
        A_parsed = [[parse_value(v) for v in row] for row in A]
        b_parsed = [parse_value(v) for v in b]
    except Exception as e:
        st.error(f"输入解析失败：{e}")
        st.stop()

    # 缓存模型参数
    st.session_state["model_params"] = {
        "A": A_parsed, "b": b_parsed, "types": types,
        "is_min": is_min, "var_names": var_names, "num_vars": num_vars,
    }

    # 显示原始模型
    with st.expander("📄 原始模型", expanded=True):
        obj_type = "\\min" if is_min else "\\max"
        terms = []
        for i in range(num_vars):
            coeff = c_parsed[i]
            name = var_names[i]
            if coeff == 0:
                continue
            if coeff == 1:
                terms.append(name)
            elif coeff == -1:
                terms.append(f"-{name}")
            else:
                terms.append(f"{coeff}{name}")
        obj_expr = " + ".join(terms).replace("+ -", "- ")
        st.latex(f"{obj_type} \\quad z = {obj_expr}")

        sym_map = {"<=": "\\leq", ">=": "\\geq", "=": "="}
        for i in range(num_constraints):
            lhs_terms = []
            for j in range(num_vars):
                coeff = A_parsed[i][j]
                name = var_names[j]
                if coeff == 0:
                    continue
                if coeff == 1:
                    lhs_terms.append(name)
                elif coeff == -1:
                    lhs_terms.append(f"-{name}")
                else:
                    lhs_terms.append(f"{coeff}{name}")
            lhs = " + ".join(lhs_terms).replace("+ -", "- ")
            st.latex(f"{lhs} {sym_map[types[i]]} {b_parsed[i]}")
        st.latex(f"{', '.join(var_names)} \\geq 0")

        method_name = {"big_m": "大M法", "two_phase": "两阶段法"}
        if needs_art:
            st.info(f"🔧 本题含 $\\geq$ 或 $=$ 约束，使用 **{method_name[method]}** 处理人工变量。")

    # 求解
    solver = SimplexSolver(c_parsed, A_parsed, b_parsed, types, is_min, var_names, method=method)
    snapshots = solver.solve()

    st.session_state["snapshots"] = snapshots
    st.session_state["current_step"] = 0

# ========================================
#  逐步展示
# ========================================
if "snapshots" in st.session_state:
    snapshots = st.session_state["snapshots"]
    total_steps = len(snapshots)

    st.divider()
    st.subheader("🔄 逐步演示")

    # 步骤控制按钮
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        if st.button("⏮ 第一步"):
            st.session_state["current_step"] = 0
    with col2:
        if st.button("◀ 上一步"):
            st.session_state["current_step"] = max(0, st.session_state["current_step"] - 1)
    with col3:
        if st.button("下一步 ▶"):
            st.session_state["current_step"] = min(total_steps - 1, st.session_state["current_step"] + 1)
    with col4:
        if st.button("最后一步 ⏭"):
            st.session_state["current_step"] = total_steps - 1

    step = st.slider(
        "当前步骤", 0, total_steps - 1,
        st.session_state["current_step"], key="step_slider",
    )
    st.session_state["current_step"] = step
    snap = snapshots[step]

    # 阶段 + 状态指示
    phase_map = {0: "", 1: "第一阶段 · ", 2: "第二阶段 · "}
    status_map = {
        "ongoing": "🔄 迭代中",
        "optimal": "✅ 已达最优",
        "unbounded": "⚠️ 无界解",
        "infeasible": "❌ 无可行解",
    }
    phase_str = phase_map.get(snap.phase, "")
    status_str = status_map.get(snap.status, "")
    st.info(f"**步骤 {step}/{total_steps - 1}** — {phase_str}{status_str}")

    # 教学说明
    st.markdown("### 📖 说明")
    st.markdown(snap.explanation)

    # 单纯形表
    st.markdown("### 📊 单纯形表")
    st.markdown(snapshot_to_latex_table(snap, highlight=(snap.pivot_col >= 0)))

    if snap.pivot_col >= 0:
        st.caption("🔴 = 主元 &nbsp;&nbsp; 🔵 = 入基列 &nbsp;&nbsp; 🟢 = 出基行")

    # θ 比值
    if snap.theta:
        st.markdown("### 📏 θ 比值")
        m = len(snap.tableau) - 1
        for i in range(m):
            bv_name = snap.var_names[snap.basis[i]]
            if i < len(snap.theta) and snap.theta[i] is not None:
                marker = " ← **最小**" if i == snap.pivot_row else ""
                st.markdown(
                    f"- 第 {i+1} 行（${bv_name}$）：$\\theta = {frac_display(snap.theta[i])}${marker}"
                )
            else:
                st.markdown(
                    f"- 第 {i+1} 行（${bv_name}$）：$\\theta$ = — （系数 $\\leq 0$）"
                )

    # 2D 可行域图
    if "model_params" in st.session_state:
        params = st.session_state["model_params"]
        if params["num_vars"] == 2:
            st.markdown("### 📈 几何视角（可行域与路径）")
            try:
                from plot_2d import plot_feasible_region
                fig = plot_feasible_region(
                    params["A"], params["b"], params["types"],
                    snapshots, params["var_names"], params["is_min"]
                )
                st.plotly_chart(fig, use_container_width=True)
                st.info(
                    "💡 **教学提示**：单纯形法的本质是在可行域的**顶点**间移动。"
                    "红色虚线展示了算法从初始基可行解出发，沿多边形边缘走到最优顶点的路径。"
                )
            except Exception as e:
                st.warning(f"绘图时出现问题：{e}")

    # 全部步骤折叠面板
    with st.expander("📋 查看所有迭代（完整记录）"):
        for i, s in enumerate(snapshots):
            phase_tag = ""
            if s.phase == 1:
                phase_tag = "🔷 第一阶段 · "
            elif s.phase == 2:
                phase_tag = "🔶 第二阶段 · "
            st.markdown(f"---\n#### {phase_tag}步骤 {i}")
            st.markdown(s.explanation)
            st.markdown(snapshot_to_latex_table(s, highlight=False))
