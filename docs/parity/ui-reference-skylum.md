# Skylum 官方页面 UI 参考

参考页面：https://skylum.com/hans/luminar

该页面作为 zpixel_edit 的官方视觉方向和信息架构参考，但不替代本机 Luminar Neo 1.28.0
桌面应用的黑盒截图、控件值和事件回放。官网可能展示不同版本或营销合成图，因此不能
单独作为像素级 parity 通过证据。

## 可直接采用的视觉与布局原则

1. 主画布占据绝大部分空间，图片居中显示在接近黑色的沉浸背景中。
2. 顶部保持低高度工作区导航，主要入口为目录、预置、编辑和导出；付费附加功能不在
   本项目范围内；
   当前工作区使用高对比选中态，不使用大面积彩色导航。
3. 左侧为窄层/资源区，中央为预览画布，右侧为约 300–360 px 的工具与参数面板。
4. 右侧工具按 Favorites、Image Quality、Essentials、Landscape、Creative、Portrait 等
   分组；具体工具使用可折叠模块，展开后直接呈现滑杆和素材选择。
5. 控件采用紧凑的深色面板、细分隔线、小圆角和清晰的数值反馈；主要强调色仅用于
   当前选择、滑杆进度和主操作。
6. 底栏承载缩放比例、文件信息、前后对比和 Actions，不占用中央画布。
7. before/after 应是画布级快捷交互；工具应用后仍保留无损编辑栈和可回调参数。

## Sky AI 面板参考结构

```text
Sky AI
  Sky Selection / 天空素材网格
  Orientation
    Horizon Position
    Vertical Position
    Horizontal Position
    Flip
  Mask Refinement
    Global
    Close Gaps
    Fix Details
  Scene Relighting
  Reflection
  Sky Adjustments
```

zpixel_edit 的 Sky 页面应从当前少量全局参数升级为上述分区。模型不可用或 Exact
门禁未通过时，模块保留稳定布局并显示具体阻塞原因，不能用“已应用”状态掩盖
未完成模型的真实不可用状态。

## zpixel_edit 对齐优先级

### P0：工作区骨架

- 顶栏使用目录 / 预置 / 编辑 / 导出，不加入付费附加功能入口；
- 左层面板、中央画布、右工具面板、底部状态栏形成稳定四区结构；
- 收紧圆角、阴影和卡片间距，避免网页仪表盘观感；
- 画布优先，参数滚动只发生在右侧面板。

### P1：工具与参数面板

- 按官网工具家族重新组织现有 capability tabs；
- 工具列表使用折叠模块，当前模块显示编辑栈/遮罩入口和重置动作；
- Sky AI 使用素材选择、方向、蒙版细化、场景重照明、倒影和天空调整分区；
- loading、blocked、fallback 和 Exact 状态不引起布局跳动。

### P2：画布交互

- 增加底栏缩放、适合画布、100%、前后对比和 Actions；
- 增加按住查看原图、可拖拽 before/after 分割线和统一 preview/export 状态；
- 防止旧预览覆盖新参数，滑杆预览支持取消和请求版本号。

## 验收边界

- 官网页面：用于整体风格、功能家族、工作区结构和官方术语；
- 本机 Luminar Neo 1.28.0 build 23071 实机截图：用于尺寸、位置、字体、控件范围、默认值
  和状态；
- Luminar 事件回放：用于键盘、撤销/重做、滑杆提交、遮罩、素材和导出行为；
- 只有实机视觉 diff 和事件序列通过后，才能标记 UI parity-passed。
