PSOPT-HMI + ECG Monitor — Windows 64 位完整项目包
版本日期：2026-11-18

这是完整项目包，可解压到新文件夹独立使用，不必覆盖旧项目。
包含代码、Windows PLUX 驱动、启动脚本、环境检查、依赖清单和测试。
不包含 Python 安装程序、已安装的 Python 环境或受试者/实验数据。

一、已有正常运行的旧版本（推荐沿用原环境）
1. 将整个压缩包解压到一个新的本地文件夹，例如 C:\PSOPT-HMI-Monitor。
   保留旧项目作为备份，不要把旧虚拟环境复制过来。
2. 对照原控制器检查新文件的配置：
   ECG_Device_Controller_v2.py：webserver、ECG_DEVICES、frequency、code、r_threshold。
   biosignalHeartpy_v002.py：fs、窗口参数、shapeletA、shapeletB。
   如果她使用的服务器、设备或实验参数不同，请改为原来的值。
   若旧版本有额外自定义逻辑，需要先核对，不能仅凭文件名视为相同。
3. 原来若需要激活 Conda / venv，先按原方法激活，然后进入新目录。
4. 运行 python check_windows_environment.py 检查依赖和驱动。
5. 运行 Start_ECG_Monitor_v2.bat，输入游戏使用的 Session Identifier。
   原来可直接双击 .bat 的电脑，也可直接双击新 .bat。

命令行等价入口：
  python ECG_Device_Controller_v2.py YOUR_SESSION_ID monitor

不显示监控窗口：
  python ECG_Device_Controller_v2.py YOUR_SESSION_ID
  或运行 Start_ECG_Recording_v2.bat。

二、需要新建环境时
本包沿用原项目自带的驱动，提供 Win64_37、Win64_38、Win64_39、Win64_310。
原来的 Python 版本、架构与 PLUX 驱动必须匹配。
配套依赖清单固定为 Python 3.10 x64；不要把它直接装入旧版 3.7/3.8/3.9 环境。
这些旧版本仅用于兼容现有驱动；本包没有迁移到新一代 PLUX SDK。

如果电脑已安装 Python 3.10 64 位（含 pip、venv、Tcl/Tk）：
  双击 Setup_Environment.bat。
  它会在当前目录创建 .venv，并联网安装 requirements-windows-py310.lock.txt。
  安装成功后，两个启动 .bat 会自动使用本目录的 .venv。
  它不会修改旧项目的环境；已有 .venv 版本不符时会停止，不会删除替换。

手动执行等价命令：
  py -3.10-64 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements-windows-py310.lock.txt
  .venv\Scripts\python.exe check_windows_environment.py

Python Windows 安装与 launcher 说明：
https://docs.python.org/3.10/using/windows.html

三、设备与游戏
1. 充好电，拔掉充电线，再开机使用；沿用原来的 Windows 蓝牙配对方法。
2. 一次只运行一个连接该设备的采集程序，关闭旧版采集程序和 OpenSignals。
3. 在游戏和控制器中使用相同 Session Identifier。
4. 设备连接后，会显示地址和 battery 电量；低于 10% 会提示充电。
5. 监控窗口在实际开始 ECG 采集时弹出，不是在脚本刚启动时弹出。
6. 关闭监控窗口不会停止实验；下个 block 可重新打开。

当前默认服务器：
https://brainwellnessgamesapi.azurewebsites.net

当前已配置设备地址：
BTH00:07:80:0F:31:54
BTH00:07:80:0F:30:9F
BTH00:07:80:0F:31:34

四、输出和分析
ECG_Block_*.csv、HF_Block_*.csv、Rho_Shapelet_*.csv 写入运行目录。
监控波形只为显示缩减点数；原始 CSV 和分析仍使用完整数据。
监控读取既有算法结果，不另算难度决策。
现有 HF-HRV 分析要求至少 90 秒 ECG；本次没有增加短 block 的替代决策。

五、常见问题
No module named ...：未激活旧环境，或新环境依赖没有安装完成。
No bundled driver ...：Python 版本或 32/64 位与驱动不匹配。
DLL load failed / MSVCP140.dll / VCRUNTIME140.dll：检查 Microsoft Visual C++
x64 运行库。使用微软官方安装包，勿从第三方站点下载单个 DLL：
https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
设备找不到：检查开机、配对、是否被其他程序占用，以及 ECG_DEVICES。
服务器或 session 错误：确认网络、webserver 和 Session Identifier。
未弹监控窗：确认命令带 monitor，并且游戏已经进入 ECG 采集阶段。

六、验证范围
运行源代码保持与发送方当前版本一致。
离线回归及 macOS 实际设备连接读取已验证；Windows 蓝牙采集需要在
接收方电脑上用测试 session 验证，不能把静态打包检查当作 Windows 实机测试。
可在 Python 3.10 环境执行：python -m unittest -v test_ecg_monitor.py
check_windows_environment.py 只检查环境，不连接蓝牙、不访问游戏 API。

七、文件完整性与第三方来源
MANIFEST_SHA256.txt 记录包内文件的校验值。
third_party 记录 PLUX 来源及上游仓库许可证副本。
本包未包含 CSV、运行日志、账号凭据或个人 Python 环境。
