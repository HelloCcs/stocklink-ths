# StockLink THS

StockLink THS 是一款 Windows 桌面辅助工具，可将表格中的六位股票代码发送到正在运行的同花顺行情窗口，并切换到该股票的日 K 图。

## 使用方法

1. 启动 StockLink。
2. 在 WPS 或其他表格中复制一个六位股票代码。
3. 按 **Ctrl+Alt+Z**。
4. StockLink 查找可见的同花顺窗口，激活所选窗口，输入股票代码，再发送同花顺的 `05` 日 K 命令。

项目还保留了早期的日期标记和 K 线跟踪模块，供开发和研究使用。当前简化热键流程不代表日期覆盖标记功能已经通过真实界面验收。

## 运行环境

- Windows 10 或更高版本
- Python 3.10 或更高版本
- 本机已安装同花顺客户端（`hexin.exe`）
- 安装 `requirements.txt` 中的 Python 依赖；使用 OCR 模块时还需安装 `requirements-vision.txt` 中的依赖

在项目目录中创建虚拟环境并安装基础依赖：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动程序：

```powershell
.\.venv\Scripts\python.exe main.py
```

源码运行流程面向 Windows，并使用带安全检查的 Win32 输入操作。无法唯一识别可见同花顺目标窗口时，程序会停止并报告失败。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -q
```

最近一次本地测试共运行 101 项，失败、错误和跳过均为 0。测试覆盖表格数据解析、热键分发、目标窗口选择、命令顺序和失败传播。真实同花顺界面行为仍取决于用户的 Windows 桌面环境及同花顺版本。

## 范围与安全

仓库不包含同花顺、WPS、客户表格、截图、运行证据或打包后的二进制文件。请自行安装相关软件并遵循其许可和使用条款。本工具不用于发送交易委托或修改账户数据。

## 参与贡献

请参阅[贡献指南](CONTRIBUTING.md)。涉及窗口激活或键盘修饰键的改动，应附带针对性测试和清晰的 Windows 复现步骤。

## 安全问题

请参阅[安全说明](SECURITY.md)。请勿在 Issue 或 Pull Request 中附上凭据、客户文件、截图或实时桌面证据。

## 许可证

本项目代码采用 MIT 许可证。第三方依赖仍分别适用其自身许可证；详情见[第三方依赖说明](THIRD_PARTY_NOTICES.md)。
