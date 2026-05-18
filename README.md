# MyCalendar

一个为 Windows 自用场景设计的轻量日历应用。它使用 Python 和 PySide6 编写，目标是提供一个可以快速查看、添加和管理日程的小窗口日历，而不是复杂的同步型日历软件。

项目目前以本地使用为主，所有日程都保存在本机 JSON 文件中，不依赖网络和账号。

## 功能特点

- 日视图、周视图、月视图
- 小窗模式和全屏模式切换
- 本地保存日程数据
- 日程支持标题、日期、开始时间、结束时间、颜色和备注
- 日视图按时间轴显示日程
- 日程块会根据时长自动占据对应时间范围
- 重叠日程会横向分列显示
- 日视图左侧留出拖选区域，可以框选时间段快速创建日程
- 点击日程进入编辑页
- 编辑页支持修改和删除日程
- 时间选择使用滚轮式时间表
- 颜色选择使用纯色小方块
- 月视图用彩色圆点和横条展示日程摘要
- 周视图支持小窗横向滚动查看每天日程
- 日期按钮支持悬浮轮盘，在当前月份内滚动切换日期
- 返回按钮可以回到上一步页面
- 今天按钮可以回到今天的日视图

## 界面说明

顶部左侧：

```text
返回  今天  日  ‹ 当前周/月 ›
```

顶部右侧：

```text
周  月
```

其中：

- `返回`：回到上一步页面
- `今天`：回到今天的日视图
- `日`：切换到日视图；鼠标悬停时会出现日期轮盘
- `周`：切换到周视图
- `月`：切换到月视图，并自动进入全屏
- `‹ 当前周/月 ›`：仅在周视图或月视图中显示，用于切换上一周/下一周或上个月/下个月

## 运行方式

### 方式一：直接双击运行

第一次运行前，先双击：

```text
install_dependencies.bat
```

它会把 PySide6 安装到项目自己的 `.vendor` 文件夹中。

安装完成后，双击：

```text
run_calendar.bat
```

### 方式二：在 VSCode 终端运行

进入项目文件夹后执行：

```powershell
python main.py
```

如果提示缺少 PySide6，先运行：

```powershell
python -m pip install PySide6
```

或者只安装到当前项目目录：

```powershell
python -m pip install PySide6 --target .vendor
```

## 快捷键

- `Ctrl + N`：快速添加日程
- `Ctrl + T`：回到今天
- `F11`：全屏/小窗切换
- `Esc`：回到小窗模式

## 数据保存

日程数据保存在：

```text
data/events.json
```

程序第一次运行时会自动创建这个文件。

数据格式大致如下：

```json
{
  "id": "event-id",
  "date": "2026-04-30",
  "title": "示例日程",
  "start_hour": 9,
  "duration": 2,
  "color_name": "蓝色",
  "color": "#3B82F6",
  "notes": "备注内容",
  "created_at": "2026-04-30T18:00:00"
}
```

## 项目结构

```text
MyCalendar/
  main.py
  requirements.txt
  install_dependencies.bat
  run_calendar.bat
  data/
    events.json
  README.md
```

主要文件说明：

- `main.py`：应用主程序，包含界面、数据读写和日历逻辑
- `requirements.txt`：项目依赖
- `install_dependencies.bat`：安装 PySide6 到项目目录
- `run_calendar.bat`：启动程序
- `data/events.json`：本地日程数据

## 依赖

```text
PySide6
```

项目使用 Python 标准库处理日期、JSON 存储和基础路径逻辑，界面部分使用 PySide6。

## 当前定位

这个项目更像一个个人桌面工具，而不是完整商业日历软件。

它目前不包含：

- 云同步
- 账号登录
- 多设备同步
- 日程共享
- 复杂重复日程
- 系统托盘和全局快捷键

这些功能以后可以继续扩展，但当前版本优先保证自用、轻量和可维护。


## 开发背景

这个项目从一个简单的 Python 窗口日历开始，逐步演化成现在的 PySide6 桌面日历。开发重点一直是个人使用体验：快速打开、快速看日程、快速添加，不引入不必要的同步和账号系统。

## License

目前未指定开源许可证。上传到 GitHub 前建议根据你的想法选择一个许可证，比如 MIT License。
