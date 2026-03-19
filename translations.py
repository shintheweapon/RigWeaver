"""
RigWeaver — UI translations.

Add new locales by extending the _ZH_HANS dict below and registering the
locale code in `translations_dict`.
"""

_ZH_HANS: dict[tuple[str, str], str] = {
    # --- Panel & section headers ---
    ("*", "RigWeaver"):                 "RigWeaver",
    ("*", "Extract Used Armature"):     "提取使用中的骨架",
    ("*", "Generate Mesh"):             "生成网格",
    ("*", "Vertex Group Select"):       "顶点组选择",

    # --- Mode-gate buttons ---
    ("*", "Requires Object Mode"):      "需要物体模式",
    ("*", "Enter Object Mode"):         "切换至物体模式",
    ("*", "Requires Pose Mode"):        "需要姿态模式",
    ("*", "Enter Pose Mode"):           "切换至姿态模式",

    # --- VG panel UI ---
    ("*", "Previewing mixed weights"):  "正在预览混合权重",
    ("*", "Exit Preview"):              "退出预览",
    ("*", "Mix into Group"):            "混合至组",
    ("*", "No vertex groups"):          "无顶点组",
    ("*", "All"):                       "全选",
    ("*", "None"):                      "全不选",
    ("*", "Mix Checked Groups"):        "混合已勾选组",
    ("*", "Preview Mix"):               "预览混合",
    ("*", "Target"):                    "目标",

    # --- Operator labels ---
    ("*", "Generate Bone Mesh"):        "生成骨骼网格",
    ("*", "Update Mesh"):               "更新网格",
    ("*", "Preview Weight Radius"):     "预览权重半径",
    ("*", "Toggle Vertex Group"):       "切换顶点组",

    # --- Extract properties ---
    ("*", "Retarget Meshes"):           "重定向网格",
    ("*", "Auto Bone Orientation"):     "自动骨骼朝向",
    ("*", "Connect Child Bones"):       "连接子骨骼",
    ("*", "Separate Objects"):          "分离为单独对象",
    ("*", "Triangulate"):               "三角化",
    ("*", "Output Name"):               "输出名称",

    # --- Mesh gen properties ---
    ("*", "Mode"):                      "模式",
    ("*", "Column Resolution"):         "列分辨率",
    ("*", "Row Resolution"):            "行分辨率",
    ("*", "Ribbon Width"):              "带状宽度",
    ("*", "Gap Factor"):                "间隙系数",
    ("*", "Bridge Filter"):             "桥接过滤器",
    ("*", "Weight Radius"):             "权重半径",
    ("*", "Auto-Rig"):                  "自动绑定",
    ("*", "Generate UVs"):              "生成UV",
    ("*", "Subdivision Surface"):       "细分曲面",
    ("*", "Levels"):                    "级别",

    # --- VG select properties ---
    ("*", "Group Name"):                "组名",
    ("*", "Blend Mode"):                "混合模式",
    ("*", "Target Group"):              "目标组",
    ("*", "Remove Source Groups"):      "删除源组",

    # --- mesh_mode enum ---
    ("*", "Individual Strips"):         "独立带状",
    ("*", "Connected Surface"):         "连接曲面",
    ("*", "Connected Loop"):            "封闭环形曲面",
    ("*", "Auto-Split Surface"):        "自动分割曲面",
    ("*", "Tree Surface"):              "树状曲面",

    # --- vg blend mode enum ---
    ("*", "Max"):                       "最大值",
    ("*", "Average"):                   "平均值",
    ("*", "Add"):                       "叠加",
    ("*", "Min"):                       "最小值",
}

# zh_HANS is the BCP-47 / CLDR tag; zh_CN is the legacy Blender locale name.
# Both map to the same dictionary so either setting works.
translations_dict: dict[str, dict] = {
    "zh_CN":   _ZH_HANS,
    "zh_HANS": _ZH_HANS,
}
