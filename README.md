<div align="center">
  <img src="ico.ico" width="120" alt="GitHub Image Uploader Logo" />
  <h1 align="center">GitHub Image Uploader</h1>
  <h4 align="center">现代化 UI 的 GitHub 图床管理工具，支持上传、预览、重命名、删除、懒加载等功能</h4>
</div>

<div align="center">
  <a href="https://github.com/fengjiayou/GitHubImageUploader/stargazers"><img src="https://img.shields.io/github/stars/fengjiayou/GitHubImageUploader?style=for-the-badge&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/fengjiayou/GitHubImageUploader/releases/latest"><img src="https://img.shields.io/github/v/release/fengjiayou/GitHubImageUploader?style=for-the-badge&logo=github" alt="Latest Release"></a>
  <a href="https://github.com/fengjiayou/GitHubImageUploader/releases"><img src="https://img.shields.io/github/downloads/fengjiayou/GitHubImageUploader/total?style=for-the-badge&logo=github" alt="Downloads"></a>
  <a href="https://github.com/fengjiayou/GitHubImageUploader/issues"><img src="https://img.shields.io/github/issues/fengjiayou/GitHubImageUploader?style=for-the-badge&logo=github" alt="Issues"></a>
  <a href="https://github.com/fengjiayou/GitHubImageUploader/blob/main/LICENSE"><img src="https://img.shields.io/github/license/fengjiayou/GitHubImageUploader?style=for-the-badge" alt="License"></a>
</div>

---

## 关于

**GitHub Image Uploader** 是一个基于 Python + CustomTkinter 的图床管理工具，支持将图片直接上传到 GitHub 仓库并生成直链，还提供了现代化的管理界面。

主要功能：
-  **批量上传图片**（支持 PNG/JPG/JPEG/GIF）
-  **在线预览**（支持双击放大）
-  **全库图片管理**
-  **删除图片**
-  **复制直链/Markdown**
-  **懒加载 + 动态批量加载**
-  **自定义域名替换**
-  **跟随系统 / 明亮 / 暗色 主题**
-  **统计面板（总数、总大小、最后上传时间）**

---

## 系统要求

| 组件 | 需求 |
|------|------|
| **Python** | 3.8 或更高版本 |
| **依赖库** | `pillow`, `requests`, `customtkinter` |
| **系统** | Windows / macOS / Linux |

---

## 📦 安装

```bash
git clone https://github.com/fengjiayou/GitHubImageUploader.git
cd GitHubImageUploader
pip install -r requirements.txt
```
>**或**下载现成的[版本](https://github.com/fengjiayou/GitHubImageUploader/releases/tag/%E6%AD%A3%E5%BC%8F%E7%89%88)

## 配置

首次运行时，在 **设置** 中填写：

| 字段         | 必填 | 示例                        |
| ---------- | -- | ------------------------- |
| GitHub访问令牌 | ✅  | `ghp_xxxxxxxxxx`          |
| 仓库名称       | ✅  | `username/repo`           |
| 存储路径       | ❌  | `images/2025`             |
| 分支名称       | ❌  | `main`                    |
| 自定义域名      | ❌  | `https://cdn.example.com` |

> GitHub Token 需开启 `repo` 权限，可在 [GitHub Tokens](https://github.com/settings/tokens) 中创建。

## 运行
```bash
python main.py
```


## 界面预览

<div align="center">
  <img src="https://lsky-pro.fengmayou.top/u4PqWE.png" width="80%" alt="主界面" />
  <img src="https://lsky-pro.fengmayou.top/SVE0OA.png" width="80%" alt="设置" />
</div>


## 贡献

欢迎 PR 和 Issue 来改进这个项目！


## 许可证

MIT License © 2025 [FengJiayou](https://github.com/fengjiayou)
