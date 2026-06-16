# 快速开始 - GitHub Actions 自动编译

## 你需要什么
- GitHub 账户（免费注册：https://github.com/signup）
- Git（下载：https://git-scm.com/）

## 步骤

### 1. 创建 GitHub 仓库

登录 GitHub，点右上角 `+` → `New repository`
- 名称：`msr-driver`
- 选 **Private**（驱动代码别公开）
- 不要勾选 "Add a README"
- 点 `Create repository`

### 2. 上传代码

在 `msr_driver/` 目录下打开终端：

```bash
git init
git add .
git commit -m "MSR driver for Sandy Bridge"
git branch -M main
git remote add origin https://github.com/你的用户名/msr-driver.git
git push -u origin main
```

### 3. 等待编译

1. 打开仓库页面 → `Actions` 标签
2. 会自动看到 "Build MSR Driver" 工作流在运行
3. 等待 3-5 分钟完成（绿色 ✅）

### 4. 下载 .sys 文件

1. 点击完成的工作流 run
2. 下方 `Artifacts` 区域找到 `msr-driver-x64`
3. 点击下载 zip，解压得到 `msr_drv.sys`

### 5. 在 Win11 上安装驱动

```cmd
# 以管理员身份运行

# 1. 开启测试签名模式
bcdedit /set testsigning on
# 重启电脑

# 2. 复制驱动到系统目录
copy msr_drv.sys C:\Windows\System32\drivers\

# 3. 注册并启动
sc create msr_drv type= kernel start= demand binPath= C:\Windows\System32\drivers\msr_drv.sys
sc start msr_drv

# 4. 运行 Python 客户端
python msr_client.py
```

## 注意事项

- 驱动未签名（GitHub Actions 编译出来的没有签名）
- 必须开启 `testsigning` 模式才能加载
- 用完后可以关闭：`bcdedit /set testsigning off`
