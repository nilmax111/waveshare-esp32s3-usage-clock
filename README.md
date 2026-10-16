# Waveshare ESP32-S3 Usage Clock

Waveshare ESP32-S3-LCD-1.47 五页 USB 信息屏，Mac 获取指标，屏幕显示时间与数据。

BOOT 顺序：**Codex → WorkBuddy → DeepSeek → 硬件信息 → 农历时辰**。重新上电回到首页；不要按住 BOOT 插电，否则可能进入下载模式。

## 功能

- 北京时间 UTC+8，每2秒USB同步，保持供电时可离线计时。
- Codex：两个额度窗口的已用/剩余比例和重置时间，不是普通ChatGPT消息数或剩余token。
- WorkBuddy：当前资源包积分，不是终身消费。使用本机官方客户端登录，内部接口可能随升级变化。
- DeepSeek：分别显示CNY/USD总余额、充值/赠送余额；累计消费和token接口未提供，显示N/A。
- 硬件：Flash、应用、Heap、PSRAM、SD统计；SD异步扫描不阻塞页面。
- 农历：日期、干支生肖、时辰刻数、传统经络对应与一般生活提示，不是健康测量或诊疗建议。

## 硬件

专用于 ESP32-S3-LCD-1.47：172×320 ST7789，无触摸，16MB Flash，固件不启用PSRAM。
LCD MOSI45/SCLK40/CS42/DC41/RST39/BL48；BOOT GPIO0；SD CLK14/CMD15/D0 16（1-bit）。

## 安装和构建

需要macOS、Python 3.12及已登录的官方Codex/WorkBuddy客户端。DeepSeek可选，首次配置需要Swift编译器（Xcode Command Line Tools）。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x build.sh run.command *.command
./build.sh
```

烧录前确认板型、备份和实际端口，停止占用串口的服务。PORT需自行替换：

```sh
.venv/bin/python host/service.py uninstall
./build.sh -t upload --upload-port PORT
```

PlatformIO上传可能更新引导程序和分区，请先备份原固件。本仓库不含个人设备备份、工具链或编译固件。

## 配置与启动

默认只连接唯一一块匹配USB VID/PID的Espressif设备；同类板无法仅凭VID/PID区分。推荐复制`device.example.json`为`device.local.json`，填入自己的目标板序列号。本地配置被Git忽略。也可前台运行`host/bridge.py --port PORT`。

在项目目录双击`启动微雪屏同步.command`，或执行：

```sh
.venv/bin/python host/service.py install
.venv/bin/python host/service.py status
# 重启 / 停止并卸载
.venv/bin/python host/service.py restart
.venv/bin/python host/service.py uninstall
```

登录Mac后后台同步，USB自动重连。Mac休眠/关机时不能获取新数据；被macOS禁止的后台项目需要用户允许。关闭启动窗口不停止服务。脚本相对自身定位项目，不要单独复制到桌面，可创建Finder替身。移动项目后重新安装服务。

同一用户的`local.waveshare.codex-clock`服务标签只管理一个实例，不要与旧副本同时运行。启动检查预期固件v5.3，要求近期USB回执和三个平台数据；未配置的平台会报告未就绪，其他功能仍可运行。SD需进入硬件页触发扫描。脚本不会自动烧录。

## 认证和隐私

- Codex通过官方本机app-server，不复制登录文件。
- WorkBuddy在内存使用当前官方客户端认证，唯一目标为`https://copilot.tencent.com/billing/meter/get-user-resource-summary`，不跟随重定向。仅适配个人账户。运行此适配器表示你允许它为查询自己的积分使用当前登录状态；代码不含官方程序、密钥或认证数据。
- DeepSeek双击`配置DeepSeek密钥.command`隐藏输入Key，存入macOS登录钥匙串，仅访问`https://api.deepseek.com/user/balance`。Key不写入源码、命令参数、固件或串口。钥匙串锁定时可能不可用。
- 不要上传Key、Token、登录文件、`.runtime`、设备备份或实际序列号。运行数据只在本机生成；同用户权限或进程内存被攻破时不保证凭据安全。

这是独立清理的源码快照，不包含原工作区历史、个人路径、账号记录、日志、设备备份或交接文档。通用应用路径是支持软件的位置，不是私人配置。

## 验证和字库

```sh
.venv/bin/python -m unittest discover -s host -p 'test_*.py'
clang++ -std=c++11 -I src tests/lunar_calendar_test.cpp -o /tmp/lunar-test
/tmp/lunar-test
```

已生成的中文字库来自Noto Sans SC（SIL OFL 1.1），归属及许可见`third_party/`；无本机系统字体。直接构建不需要下载字体。重建时运行：

```sh
.venv/bin/python scripts/build_lunar_assets.py --font /path/to/NotoSansSC.ttf
```

农历表范围1900–2100，未逐日核验全表。午夜换日、生肖按农历年；23:00子时起，每刻15分钟是本页约定。字模统一基线。

## 资料

- [微雪硬件](https://docs.waveshare.net/ESP32-S3-LCD-1.47/)
- [DeepSeek余额接口](https://api-docs.deepseek.com/api/get-user-balance/)
- [香港天文台历法](https://www.hko.gov.hk/sc/gts/time/conversion.htm)
- [Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc)

第三方字体按随附许可使用；项目不额外授予第三方客户端代码/协议权利。仓库未指定整体开源许可证。
