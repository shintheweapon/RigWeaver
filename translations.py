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
    ("*", "Generate Rig from Mesh"):    "从网格生成骨骼绑定",
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
    ("*", "Generate Proxy Mesh"):       "生成代理网格",
    ("*", "Update Mesh"):               "更新网格",
    ("*", "Preview Weight Radius"):     "预览权重半径",
    ("*", "Toggle Vertex Group"):       "切换顶点组",
    ("*", "Generate Rig"):              "生成骨骼绑定",
    ("*", "Generate Rig from Mesh"):    "从网格生成骨骼绑定",
    ("*", "Preview Rig"):               "预览骨骼绑定",
    ("*", "Update Rig"):                "更新骨骼绑定",
    ("*", "Set as Parent"):             "设为父级",
    ("*", "AUTO requires NumPy"):       "AUTO 模式需要 NumPy",

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
    ("*", "Row Interpolation"):         "行插值",
    ("*", "Lateral Interpolation"):     "横向插值",
    ("*", "Linear"):                    "线性",
    ("*", "Catmull-Rom"):               "Catmull-Rom 样条",
    ("*", "Straight lines between bone midpoints"):
        "骨骼中点间直线插值",
    ("*", "Smooth spline through bone midpoints — eliminates angular kinks at bone junctions"):
        "通过骨骼中点的平滑样条——消除骨骼连接处的折角",
    ("*", "Straight blend between adjacent chain columns"):
        "相邻骨骼链列之间的直线混合",
    ("*", "Smooth spline through chain positions — genuinely curves the cross-section "
         "profile for rounder silhouettes"):
        "通过骨骼链位置的平滑样条——真正弯曲截面轮廓，使截面更圆滑",
    ("*", "Lateral Strength"):          "横向强度",
    ("*", "How strongly the Catmull-Rom spline curves the cross-section. "
          "0 = straight (same as Linear), 1 = full spline curvature."):
        "Catmull-Rom 样条弯曲截面的强度。0 = 直线（与线性相同），1 = 完整样条曲率。",
    ("*", "Ribbon Width"):              "带状宽度",
    ("*", "Gap Factor"):                "间隙系数",
    ("*", "Bridge Filter"):             "桥接过滤器",
    ("*", "Weight Radius"):             "权重半径",
    ("*", "Auto-Rig"):                  "自动绑定",
    ("*", "Generate UVs"):              "生成UV",
    ("*", "Subdivision Surface"):       "细分曲面",
    ("*", "Levels"):                    "级别",

    # --- Rig from Mesh properties ---
    ("*", "Chains"):                    "骨骼链数量",
    ("*", "Bones per Chain"):           "每链骨骼数",
    ("*", "Up Axis"):                   "朝上轴向",
    ("*", "Assign Weights"):            "分配权重",
    ("*", "Auto"):                      "自动",

    # --- VG select properties ---
    ("*", "Group Name"):                "组名",
    ("*", "Blend Mode"):                "混合模式",
    ("*", "Target Group"):              "目标组",
    ("*", "Remove Source Groups"):      "删除源组",

    # --- mesh_mode enum ---
    ("*", "Individual Strips"):         "独立条带",
    ("*", "Connected Surface"):         "连接曲面",
    ("*", "Connected Loop"):            "封闭环形曲面",
    ("*", "Auto-Split Surface"):        "自动分割曲面",
    ("*", "Tree Surface"):              "树状曲面",

    # --- vg blend mode enum ---
    ("*", "Max"):                       "最大值",
    ("*", "Average"):                   "平均值",
    ("*", "Add"):                       "叠加",
    ("*", "Min"):                       "最小值",

    # -----------------------------------------------------------------------
    # Tooltips — operator bl_description
    # -----------------------------------------------------------------------
    ("*", "Build a reduced armature from bones that actually deform meshes. "
          "Optionally retarget mesh Armature modifiers to the new armature."):
    "从实际驱动网格变形的骨骼中构建精简骨架，"
    "并可选择将网格的骨架修改器重定向至新骨架。",

    ("*", "Create a surface mesh from the selected bone chains in Pose Mode. "
          "Single chain produces a ribbon; multiple chains produce a connected "
          "cross-section surface. Intended as a low-poly simulation cage."):
    "在姿态模式下从选中的骨骼链生成曲面网格。"
    "单条骨骼链生成带状网格，多条生成连接的横截面曲面，"
    "适合用作低面数模拟笼。",

    ("*", "Regenerate geometry of existing proxy mesh object(s) from this armature "
          "using current settings and selected bones, preserving modifiers and transforms"):
    "使用当前设置和选中骨骼重新生成此骨架对应的现有代理网格对象，"
    "保留修改器和变换。",

    ("*", "Toggle a wireframe overlay in the viewport showing the weight radius "
          "used for bone weight assignment. Radius = bone length × Weight Radius"):
    "在视图中切换线框叠加层，显示用于骨骼权重分配的权重半径。"
    "半径 = 骨骼长度 × 权重半径",

    ("*", "Toggle this vertex group in/out of the active selection set"):
        "切换此顶点组在当前选择集中的选中状态",

    ("*", "Select vertices in all vertex groups"):   "选中所有顶点组",
    ("*", "Deselect all vertex groups"):             "取消选中所有顶点组",

    ("*", "Toggle a live Weight Paint preview of the blended vertex group weights"):
        "切换混合顶点组权重的实时权重绘制预览",

    ("*", "Merge checked vertex groups into a single target group"):
        "将已勾选的顶点组合并至单一目标组",

    # -----------------------------------------------------------------------
    # Tooltips — property descriptions
    # -----------------------------------------------------------------------
    ("*", "Update Armature modifiers on connected meshes to point to the new "
          "reduced armature instead of the original"):
        "更新关联网格上的骨架修改器，使其指向新的精简骨架而非原始骨架",

    ("*", "Recalculate bone rolls on the reduced armature so the local Z axis "
          "aligns with global +Z (same as FBX import 'Automatic Bone Orientation')"):
        "重新计算精简骨架上的骨骼滚动角，使局部Z轴与全局+Z对齐"
        '（与FBX导入"自动骨骼朝向"一致）',

    ("*", "Snap every child bone's head to its parent's tail in the reduced "
          "armature, forming a continuous connected chain regardless of whether "
          "intermediate bones were skipped"):
        "将精简骨架中每块子骨骼的头部吸附至父骨骼的尾部，"
        "无论是否跳过了中间骨骼，均形成连续骨骼链",

    ("*", "Create one mesh object per chain instead of merging all ribbons into "
          "a single object (only active when Individual Chains is on)"):
        "为每条骨骼链创建独立网格对象，而非合并为一个"
        '（仅在"独立条带"模式下有效）',

    ("*", "Convert all quad faces to triangles in the generated mesh"):
        "将生成网格中的所有四边面转换为三角面",

    ("*", "Quad columns per panel in the lateral direction (between adjacent "
          "chains). 1 = single column."):
        "每个面板横向（相邻骨骼链之间）的四边形列数，1 = 单列",

    ("*", "Subdivisions per bone segment in the longitudinal direction (along "
          "the chain). 1 = one row per bone, 2+ = interpolated rows within "
          "each segment."):
        "每段骨骼纵向（沿骨骼链方向）的细分数，"
        "1 = 每段一行，2及以上 = 段内插值多行",

    ("*", "Width of the ribbon mesh generated from a single bone chain"):
        "单条骨骼链生成的带状网格宽度",

    ("*", "A gap larger than this multiple of the median inter-chain distance "
          "is treated as a strip boundary"):
        "相邻骨骼链间距超过中位链间距的此倍数时，视为条带分界",

    ("*", "Circumradius threshold as a multiple of the median edge length. "
          "Higher values keep more triangles; lower values prune long bridging edges."):
        "外接圆半径阈值，以中位边长的倍数表示。"
        "值越大保留三角面越多，值越小则裁剪较长桥接边。",

    ("*", "Radius of each bone's weight influence as a multiple of the bone's "
          "length. Vertices outside all influence zones fall back to the nearest bone."):
        "每块骨骼权重影响范围的半径，以骨骼长度的倍数表示。"
        "超出所有影响范围的顶点将归属至最近骨骼。",

    ("*", "Create one vertex group per bone (inverse-distance weights) and add "
          "an Armature modifier pointing to the source armature, making the "
          "generated mesh immediately deform-ready."):
        "为每块骨骼创建顶点组（距离反比权重），并添加指向源骨架的骨架修改器，"
        "使生成网格可立即用于变形。",

    ("*", "Create a UVMap layer on the generated mesh (U=lateral, V=longitudinal)"):
        "在生成网格上创建UV贴图层（U=横向，V=纵向）",

    ("*", "Add a Subdivision Surface modifier to the generated mesh"):
        "为生成网格添加细分曲面修改器",

    ("*", "Viewport subdivision levels (1 = light smooth, 2–3 = heavier)"):
        "视图细分级别（1 = 轻度平滑，2-3 = 较重）",

    ("*", "Base name for generated mesh object(s). In Separate Objects mode "
          "this becomes a prefix: OutputName_BoneName"):
        '生成网格对象的基础名称。在"分离对象"模式下用作前缀：输出名称_骨骼名称',

    ("*", "Whether the viewport envelope radius overlay is currently displayed"):
        "视图中权重半径叠加层当前是否显示",

    ("*", "Name of the vertex group to toggle"):    "要切换的顶点组名称",

    ("*", "JSON list of vertex group names active in the RigWeaver selector"):
        "RigWeaver选择器中激活的顶点组名称JSON列表",

    ("*", "How to combine weights from multiple groups"): "多组权重的合并方式",
    ("*", "Name for the new merged vertex group"):        "新合并顶点组的名称",

    ("*", "Delete the checked source groups after mixing"):
        "混合后删除已勾选的源顶点组",

    ("*", "Whether the mix preview is currently displayed"): "混合预览当前是否显示",
    ("*", "Active index for vertex group UIList"):           "顶点组列表的当前活跃索引",

    # -----------------------------------------------------------------------
    # Tooltips — enum item descriptions
    # -----------------------------------------------------------------------
    ("*", "One ribbon per chain (hair, fur, loose strands)"):
        "每条骨骼链生成一条带状网格（适合发丝、毛发、散状链条）",

    ("*", "Panels between sorted adjacent chains (flat panels, even chain spacing)"):
        "在排列好的相邻骨骼链之间生成面板（适合平面结构、均匀间距）",

    ("*", "Closed surface, last chain connects back to first (skirts, rings, cylinders)"):
        "封闭曲面，末端骨骼链与首端相连（适合裙摆、环形、圆柱体）",

    ("*", "Connected surface with automatic gap detection "
          "(inner/outer loop layouts, box pleats)"):
        "带自动间隙检测的连接曲面（适合内外双层布局、箱型褶皱）",

    ("*", "Sample-point triangulation for branching or irregular layouts (capes, fans)"):
        "基于采样点的三角剖分，适合分叉或不规则布局（披风、扇形）",

    ("*", "Strongest weight wins"):      "取最大权重",
    ("*", "Mean of all weights"):        "取所有权重的平均值",
    ("*", "Sum, clamped to 1.0"):        "权重叠加，上限为1.0",
    ("*", "Weakest weight wins"):        "取最小权重",

    # -----------------------------------------------------------------------
    # Tooltips — Generate Rig from Mesh
    # -----------------------------------------------------------------------
    ("*", "Toggle a viewport overlay showing where the generated bones will be "
          "placed. Updates live as Chains, Bones per Chain, and Up Axis change."):
        "切换视图叠加层，预览骨骼的生成位置。"
        "调整骨骼链数量、每链骨骼数和朝上轴向时实时更新。",

    ("*", "Generate a bone cage armature from the active mesh using cylindrical "
          "decomposition. Bones radiate around the mesh's up axis from top to bottom."):
        "使用圆柱分解法从当前激活网格生成骨骼笼骨架，"
        "骨骼沿网格朝上轴向由顶到底辐射分布。",

    ("*", "Regenerate the existing bone cage armature in-place using the current "
          "settings, preserving the Armature modifier on the source mesh."):
        "使用当前设置就地重新生成现有骨骼笼骨架，"
        "保留源网格上的骨架修改器。",

    ("*", "Parent the mesh to the generated armature so it follows it in "
          "the outliner hierarchy. World transform is preserved."):
        "将网格设为已生成骨架的子级，使其跟随骨架出现在大纲视图层级中。"
        "保留世界变换不变。",

    ("*", "Number of radial bone chains distributed around the mesh"):
        "围绕网格分布的放射状骨骼链数量",

    ("*", "Number of bones per chain (height subdivisions from top to bottom)"):
        "每条骨骼链的骨骼数量（由顶到底的高度细分数）",

    ("*", "Axis that points from the bottom to the top of the garment. "
          "AUTO detects the principal axis via PCA (requires NumPy)."):
        "从服装底部指向顶部的轴向。"
        "AUTO模式通过PCA自动检测主轴（需要NumPy）。",

    ("*", "Create one vertex group per bone and add an Armature modifier "
          "to the source mesh, making it immediately deform-ready."):
        "为每块骨骼创建顶点组，并向源网格添加骨架修改器，使其可立即用于变形。",

    ("*", "Radius of each bone's weight influence as a multiple of the bone's length. "
          "Vertices outside all zones fall back to the nearest bone."):
        "每块骨骼权重影响范围的半径，以骨骼长度的倍数表示。"
        "超出所有范围的顶点将归属至最近骨骼。",

    ("*", "Base name for the generated armature object and its bones"):
        "生成骨架对象及其骨骼的基础名称",

    ("*", "Detect automatically via PCA (requires NumPy)"):
        "通过PCA自动检测（需要NumPy）",
}

# zh_HANS is the BCP-47 / CLDR tag; zh_CN is the legacy Blender locale name.
# Both map to the same dictionary so either setting works.
translations_dict: dict[str, dict] = {
    "zh_CN":   _ZH_HANS,
    "zh_HANS": _ZH_HANS,
}
