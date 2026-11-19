PSOPT-HMI ECG monitor 更新包（Windows 已有旧版本）
版本日期：2026-11-18

适用场景
同事电脑上已有 ECG_Device_Controller_v2.py 和 biosignalHeartpy_v002.py，
旧版本能在原来的 Python 环境中连接 ECG、运行游戏并保存数据。
本包提供当前 v2 控制器及其监控功能；不是独立安装程序。

一、更新前
1. 退出正在运行的 ECG 程序。
2. 复制整个旧项目文件夹，保留一份完整备份。
3. 检查旧项目是否有本机配置或算法改动：
   ECG_Device_Controller_v2.py：webserver、ECG_DEVICES、frequency、code、r_threshold。
   biosignalHeartpy_v002.py：采样率 fs、分析窗口参数、shapeletA、shapeletB。
   更新后需保留与原实验一致的配置；若旧版还有其他自定义逻辑，先对比再合并。
   当前包仍使用原项目中的 BrainWellness Games API 地址，未配置新的服务器。

二、复制文件
将以下文件放进旧项目根目录，也就是原来运行 .bat 的那个文件夹：

  ECG_Device_Controller_v2.py     替换同名文件（先备份、核对配置）
  biosignalHeartpy_v002.py         替换同名文件（先备份、核对参数）
  ecg_monitor.py                  新增；若已有同名文件则先备份
  Start_ECG_Monitor_v2.bat         新增监控启动入口

不要替换或删除：
  PLUX-API-Python3 文件夹
  原来已能工作的 Python / Conda / venv 环境
  原有 CSV 数据、实验结果和其他启动脚本

不要直接在压缩包中运行 .bat；必须先解压并复制到原项目目录。
不要只复制 .bat：两个修改后的 Python 文件都需要 ecg_monitor.py。

三、启动
沿用旧版本成功运行时的环境。

如果旧版可以直接双击启动：
  双击 Start_ECG_Monitor_v2.bat
  输入与游戏一致的 Session Identifier，按回车。

如果旧版需要先激活 Conda / venv：
  先按原方法激活环境，再在旧项目目录运行：
  python ECG_Device_Controller_v2.py YOUR_SESSION_ID monitor

不要仅为这次更新改装另一版本 Python。PLUX 驱动必须与原有 Python
版本和 32/64 位架构匹配；本包不附带新的 PLUX 驱动。

新增窗口只依赖 Python 的 Tkinter；其余分析依赖沿用旧环境。
可在同一环境运行 python -m tkinter 检查窗口支持，检查完关闭测试窗口。

四、预期表现
设备连接后会显示地址和 battery 电量。
监控窗口在 ECG 实际开始采集时弹出，而不是刚启动脚本时弹出。
窗口显示原始/清理后波形、8 个窗口的 ln(HF-HRV)、shapelet A/B
相关系数、难度决策和上传状态。
关闭监控窗口不会停止实验；下一个 block 开始采集时可重新打开。
实验退出时监控窗口自动关闭。
原始 CSV 仍写入项目目录；HF-HRV 分析仍要求至少 90 秒 ECG。

不带 monitor 参数可以关闭监控：
  python ECG_Device_Controller_v2.py YOUR_SESSION_ID

五、首次验证与回退
先用测试 session 验证设备连接、游戏启动、窗口更新和 CSV 保存。
本包的离线回归检查及 Mac 设备连接检查通过；Windows 蓝牙和完整
实验流程仍需在接收方电脑上验证。
如需回退，退出程序后恢复备份的两个 Python 文件，再用原启动脚本运行。

包内没有受试者数据、CSV、凭据、虚拟环境或蓝牙驱动。
MANIFEST_SHA256.txt 用于核对包内文件是否完整。
