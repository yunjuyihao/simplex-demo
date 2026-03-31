"""2D 可行域与迭代路径可视化模块"""

import numpy as np
import plotly.graph_objects as go
from itertools import combinations
from collections import defaultdict

def plot_feasible_region(A, b, constraint_types, snapshots, var_names, is_min):
    """绘制二维线性规划的可行域与单纯形法迭代路径"""
    
    # 提取所有迭代路径的坐标 (x1, x2)
    path_x, path_y = [], []
    for snap in snapshots:
        x1_val, x2_val = 0.0, 0.0
        for i, bv in enumerate(snap.basis):
            if bv == 0: x1_val = float(snap.tableau[i][-1])
            if bv == 1: x2_val = float(snap.tableau[i][-1])
        path_x.append(x1_val)
        path_y.append(x2_val)

    # ---------- 新增：合并相同坐标的步骤 ----------
    step_groups = defaultdict(list)
    for i, (px, py) in enumerate(zip(path_x, path_y)):
        # 保留4位小数作为字典的键，避免浮点误差导致无法合并
        coord = (round(px, 4), round(py, 4))
        step_groups[coord].append(i)
    # ----------------------------------------------

    # 1. 收集所有边界直线方程 (ax1 + bx2 = c)
    lines = []
    for i in range(len(b)):
        lines.append((float(A[i][0]), float(A[i][1]), float(b[i]), constraint_types[i]))
    
    lines.append((1.0, 0.0, 0.0, '>='))
    lines.append((0.0, 1.0, 0.0, '>='))
    
    bbox_size = max([10.0] + [px*1.5 for px in path_x] + [py*1.5 for py in path_y])
    lines.append((1.0, 0.0, bbox_size, '<='))
    lines.append((0.0, 1.0, bbox_size, '<='))

    # 2. 求所有直线的两两交点
    vertices = []
    eqs = [(L[0], L[1], L[2]) for L in lines]
    for (A1, B1, C1), (A2, B2, C2) in combinations(eqs, 2):
        det = A1 * B2 - A2 * B1
        if abs(det) > 1e-9: 
            x = (C1 * B2 - C2 * B1) / det
            y = (A1 * C2 - A2 * C1) / det
            vertices.append((x, y))

    # 3. 过滤出满足所有不等式的有效顶点
    feasible_vertices = []
    for x, y in vertices:
        if x < -1e-6 or y < -1e-6: 
            continue
        is_feasible = True
        for a1, a2, rhs, ctype in lines[:-2]:
            val = a1 * x + a2 * y
            if ctype == '<=' and val > rhs + 1e-6:
                is_feasible = False; break
            elif ctype == '>=' and val < rhs - 1e-6:
                is_feasible = False; break
            elif ctype == '=' and abs(val - rhs) > 1e-6:
                is_feasible = False; break
                
        if is_feasible:
            if not any(abs(x - fx) < 1e-5 and abs(y - fy) < 1e-5 for fx, fy in feasible_vertices):
                feasible_vertices.append((x, y))

    # 4. 组装 Plotly 图表
    fig = go.Figure()

    if feasible_vertices:
        cx = sum(v[0] for v in feasible_vertices) / len(feasible_vertices)
        cy = sum(v[1] for v in feasible_vertices) / len(feasible_vertices)
        feasible_vertices.sort(key=lambda v: np.arctan2(v[1] - cy, v[0] - cx))
        feasible_vertices.append(feasible_vertices[0])
        
        fx, fy = zip(*feasible_vertices)
        fig.add_trace(go.Scatter(
            x=fx, y=fy, fill='toself', mode='lines',
            name='可行域', fillcolor='rgba(0,176,246,0.3)',
            line=dict(color='rgba(0,176,246,1)', width=2)
        ))

    # 5. 绘制单纯形法的迭代路径
    fig.add_trace(go.Scatter(
        x=path_x, y=path_y, mode='lines+markers',
        name='单纯形法迭代路径',
        marker=dict(size=10, color='red', symbol='circle'),
        line=dict(width=3, color='red', dash='dot')
    ))

    # ---------- 修改：使用合并后的步骤进行标注，并添加背景色防遮挡 ----------
    for (px, py), steps in step_groups.items():
        step_str = ", ".join(map(str, steps))  # 例如 "0, 1"
        fig.add_annotation(
            x=px, y=py, text=f"Step {step_str}",
            showarrow=True, arrowhead=2, ax=20, ay=-30,
            font=dict(color="red", size=12),
            bgcolor="rgba(255, 255, 255, 0.7)"  # 白色半透明背景，阅读更清晰
        )
    # ------------------------------------------------------------------------

    # ---------- 修改：使用 HTML 下标代替 LaTeX ----------
    x_label = var_names[0].replace('_', '<sub>') + '</sub>'
    y_label = var_names[1].replace('_', '<sub>') + '</sub>'
    # ----------------------------------------------------

    fig.update_layout(
        title="📈 可行域与单纯形法搜索路径",
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_white",
        # 将 xanchor 改为 right，x 改为 0.99，并加上背景色防遮挡
        legend=dict(
            yanchor="top", y=0.99, 
            xanchor="right", x=0.99,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="rgba(0, 0, 0, 0.2)",
            borderwidth=1
        )
    )

    
    return fig
