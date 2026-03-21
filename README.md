# RigWeaver

Bone extraction and simulation proxy mesh tools for Blender.

RigWeaver helps you:
- extract only deforming bones into a clean reduced armature,
- generate or update proxy meshes from selected pose-bone chains,
- generate/update a cage rig from mesh,
- multi-select and mix vertex groups faster.

---

## English

### 1. Requirements
- Blender 4.5.0+
- RigWeaver extension package (`RigWeaver_v<version>.zip`)
- Optional: NumPy (needed for some AUTO/TREE features)
- Optional: GPU support for viewport preview overlays

### 2. Install
1. Build package:
   - Run `./build.ps1` in repo root (PowerShell).
2. Install in Blender:
   - `Edit > Preferences > Extensions > Install from File`
   - Select generated zip: `RigWeaver_v<version>.zip`.
3. Open `3D Viewport > Sidebar (N) > RigWeaver`.

Note:
- The build script derives the zip base name from `blender_manifest.toml` `name`, then normalizes non-alphanumeric characters to `_`.

### 3. Main Workflows

#### A. Extract Deforming Bones (Armature, Object Mode)
1. Select an armature.
2. In `RigWeaver > Extract Deforming Bones`:
   - optional: `Retarget Meshes`
   - optional: `Auto Bone Orientation`
   - optional: `Connect Child Bones`
3. Click `Extract Deforming Bones`.

Result:
- Creates a reduced armature with only actually weighted/deforming bones.

#### B. Generate Proxy Mesh (Armature, Pose Mode)
1. Select armature, switch to Pose Mode.
2. Select pose bones/chains.
3. In `RigWeaver > Generate Mesh`, set:
   - `Mode` (Individual / Surface / Loop / Auto-Split / Tree)
   - longitudinal/lateral interpolation and resolution options
   - optional `Auto-Rig`, `Generate UVs`, `Subdivision Surface`
4. Click `Preview` to iterate.
5. Click `Generate Proxy Mesh` to commit, or `Update Mesh` to regenerate existing proxy.
6. Click `Discard Preview` to remove wireframe preview manually.

Result:
- Generates low-poly proxy geometry for simulation or rig workflows.

#### C. Generate Rig from Mesh (Mesh, Object Mode)
1. Select mesh object.
2. In `RigWeaver > Generate Rig from Mesh`, set:
   - `Chains`
   - `Bones per Chain`
   - `Up Axis` (`AUTO` requires NumPy)
   - optional weights/parent options
3. Click `Preview Rig`.
4. Click `Generate Rig` or `Update Rig`.

Result:
- Builds/updates a radial cage armature from mesh shape.

#### D. Vertex Group Select + Mix (Mesh, Edit/Weight Paint)
1. Select mesh with vertex groups.
2. Enter Edit Mode.
3. In `Vertex Group Select`, check groups, set:
   - `Blend Mode`
   - `Target`
   - `Remove Source Groups`
4. Click `Preview Mix` (enters Weight Paint preview).
5. Click `Mix into Group` to commit.

Result:
- Quickly combines multiple groups into one target group.

### 4. GIF Walkthrough Slots (docs/media)
Place your media files here and README will render them automatically.

#### Proxy Preview -> Generate Cycle
![Proxy Preview to Generate](docs/media/proxy-preview-generate.gif)

#### Proxy Update Cycle
![Proxy Update Mesh](docs/media/proxy-update-cycle.gif)

#### Rig From Mesh Preview -> Generate
![Rig From Mesh Preview to Generate](docs/media/rig-from-mesh-preview-generate.gif)

#### Vertex Group Preview Mix -> Commit
![Vertex Group Mix Workflow](docs/media/vg-mix-workflow.gif)

#### Optional Static Panel Overview
![RigWeaver Panel Overview](docs/media/panel-overview.png)

Recommended GIF capture guidelines:
- Keep each GIF around 4-10 seconds.
- Crop to the action area (panel + relevant viewport region).
- Avoid large dimensions/files; optimize for GitHub page load.
- Use clear starting/ending states so loop is understandable.

### 5. Mode/Context Requirements
- `Extract Deforming Bones`: active object must be Armature in Object Mode.
- `Generate Mesh` / `Preview Mesh` / `Update Mesh`: Armature in Pose Mode with selected pose bones.
- `Generate Rig from Mesh`: active object must be Mesh in Object Mode.
- `Vertex Group Select`: Mesh in Edit Mode or Weight Paint Mode.

### 6. NumPy/GPU Notes
- NumPy is required for:
  - `Tree` mesh mode in proxy generation,
  - `AUTO` up-axis in rig-from-mesh.
- GPU preview availability affects overlay preview operators.

### 7. Project Structure
```
.
├─ __init__.py
├─ blender_manifest.toml
├─ build.ps1
├─ translations.py
├─ operators/
│  ├─ extract_ops.py
│  ├─ mesh_gen_ops.py
│  ├─ rig_from_mesh_ops.py
│  └─ vg_select_ops.py
└─ ui/
   └─ panel.py
```

---

## 中文

### 1. 环境要求
- Blender 4.5.0+
- RigWeaver 扩展包（`RigWeaver_v<version>.zip`）
- 可选：NumPy（部分 AUTO/TREE 功能需要）
- 可选：GPU 预览叠加支持

### 2. 安装
1. 打包：
   - 在仓库根目录运行 `./build.ps1`（PowerShell）。
2. 在 Blender 安装：
   - `编辑 > 偏好设置 > 扩展 > 从文件安装`
   - 选择生成的 zip：`RigWeaver_v<version>.zip`。
3. 打开 `3D 视图 > 侧边栏(N) > RigWeaver`。

说明：
- 构建脚本会从 `blender_manifest.toml` 的 `name` 字段生成 zip 名称，并将非字母数字字符规范化为 `_`。

### 3. 核心流程

#### A. 提取形变骨骼（骨架对象，物体模式）
1. 选中骨架对象。
2. 在 `RigWeaver > Extract Deforming Bones` 中按需设置：
   - `Retarget Meshes`
   - `Auto Bone Orientation`
   - `Connect Child Bones`
3. 点击 `Extract Deforming Bones`。

结果：
- 生成仅包含实际参与权重变形骨骼的精简骨架。

#### B. 生成代理网格（骨架对象，姿态模式）
1. 选中骨架并切换到姿态模式。
2. 选择骨骼/骨骼链。
3. 在 `RigWeaver > Generate Mesh` 设置：
   - `Mode`（Individual / Surface / Loop / Auto-Split / Tree）
   - 纵向/横向插值与分辨率
   - 可选 `Auto-Rig`、`Generate UVs`、`Subdivision Surface`
4. 点击 `Preview` 反复预览。
5. 点击 `Generate Proxy Mesh` 提交，或 `Update Mesh` 更新现有网格。
6. 需要时点击 `Discard Preview` 手动丢弃线框预览。

结果：
- 生成用于模拟或绑定流程的低模代理网格。

#### C. 从网格生成绑定（网格对象，物体模式）
1. 选中网格对象。
2. 在 `RigWeaver > Generate Rig from Mesh` 设置：
   - `Chains`
   - `Bones per Chain`
   - `Up Axis`（`AUTO` 需要 NumPy）
   - 可选自动权重/父子关系
3. 点击 `Preview Rig`。
4. 点击 `Generate Rig` 或 `Update Rig`。

结果：
- 根据网格形状生成/更新放射式骨架笼。

#### D. 顶点组选择与混合（网格对象，编辑/权重绘制）
1. 选中带顶点组的网格。
2. 进入编辑模式。
3. 在 `Vertex Group Select` 中勾选并设置：
   - `Blend Mode`
   - `Target`
   - `Remove Source Groups`
4. 点击 `Preview Mix`（进入权重绘制预览）。
5. 点击 `Mix into Group` 提交。

结果：
- 快速将多个顶点组混合到目标组。

### 4. GIF 演示占位（docs/media）
将文件放入下列路径后，README 会自动显示。

#### 代理预览 -> 提交生成
![Proxy Preview to Generate](docs/media/proxy-preview-generate.gif)

#### 代理网格更新流程
![Proxy Update Mesh](docs/media/proxy-update-cycle.gif)

#### 从网格生成绑定 预览 -> 生成
![Rig From Mesh Preview to Generate](docs/media/rig-from-mesh-preview-generate.gif)

#### 顶点组预览混合 -> 提交
![Vertex Group Mix Workflow](docs/media/vg-mix-workflow.gif)

#### 可选静态图：面板总览
![RigWeaver Panel Overview](docs/media/panel-overview.png)

建议：
- 每段 GIF 控制在 4-10 秒。
- 裁剪到关键操作区域（面板 + 相关视口）。
- 控制分辨率和体积，避免 README 加载过慢。
- 起止状态清晰，循环时也能看懂。

### 5. 模式/上下文要求
- `Extract Deforming Bones`：激活对象为骨架，且在物体模式。
- `Generate Mesh` / `Preview Mesh` / `Update Mesh`：骨架对象 + 姿态模式 + 已选骨骼。
- `Generate Rig from Mesh`：激活对象为网格，且在物体模式。
- `Vertex Group Select`：网格对象，编辑模式或权重绘制模式。

### 6. NumPy/GPU 说明
- NumPy 用于：
  - 代理网格 `Tree` 模式，
  - 从网格生成绑定时的 `AUTO` 上轴检测。
- 叠加层预览功能依赖 GPU 预览能力。

### 7. 目录结构
```
.
├─ __init__.py
├─ blender_manifest.toml
├─ build.ps1
├─ translations.py
├─ operators/
│  ├─ extract_ops.py
│  ├─ mesh_gen_ops.py
│  ├─ rig_from_mesh_ops.py
│  └─ vg_select_ops.py
└─ ui/
   └─ panel.py
```
