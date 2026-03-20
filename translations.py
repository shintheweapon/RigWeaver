"""
RigWeaver — UI translations.

Add new locales by extending the _ZH_HANS dict below and registering the
locale code in `translations_dict`.
"""

_ZH_HANS: dict[tuple[str, str], str] = {
    # --- Panel & section headers ---
    ("*", "RigWeaver"):                 "RigWeaver",
    ("*", "Extract Deforming Bones"):     "提取形变骨骼",
    ("*", "Generate Mesh"):             "生成网格",
    ("*", "Generate Rig from Mesh"):    "从网格生成绑定",
    ("*", "Vertex Group Select"):       "顶点组选择",

    # --- Mode-gate buttons ---
    ("*", "Requires Object Mode"):      "需要物体模式",
    ("*", "Enter Object Mode"):         "切换至物体模式",
    ("*", "Requires Pose Mode"):        "需要姿态模式",
    ("*", "Enter Pose Mode"):           "切换至姿态模式",

    # --- VG panel UI ---
    ("*", "Previewing mixed weights"):  "正在预览权重混合",
    ("*", "Exit Preview"):              "退出预览",
    ("*", "Mix into Group"):            "混合到组",
    ("*", "No vertex groups"):          "无顶点组",
    ("*", "All"):                       "全选",
    ("*", "None"):                      "全不选",
    ("*", "Mix Checked Groups"):        "混合勾选组",
    ("*", "Preview Mix"):               "预览混合",
    ("*", "Target"):                    "目标",

    # --- Operator labels ---
    ("*", "Generate Proxy Mesh"):       "生成代理网格",
    ("*", "Preview Mesh"):              "预览网格",
    ("*", "Preview"):                   "预览",
    ("*", "Discard Preview"):           "丢弃预览",
    ("*", "Update Mesh"):               "更新网格",
    ("*", "Preview Envelop Weight Radius"):     "预览封套权重半径",
    ("*", "Toggle Vertex Group"):       "切换顶点组",
    ("*", "Generate Rig"):              "生成绑定",
    ("*", "Generate Rig from Mesh"):    "从网格生成绑定",
    ("*", "Preview Rig"):               "预览绑定",
    ("*", "Update Rig"):                "更新绑定",
    ("*", "Set as Parent"):             "设为父级",
    ("*", "AUTO requires NumPy"):       "自动模式需要 NumPy",

    # --- Extract properties ---
    ("*", "Retarget Meshes"):           "重定向网格绑定",
    ("*", "Auto Bone Orientation"):     "自动骨骼朝向",
    ("*", "Connect Child Bones"):       "连接子骨骼",
    ("*", "Separate Objects"):          "分离为单独对象",
    ("*", "Triangulate Face"):               "三角化面",
    ("*", "Output Name"):               "输出名称",

    # --- Mesh gen properties ---
    ("*", "Mode"):                      "模式",
    ("*", "Longitudinal (Along Chain)"): "纵向（沿骨骼链）",
    ("*", "Lateral (Between Chains)"):   "横向（链间）",
    ("*", "Lateral Columns"):            "横向列数",
    ("*", "Longitudinal Subdivisions"):  "纵向细分",
    ("*", "Longitudinal Interpolation"): "纵向插值",
    ("*", "Lateral Interpolation"):      "横向插值",
    ("*", "Linear"):                    "线性",
    ("*", "Catmull-Rom"):               "Catmull-Rom 样条",
    ("*", "Natural Cubic"):             "自然三次样条",
    ("*", "Straight lines between bone midpoints along the chain"):
        "骨骼链上各骨骼中点间以直线连接",
    ("*", "C1 Smooth spline through bone midpoints, removes angular kinks "
     "where bones meet"):
        "通过骨骼中点的 C1 平滑样条，消除骨骼连接处的折角",
    ("*", "C2 smooth spline through chain midpoints, smoothest longitudinal profile"):
        "通过骨骼链中点的 C2 平滑样条，提供最平滑的纵向轮廓",
    ("*", "Straight lines between adjacent chain columns, flat-sided panels"):
        "相邻骨骼链间直线连接，生成平面面板",
    ("*", "C1 smooth spline through all chain positions, curved cross-section "
     "silhouette with continuous tangents"):
        "通过所有骨骼链位置的 C1 平滑样条，截面轮廓曲线且切线连续",
    ("*", "C2 smooth spline, curvature is also continuous at every chain; "
     "the mathematically smoothest possible cross-section curve"):
        "C2 平滑样条，各骨骼链位置曲率连续，数学意义上的最平滑截面曲线",
    ("*", "Lateral Strength"):          "横向强度",
    ("*", "Blend between straight (Linear) and curved (spline) surface profile. "
          "0 = fully straight, 1 = full spline curvature."):
        "表面轮廓在直线（线性）与曲线（样条）之间的混合程度。0 = 完全直线，1 = 完整样条曲率。",
    ("*", "Ribbon Width"):              "带状宽度",
    ("*", "Gap Factor"):                "间隙系数",
    ("*", "Bridge Filter"):             "桥接过滤",
    ("*", "Weight Radius"):             "权重半径",
    ("*", "Auto-Rig"):                  "自动绑定",
    ("*", "Generate UVs"):              "生成UV",
    ("*", "Subdivision Surface"):       "细分曲面",
    ("*", "Levels"):                    "级别",

    # --- Rig from Mesh properties ---
    ("*", "Chains"):                    "骨骼链数量",
    ("*", "Bones per Chain"):           "每链骨骼数",
    ("*", "Up Axis"):                   "上方朝向轴",
    ("*", "Assign Weights"):            "分配权重",
    ("*", "Auto"):                      "自动",

    # --- VG select properties ---
    ("*", "Group Name"):                "组名",
    ("*", "Blend Mode"):                "混合模式",
    ("*", "Target Group"):              "目标组",
    ("*", "Remove Source Groups❗"):      "删除源组❗",

    # --- mesh_mode enum ---
    ("*", "Individual Strips (hair)"):         "独立条带（头发）",
    ("*", "Connected Surface (plane)"):         "连接曲面（平面式）",
    ("*", "Connected Loop (skirt)"):            "封闭环形曲面（裙子）",
    ("*", "Auto-Split Surface (box pleats)"):        "自动分割曲面（箱型褶皱）",
    ("*", "Tree Surface (non-uniform chain layout)"):              "树状曲面（非均匀骨骼链布局）",

    # --- vg blend mode enum ---
    ("*", "Max"):                       "最大值",
    ("*", "Average"):                   "平均值",
    ("*", "Add"):                       "叠加",
    ("*", "Min"):                       "最小值",

    # -----------------------------------------------------------------------
    # Tooltips, operator bl_description
    # -----------------------------------------------------------------------
    ("*", "Build a reduced armature from bones that actually deform meshes. "
          "Optionally retarget mesh Armature modifiers to the new armature."):
        "从实际参与网格变形的骨骼中构建精简骨架，并可将网格的骨架修改器重定向至新骨架。",

    ("*", "Create a surface mesh from the selected bone chains in Pose Mode. "
          "Single chain produces a ribbon; multiple chains produce a connected "
          "cross-section surface. Intended as a low-poly simulation cage."):
        "在姿态模式下从选中的骨骼链生成曲面网格。单条骨骼链生成条带状网格，多条骨骼链则生成连接的截面曲面，适合用作低面数的模拟用网格笼。",

    ("*", "RigWeaver: Natural Cubic interpolation requires NumPy, not available in this Blender build."):
        "RigWeaver：自然三次样条插值依赖 NumPy，但当前 Blender 版本未提供该模块。",

    ("*", "Regenerate geometry of existing proxy mesh object(s) from this armature "
          "using current settings and selected bones, preserving modifiers and transforms"):
        "使用当前设置和选中的骨骼，重新生成现有代理网格对象的几何体，并保留修改器和变换。",

    ("*", "Toggle a wireframe overlay in the viewport showing the weight radius "
          "used for bone weight assignment. Radius = bone length × Weight Radius"):
        "在视口中切换线框叠加层，显示骨骼权重分配半径。半径 = 骨骼长度 × 权重半径",

    ("*", "Toggle this vertex group in/out of the active selection set"):
        "将此顶点组移入选集或移出",

    ("*", "Select vertices in all vertex groups"):   "选中所有顶点组",
    ("*", "Deselect all vertex groups"):             "取消全选",

    ("*", "Toggle a live Weight Paint preview of the blended vertex group weights"):
        "开关混合顶点组权重的实时权重绘制预览",

    ("*", "Merge checked vertex groups into a single target group"):
        "将勾选的顶点组合并至同一目标组",

    # -----------------------------------------------------------------------
    # Tooltips, property descriptions
    # -----------------------------------------------------------------------
    ("*", "Update Armature modifiers on connected meshes to point to the new "
          "reduced armature instead of the original"):
        "更新关联网格上的骨架修改器，使其指向新的精简骨架而非原始骨架",

    ("*", "Recalculate bone rolls on the reduced armature so the local Z axis "
          "aligns with global +Z (same as FBX import 'Automatic Bone Orientation')"):
        "重新计算精简骨架上的骨骼滚动角，使局部 Z 轴与全局 +Z 对齐（与 FBX 导入的“自动骨骼朝向”同效）",

    ("*", "Snap every child bone's head to its parent's tail in the reduced "
          "armature, forming a continuous connected chain regardless of whether "
          "intermediate bones were skipped"):
        "将精简骨架中每块子骨骼的头部吸附至父骨骼的尾部，无论是否跳过了中间骨骼，都会形成连续的骨骼链",

    ("*", "Create one mesh object per chain instead of merging all ribbons into "
          "a single object (only active when Individual Chains is on)"):
        "为每条骨骼链单独创建网格对象，而非合并为单一网格（仅在“独立条带”模式下生效）",

    ("*", "Convert all quad faces to triangles in the generated mesh"):
        "将生成网格中的所有四边面转换为三角面",

    ("*", "Quad columns per panel in the lateral direction (between adjacent "
          "chains). 1 = single column."):
        "每个面板横向（相邻骨骼链之间）的四边形列数，1 = 单列",

    ("*", "Subdivisions per bone segment in the longitudinal direction (along "
          "the chain). 1 = one row per bone, 2+ = interpolated rows within "
          "each segment."):
        "每段骨骼纵向（沿骨骼链方向）的细分数，1 = 每段一行，2 及以上 = 段内插值多行",

    ("*", "Curve shape used between bone midpoints along each chain (longitudinal direction). "
     "Has no effect when Longitudinal Subdivisions is 1."):
        "沿每条骨骼链在骨骼中点之间使用的曲线形状（纵向）。当纵向细分为 1 时无效果。",

    ("*", "Curve shape used between adjacent chains (lateral direction; "
     "controls cross-section profile)."):
        "在相邻骨骼链之间使用的曲线形状（横向；控制截面轮廓）。",

    ("*", "Width of the ribbon mesh generated from a single bone chain"):
        "单条骨骼链生成的带状网格宽度",

    ("*", "A gap larger than this multiple of the median inter-chain distance "
          "is treated as a strip boundary"):
        "相邻骨骼链间距超过中位链间距的此倍数时，视为条带分界",

    ("*", "Circumradius threshold as a multiple of the median edge length. "
          "Higher values keep more triangles; lower values prune long bridging edges."):
        "外接圆半径阈值，以中位边长的倍数表示。值越大保留三角面越多，值越小则裁剪较长桥接边。",

    ("*", "Radius of each bone's weight influence as a multiple of the bone's "
          "length. Vertices outside all influence zones fall back to the nearest bone."):
        "每块骨骼权重影响范围的半径，以骨骼长度的倍数表示。超出所有影响范围的顶点将归属至最近骨骼。",

    ("*", "Create one vertex group per bone (inverse-distance weights) and add "
          "an Armature modifier pointing to the source armature, making the "
          "generated mesh immediately deform-ready."):
        "为每块骨骼创建顶点组（距离反比权重），并添加指向源骨架的骨架修改器，使生成网格可立即用于变形。",

    ("*", "Create a UV Map for the generated mesh"):
        "为生成网格创建 UV 贴图。",

    ("*", "Add a Subdivision Surface modifier to the generated mesh"):
        "为生成网格添加表面细分修改器",

    ("*", "Viewport subdivision levels (1 = light smooth, 2–3 = heavier)"):
        "视图细分级别（1 = 轻度平滑，2–3 = 强度较高）",

    ("*", "Base name for generated mesh object(s). In Separate Objects mode "
          "this becomes a prefix: OutputName_BoneName"):
        "生成网格对象的基础名称。在“分离对象”模式下，该名称将作为前缀使用，实际名称为：基础名_骨骼名（下划线自动添加）",

    ("*", "Whether the viewport envelope radius overlay is currently displayed"):
        "控制是否在视口中显示权重半径叠加层",

    ("*", "Name of the vertex group to toggle"):    "要切换的顶点组的名称",

    ("*", "JSON list of vertex group names active in the RigWeaver selector"):
        "RigWeaver 选择器中当前活跃顶点组名称的 JSON 列表",

    ("*", "How to combine weights from multiple groups"): "多组权重的合并方式",
    ("*", "Name for the new merged vertex group"):        "新合并顶点组的名称",

    ("*", "Delete the checked source groups after mixing"):
        "混合后删除已勾选的源顶点组",

    ("*", "Whether the mix preview is currently displayed"): "当前是否显示混合预览",
    ("*", "Active index for vertex group UIList"):           "当前活跃顶点组列表的索引",

    # -----------------------------------------------------------------------
    # Tooltips, enum item descriptions
    # -----------------------------------------------------------------------
    ("*", "One ribbon per chain (hair, fur, loose strands)"):
        "每条骨骼链生成一条带状网格（适合头发、毛发、离散链条）",

    ("*", "Panels between sorted adjacent chains (flat panels, even chain spacing)"):
        "在排序后的相邻骨骼链之间生成面板（适合均匀间距的非闭合布局）",

    ("*", "Closed surface, last chain connects back to first (skirts, rings, cylinders)"):
        "封闭曲面，末端骨骼链与首端相连（适合裙子、环形、圆柱体）",

    ("*", "Connected surface with automatic gap detection "
          "(inner/outer loop layouts, box pleats)"):
        "带自动间隙检测的连接曲面（适合内外双层布局、箱型褶皱）",

    ("*", "Sample-point triangulation for branching or irregular layouts (capes, fans)"):
        "基于采样点的三角剖分，适用于分支或不规则布局（如披风、扇形等非均匀骨骼链结构）",

    ("*", "Strongest weight wins"):      "取最大权重",
    ("*", "Mean of all weights"):        "取所有权重的平均值",
    ("*", "Sum, clamped to 1.0"):        "权重叠加，上限为 1.0",
    ("*", "Weakest weight wins"):        "取最小权重",

    # -----------------------------------------------------------------------
    # Tooltips, Generate Rig from Mesh
    # -----------------------------------------------------------------------
    ("*", "Toggle a viewport overlay showing where the generated bones will be "
          "placed. Updates live as Chains, Bones per Chain, and Up Axis change."):
        "开关视图叠加层，预览骨骼的生成位置。会根据骨骼链数量、每链骨骼数和上朝向轴而实时更新。",

    ("*", "Generate a bone cage armature from the active mesh using cylindrical "
          "decomposition. Bones radiate around the mesh's up axis from top to bottom."):
        "使用圆柱分解法从当前激活的网格生成笼状骨架，骨骼按网格上朝向轴从顶到底进行辐射性分布。",

    ("*", "Regenerate the existing bone cage armature in-place using the current "
          "settings, preserving the Armature modifier on the source mesh."):
        "使用当前设置原地更新现有笼状骨架，保留源网格上的骨架修改器。",

    ("*", "Parent the mesh to the generated armature so it follows it in "
          "the outliner hierarchy. World transform is preserved."):
        "将网格设为生成骨架的子对象，使其在大纲层级中跟随骨架，并保持世界变换不变。",

    ("*", "Number of radial bone chains distributed around the mesh"):
        "沿网格分布的放射状骨骼链的数量",

    ("*", "Number of bones per chain (height subdivisions from top to bottom)"):
        "每条骨骼链的骨骼数量（由顶到底的细分数）",

    ("*", "Axis that points from the bottom to the top of the garment. "
          "AUTO detects the principal axis via PCA (requires NumPy)."):
        "从服装底部指向顶部的轴向。AUTO 模式通过 PCA 自动检测主轴（需要 NumPy）。",

    ("*", "Create one vertex group per bone and add an Armature modifier "
          "to the source mesh, making it immediately deform-ready."):
        "为每块骨骼创建顶点组，并向源网格添加骨架修改器，使其可立即用于变形。",

    ("*", "Radius of each bone's weight influence as a multiple of the bone's length. "
          "Vertices outside all zones fall back to the nearest bone."):
        "每块骨骼权重影响范围的半径，以骨骼长度的倍数表示。不从属于任何范围的顶点将被分配至最近的骨骼。",

    ("*", "Base name for the generated armature object and its bones"):
        "生成的骨架对象及其骨骼的词干名称",

    ("*", "Detect automatically via PCA (requires NumPy)"):
        "通过 PCA 自动检测（需要 NumPy）",
}
