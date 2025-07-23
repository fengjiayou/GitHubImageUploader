import os
import json
import base64
import threading
import requests
import re
import io
from datetime import datetime
from urllib.parse import urlparse
from PIL import Image, ImageOps, ImageDraw
import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog, Menu, Toplevel, Label
import webbrowser


# 初始化设置
ctk.set_appearance_mode("System")  # 跟随系统主题
ctk.set_default_color_theme("blue")  # 蓝色主题
CONFIG_FILE = "config.json"

class GitHubImageManager:
    """GitHub图床管理核心功能类"""
    @staticmethod
    def upload_image(file_path, config):
        """上传图片到GitHub仓库"""
        required = ["token", "repo"]
        if any(config.get(k) is None for k in required):
            raise ValueError("缺少必要配置参数")

        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }

        path = config.get("path", "").strip("/")
        filename = os.path.basename(file_path)
        upload_path = f"{path}/{filename}" if path else filename

        response = requests.put(
            f"https://api.github.com/repos/{config['repo']}/contents/{upload_path}",
            headers=headers,
            json={
                "message": f"Upload {filename}",
                "content": content,
                "branch": config.get("branch", "main")
            }
        )

        if response.status_code not in [200, 201]:
            raise Exception(response.json().get("message", "上传失败"))
        
        return response.json()["content"]["download_url"]

    @staticmethod
    def list_images(config):
        """获取仓库中的图片列表"""
        if not all(k in config for k in ["token", "repo"]):
            raise ValueError("缺少必要配置参数")

        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }

        path = config.get("path", "").strip("/")
        url = f"https://api.github.com/repos/{config['repo']}/contents/{path}" if path else \
              f"https://api.github.com/repos/{config['repo']}/contents"

        response = requests.get(
            url,
            headers=headers,
            params={"ref": config.get("branch", "main")}
        )

        if response.status_code == 200:
            return [
                item["download_url"] for item in response.json() 
                if item["type"] == "file" and
                item["name"].lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
            ]
        else:
            raise Exception(response.json().get("message", "获取文件列表失败"))

    @staticmethod
    def delete_image(url, config):
        """从GitHub删除图片"""
        path = GitHubImageManager._extract_path_from_url(url, config)
        
        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }

        # 获取文件SHA
        response = requests.get(
            f"https://api.github.com/repos/{config['repo']}/contents/{path}",
            headers=headers,
            params={"ref": config.get("branch", "main")}
        )

        if response.status_code != 200:
            raise Exception("获取文件信息失败")

        # 执行删除
        response = requests.delete(
            f"https://api.github.com/repos/{config['repo']}/contents/{path}",
            headers=headers,
            json={
                "message": f"Delete {os.path.basename(path)}",
                "sha": response.json()["sha"],
                "branch": config.get("branch", "main")
            }
        )

        if response.status_code != 200:
            raise Exception("删除失败")

        return True

    @staticmethod
    def _extract_path_from_url(url, config):
        """从URL提取GitHub路径"""
        if config.get("custom_domain") and url.startswith(config["custom_domain"]):
            url = url.replace(config["custom_domain"], "https://raw.githubusercontent.com")

        match = re.search(
            r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/(.+)", 
            url
        )
        if not match:
            raise Exception("无法解析URL")

        return match.group(3)

class ModernImageUploader(ctk.CTk):
    """现代化GitHub图床管理工具"""
    def __init__(self):
        super().__init__()
        
        # 窗口设置
        self.title("GitHub图床管理工具 Pro")
        self.geometry("1280x800")
        self.minsize(1024, 768)
        
        # 加载配置
        self.config = self._load_config()
        self.images = []
        self.current_image = None
        self.current_loaded = 0
        
        # 懒加载设置
        self.lazyload_enabled = self.config.get("lazyload_enabled", True)
        self.dynamic_batch_size = self.config.get("dynamic_batch_size", 30)
        
        # 创建UI
        self._setup_ui()
        
        # 加载图片
        self.refresh_images()

    def _load_config(self):
        """加载配置文件"""
        default_config = {
            "token": "",
            "repo": "",
            "path": "",
            "branch": "main",
            "custom_domain": "",
            "dark_mode": False,
            "auto_refresh": True,
            "lazyload_enabled": True,
            "dynamic_batch_size": 30,
            "theme_mode": "System"
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 确保所有字段都有值且类型正确
                    for key in default_config:
                        if key not in loaded_config:
                            loaded_config[key] = default_config[key]
                        elif loaded_config[key] is None and isinstance(default_config[key], bool):
                            loaded_config[key] = default_config[key]
                    return loaded_config
            except Exception as e:
                self._log(f"加载配置失败: {e}, 使用默认配置")
                return default_config
        return default_config

    def _save_config(self):
        """保存配置文件"""
        # 确保所有布尔值不是null
        for key in self.config:
            if isinstance(self.config.get(key), bool):
                self.config[key] = bool(self.config[key])
        
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(f"保存配置失败: {e}")

    def _setup_ui(self):
        """设置现代化UI界面"""
        # 主网格布局
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # ===== 左侧边栏 =====
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nswe")
        self.sidebar.grid_rowconfigure(5, weight=1)
        
        # 应用标题
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="图床管理",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # 上传按钮
        self.upload_btn = ctk.CTkButton(
            self.sidebar,
            text="上传新图片",
            command=self._upload_files_dialog,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2A8CFF",
            hover_color="#1E6FC7"
        )
        self.upload_btn.grid(row=1, column=0, padx=20, pady=10)
        
        # 刷新按钮
        self.refresh_btn = ctk.CTkButton(
            self.sidebar,
            text="刷新列表",
            command=self.refresh_images,
            height=36,
            font=ctk.CTkFont(size=13)
        )
        self.refresh_btn.grid(row=2, column=0, padx=20, pady=5)
        
        # 统计信息面板
        self._setup_stats_panel()
        
        # 日志区域
        self.log_frame = ctk.CTkFrame(self.sidebar)
        self.log_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=10)
        self.log_area = ctk.CTkTextbox(
            self.log_frame,
            height=100,
            wrap="word",
            font=ctk.CTkFont(size=11)
        )
        self.log_area.pack(fill="both", expand=True)
        
        # 设置按钮
        self.settings_btn = ctk.CTkButton(
            self.sidebar,
            text="⚙️ 设置",
            command=self._open_settings,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=1
        )
        self.settings_btn.grid(row=7, column=0, padx=20, pady=10)
        
        # ===== 主内容区 =====
        self.main_content = ctk.CTkFrame(self, corner_radius=0)
        self.main_content.grid(row=0, column=1, sticky="nsew")
        self.main_content.grid_rowconfigure(1, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)
        
        # 搜索栏
        self._setup_search_bar()
        
        # 图片网格展示区
        self._setup_image_grid()
        
        # 底部状态栏
        self._setup_status_bar()
        
        # 右键菜单
        self._setup_context_menu()

    def _setup_stats_panel(self):
        """设置统计信息面板"""
        self.stats_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.stats_frame.grid(row=3, column=0, padx=10, pady=20, sticky="we")
        
        ctk.CTkLabel(
            self.stats_frame,
            text="📊 统计信息",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        self.image_count_label = ctk.CTkLabel(
            self.stats_frame,
            text="图片总数: 0",
            font=ctk.CTkFont(size=12)
        )
        self.image_count_label.pack(anchor="w")
        
        self.last_upload_label = ctk.CTkLabel(
            self.stats_frame,
            text="最后上传: 无",
            font=ctk.CTkFont(size=12)
        )
        self.last_upload_label.pack(anchor="w", pady=(5, 0))
        
        self.total_size_label = ctk.CTkLabel(
            self.stats_frame,
            text="总大小: 0 MB",
            font=ctk.CTkFont(size=12)
        )
        self.total_size_label.pack(anchor="w", pady=(5, 0))

    def _setup_search_bar(self):
        """设置搜索栏"""
        self.search_frame = ctk.CTkFrame(self.main_content, height=60)
        self.search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="搜索图片...",
            width=300,
            height=36
        )
        self.search_entry.pack(side="left", padx=10)
        
        self.search_btn = ctk.CTkButton(
            self.search_frame,
            text="搜索",
            width=80,
            height=36,
            command=self._search_images
        )
        self.search_btn.pack(side="left", padx=5)
        
        self.clear_search_btn = ctk.CTkButton(
            self.search_frame,
            text="清除",
            width=80,
            height=36,
            fg_color="transparent",
            border_width=1,
            command=self._clear_search
        )
        self.clear_search_btn.pack(side="left", padx=5)

    def _setup_image_grid(self):
        """设置图片网格展示区"""
        self.image_grid_frame = ctk.CTkScrollableFrame(
            self.main_content,
            fg_color="transparent"
        )
        self.image_grid_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # 3列网格布局
        for i in range(3):
            self.image_grid_frame.grid_columnconfigure(i, weight=1, uniform="col")
        
        # 上传卡片（居中显示）
        self.upload_card = ctk.CTkFrame(
            self.image_grid_frame,
            width=280,
            height=280,
            border_width=2,
            border_color=("#D1D1D1", "#3A3A3A"),
            fg_color=("gray95", "gray15")
        )
        self.upload_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.upload_icon = ctk.CTkLabel(
            self.upload_card,
            text="⬆️",
            font=ctk.CTkFont(size=48),
            justify="center"
        )
        self.upload_icon.pack(expand=True, pady=(40, 10))
        
        self.upload_text = ctk.CTkLabel(
            self.upload_card,
            text="点击上传图片\n或拖放文件到窗口",
            font=ctk.CTkFont(size=14),
            justify="center"
        )
        self.upload_text.pack(expand=True, pady=(0, 40))
        
        self.upload_card.bind("<Button-1>", lambda e: self._upload_files_dialog())

    def _setup_status_bar(self):
        """设置底部状态栏"""
        self.status_bar = ctk.CTkFrame(self.main_content, height=40)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="就绪",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.pack(side="left", padx=15)
        
        self.progress_bar = ctk.CTkProgressBar(
            self.status_bar,
            orientation="horizontal",
            width=200,
            height=6
        )
        self.progress_bar.pack(side="right", padx=15)
        self.progress_bar.set(0)

    def _setup_context_menu(self):
        """设置右键菜单"""
        self.context_menu = Menu(self, tearoff=0, font=("Arial", 10))

        self.context_menu.add_command(
            label="🖼️ 预览图片",
            command=self._preview_image
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🗌 复制链接",
            command=self._copy_image_url
        )
        self.context_menu.add_command(
            label="📝 复制Markdown",
            command=self._copy_markdown
        )
        self.context_menu.add_command(
            label="📂 重命名图片",
            command=self._rename_image
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🗑️ 删除图片",
            command=self._delete_image
        )

    def _rename_image(self):
        """重命名图片"""
        if not self.current_image:
            return

        old_name = self.current_image["name"]
        new_name = simpledialog.askstring("重命名图片", "输入新的文件名:", initialvalue=old_name)

        if new_name and new_name != old_name:
            try:
                self._log(f"开始重命名: {old_name} -> {new_name}")
                
                # 下载旧图
                response = requests.get(self.current_image["raw_url"], stream=True)
                image_data = response.content
                temp_path = os.path.join("temp_rename", new_name)

                os.makedirs("temp_rename", exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(image_data)
                
                # 上传新图
                GitHubImageManager.upload_image(temp_path, self.config)

                # 删除旧图
                GitHubImageManager.delete_image(self.current_image["raw_url"], self.config)

                self._log(f"重命名成功: {new_name}")
                self.refresh_images()

                os.remove(temp_path)
                os.rmdir("temp_rename")
            
            except Exception as e:
                messagebox.showerror("重命名失败", str(e))

    def _upload_files_dialog(self):
        """打开文件选择对话框"""
        files = filedialog.askopenfilenames(
            title="选择要上传的图片",
            filetypes=[
                ("图片文件", "*.png;*.jpg;*.jpeg"),
                ("GIF文件", "*.gif"),
                ("所有文件", "*.*")
            ]
        )
        if files:
            self._upload_files(files)

    def _upload_files(self, file_paths):
        """上传文件到GitHub"""
        def upload_task():
            self._show_progress(True)
            
            for i, path in enumerate(file_paths, 1):
                try:
                    filename = os.path.basename(path)
                    self._update_status(f"正在上传 ({i}/{len(file_paths)}): {filename}")
                    
                    # 检查文件大小 (GitHub限制25MB)
                    file_size = os.path.getsize(path)
                    if file_size > 25 * 1024 * 1024:
                        self._log(f"文件过大: {filename} (超过25MB)")
                        continue
                    
                    # 上传到GitHub
                    upload_url = GitHubImageManager.upload_image(path, self.config)
                    
                    if upload_url:
                        self._log(f"上传成功: {filename}")
                        self.refresh_images()
                    else:
                        self._log(f"上传失败: {filename}")
                        
                except Exception as e:
                    self._log(f"上传错误: {str(e)}")
            
            self._show_progress(False)
            self._update_status("上传完成")
        
        threading.Thread(target=upload_task, daemon=True).start()

    def refresh_images(self):
        """刷新图片列表"""
        def refresh_task():
            self._show_progress(True)
            self._update_status("正在加载图片...")
            
            try:
                self._clear_images()
                
                urls = GitHubImageManager.list_images(self.config)
                
                if not urls:
                    self._log("没有找到图片")
                    return
                
                # 初始加载部分图片
                initial_batch = urls[:self.dynamic_batch_size] if self.lazyload_enabled else urls
                for url in initial_batch:
                    self._add_image_preview(url)
                
                self.current_loaded = len(initial_batch)
                self._log(f"已加载 {len(initial_batch)} 张图片")
                self._update_stats()
                
                # 如果启用懒加载，启动懒加载检查
                if self.lazyload_enabled and len(urls) > self.current_loaded:
                    self._start_lazy_loader(urls[self.current_loaded:])
                
            except Exception as e:
                self._log(f"加载失败: {str(e)}")
            
            self._show_progress(False)
            self._update_status("就绪")
        
        threading.Thread(target=refresh_task, daemon=True).start()

    def _start_lazy_loader(self, remaining_urls):
        """启动懒加载器"""
        def lazy_load_task():
            while remaining_urls and self.lazyload_enabled:
                # 检查当前可见区域
                visible_widgets = []
                for widget in self.image_grid_frame.winfo_children():
                    if hasattr(widget, "image_data") and self._is_widget_visible(widget):
                        visible_widgets.append(widget)
                
                # 如果滚动到底部附近，加载更多
                if len(visible_widgets) > 0 and visible_widgets[-1] == self.image_grid_frame.winfo_children()[-1]:
                    batch = remaining_urls[:self.dynamic_batch_size]
                    for url in batch:
                        self._add_image_preview(url)
                        remaining_urls.remove(url)
                    self.current_loaded += len(batch)
                    self._log(f"懒加载 {len(batch)} 张图片")
                
                self.after(500, lazy_load_task)
                break
        
        self.after(500, lazy_load_task)

    def _is_widget_visible(self, widget):
        """检查部件是否在可见区域内"""
        try:
            canvas = self.image_grid_frame._parent_canvas
            widget_y = widget.winfo_y()
            canvas_height = self.image_grid_frame.winfo_height()
            return 0 <= widget_y <= canvas_height
        except Exception:
            return False

    def _clear_images(self):
        """清空图片列表"""
        for widget in self.image_grid_frame.winfo_children():
            if widget != self.upload_card:
                self.after(10, widget.destroy)  # 延迟销毁避免 canvas 被引用错误
        self.images = []
        self.current_loaded = 0

        # 隐藏上传卡片
        self.upload_card.grid_remove()

    def _add_image_preview(self, image_url):
        """添加现代化图片预览卡片"""
        try:
            # 解析文件名和路径
            filename = os.path.basename(image_url)
            display_url = self._apply_custom_domain(image_url)
            
            # 创建卡片容器
            card = ctk.CTkFrame(
                self.image_grid_frame,
                width=280,
                height=280,
                corner_radius=10,
                border_width=1,
                border_color=("#E1E1E1", "#4A4A4A")
            )
            
            # 计算插入位置（保持上传卡片在中间）
            row, col = divmod(len(self.images), 3)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            card.image_data = {
                "url": display_url, 
                "raw_url": image_url, 
                "name": filename,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "loaded": False
            }
            
            # 加载缩略图（带圆角效果）
            img_label = ctk.CTkLabel(
                card,
                text="加载中...",
                width=240,
                height=180,
                corner_radius=10,
                fg_color=("gray90", "gray20")
            )
            img_label.pack(pady=(10, 5))
            card.image_label = img_label
            
            # 图片信息
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            # 文件名（带省略号）
            name_label = ctk.CTkLabel(
                info_frame,
                text=filename,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            name_label.pack(fill="x")
            name_label.bind("<Button-3>", self._show_context_menu)
            
            # 日期信息
            date_label = ctk.CTkLabel(
                info_frame,
                text=card.image_data["date"],
                font=ctk.CTkFont(size=10),
                text_color=("gray50", "gray40"),
                anchor="w"
            )
            date_label.pack(fill="x", pady=(2, 0))
            
            # 操作按钮组
            btn_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            btn_frame.pack(fill="x", pady=(5, 0))
            
            ctk.CTkButton(
                btn_frame,
                text="链接",
                width=60,
                height=24,
                font=ctk.CTkFont(size=10),
                command=lambda u=display_url: self._copy_to_clipboard(u)
            ).pack(side="left", padx=(0, 5))
            
            ctk.CTkButton(
                btn_frame,
                text="Markdown",
                width=80,
                height=24,
                font=ctk.CTkFont(size=10),
                command=lambda: self._copy_markdown()
            ).pack(side="left", padx=(0, 5))
            
            # 绑定右键菜单
            card.bind("<Button-3>", self._show_context_menu)
            
            # 添加到图片列表
            self.images.append(card.image_data)
            self._update_stats()
            
            # 如果是懒加载模式，延迟加载图片
            if self.lazyload_enabled:
                def load_image():
                    if self._is_widget_visible(card) and not card.image_data["loaded"]:
                        self._load_card_image(card)
                
                self.after(100, load_image)
            else:
                self._load_card_image(card)
            
        except Exception as e:
            self._log(f"添加预览失败: {str(e)}")

    def _load_card_image(self, card):
        """加载卡片图片内容"""
        try:
            url = card.image_data["raw_url"]
            response = requests.get(url, timeout=5)
            img = Image.open(io.BytesIO(response.content))
            img = ImageOps.fit(img, (240, 180), method=Image.LANCZOS)
            
            # 创建圆角遮罩
            mask = Image.new("L", (240, 180), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, 240, 180), radius=10, fill=255)
            
            img.putalpha(mask)
            
            # 转换为CTkImage
            photo = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(240, 180)
            )
            
            card.image_label.configure(image=photo, text="")
            card.image_label.image = photo
            card.image_label.bind("<Double-1>", lambda e: self._preview_image(url))
            card.image_data["loaded"] = True
            
        except Exception as img_err:
            card.image_label.configure(text="[预览加载失败]")

    def _update_stats(self):
        """更新统计信息"""
        self.image_count_label.configure(text=f"图片总数: {len(self.images)}")
        if self.images:
            last_upload = max(img["date"] for img in self.images)
            self.last_upload_label.configure(text=f"最后上传: {last_upload}")
        else:
            self.last_upload_label.configure(text="最后上传: 无")

    def _search_images(self):
        """搜索图片"""
        keyword = self.search_entry.get().lower()
        if not keyword:
            return
            
        count = 0
        for widget in self.image_grid_frame.winfo_children():
            if hasattr(widget, "image_data"):
                img_name = widget.image_data["name"].lower()
                if keyword in img_name:
                    widget.grid()
                    count += 1
                else:
                    widget.grid_remove()
        
        self._update_status(f"找到 {count} 张匹配图片")

    def _clear_search(self):
        """清除搜索"""
        self.search_entry.delete(0, "end")
        for widget in self.image_grid_frame.winfo_children():
            if hasattr(widget, "image_data"):
                widget.grid()
        self._update_status("已清除搜索")

    def _apply_custom_domain(self, url):
        """应用自定义域名"""
        if not self.config.get("custom_domain"):
            return url
            
        try:
            # 从原始URL中提取路径
            parsed = urlparse(url)
            path = parsed.path
            
            # 移除可能的branch路径 (如/main/)
            if "/main/" in path:
                path = path.split("/main/", 1)[1]
            elif "/master/" in path:
                path = path.split("/master/", 1)[1]
            
            # 组合自定义域名
            return self.config["custom_domain"].rstrip("/") + "/" + path.lstrip("/")
            
        except:
            return url

    def _show_context_menu(self, event):
        """显示右键菜单"""
        widget = event.widget
        while not hasattr(widget, "image_data"):
            widget = widget.master
            if widget is self:
                return
                
        self.current_image = widget.image_data
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _copy_image_url(self):
        """复制图片URL"""
        if self.current_image:
            self.clipboard_clear()
            self.clipboard_append(self.current_image["url"])
            self._log(f"已复制链接: {self.current_image['url']}")

    def _copy_markdown(self):
        """复制Markdown格式"""
        if self.current_image:
            md = f"![{self.current_image['name']}]({self.current_image['url']})"
            self.clipboard_clear()
            self.clipboard_append(md)
            self._log(f"已复制Markdown: {md}")

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log(f"已复制: {text[:50]}...")

    def _preview_image(self, image_url=None):
        """现代化图片预览窗口"""
        url = image_url or (self.current_image["raw_url"] if self.current_image else None)
        if not url:
            return
            
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(io.BytesIO(response.content))
            
            preview = ctk.CTkToplevel(self)
            preview.title(f"图片预览 - {os.path.basename(url)}")
            preview.attributes("-topmost", True)
            
            # 计算适合窗口的大小
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            img_width, img_height = img.size
            
            max_width = min(img_width, screen_width * 0.8)
            max_height = min(img_height, screen_height * 0.8)
            
            ratio = min(max_width/img_width, max_height/img_height)
            display_size = (int(img_width*ratio), int(img_height*ratio))
            
            img = img.resize(display_size, Image.LANCZOS)
            photo = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=display_size
            )
            
            # 主容器
            container = ctk.CTkFrame(preview)
            container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # 图片显示
            img_label = ctk.CTkLabel(
                container,
                image=photo,
                text=""
            )
            img_label.image = photo
            img_label.pack(expand=True)
            
            # 底部工具栏
            toolbar = ctk.CTkFrame(container)
            toolbar.pack(fill="x", pady=(10, 0))
            
            ctk.CTkButton(
                toolbar,
                text="复制链接",
                width=80,
                command=lambda: self._copy_to_clipboard(url)
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                toolbar,
                text="下载",
                width=80,
                command=lambda: self._download_image(url)
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                toolbar,
                text="关闭",
                width=80,
                command=preview.destroy
            ).pack(side="right", padx=5)
            
            # 居中窗口
            preview.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() - preview.winfo_width()) // 2
            y = self.winfo_y() + (self.winfo_height() - preview.winfo_height()) // 2
            preview.geometry(f"+{x}+{y}")
            
        except Exception as e:
            messagebox.showerror("预览失败", str(e))

    def _download_image(self, url):
        """下载图片到本地"""
        try:
            filename = os.path.basename(url)
            save_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".*",
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.gif")]
            )
            if save_path:
                response = requests.get(url, stream=True)
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                self._log(f"图片已保存到: {save_path}")
        except Exception as e:
            messagebox.showerror("下载失败", str(e))

    def _delete_image(self):
        """删除图片"""
        if not self.current_image:
            return
            
        if not messagebox.askyesno(
            "确认删除",
            f"确定要永久删除 {self.current_image['name']} 吗？\n此操作不可撤销！"
        ):
            return
            
        try:
            if GitHubImageManager.delete_image(self.current_image["raw_url"], self.config):
                self._log(f"已删除: {self.current_image['name']}")
                self.refresh_images()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))

    def _open_settings(self):
        """打开设置窗口"""
        settings = ctk.CTkToplevel(self)
        settings.title("设置")
        settings.geometry("500x700")
        settings.transient(self)
        settings.grab_set()
        
        # 顶部关于按钮容器
        top_bar = ctk.CTkFrame(settings, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkButton(
            top_bar,
            text="关于",
            width=80,
            height=28,
            fg_color="transparent",
            border_width=1,
            font=ctk.CTkFont(size=12),
            command=self._show_about
        ).pack(side="right")

        # 表单框架
        form_frame = ctk.CTkFrame(settings)
        form_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 配置字段
        fields = [
            ("GitHub访问令牌", "token", True, "在GitHub设置的Developer settings中创建"),
            ("仓库名称", "repo", True, "格式: 用户名/仓库名"),
            ("存储路径", "path", False, "可选，如: images/2023"),
            ("分支名称", "branch", False, "默认为main"),
            ("自定义域名", "custom_domain", False, "如: https://cdn.example.com")
        ]
        
        entries = {}
        for i, (label, key, required, hint) in enumerate(fields):
            frame = ctk.CTkFrame(form_frame)
            frame.pack(fill="x", pady=5)
            
            label = ctk.CTkLabel(
                frame,
                text=f"{label}{'*' if required else ''}:",
                width=120,
                anchor="e"
            )
            label.grid(row=0, column=0, padx=5)
            
            entry = ctk.CTkEntry(frame)
            entry.insert(0, self.config.get(key, ""))
            entry.grid(row=0, column=1, sticky="ew", padx=5)
            
            hint_label = ctk.CTkLabel(
                frame,
                text=hint,
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "gray40")
            )
            hint_label.grid(row=1, column=1, sticky="w", padx=5)
            
            form_frame.columnconfigure(1, weight=1)
            entries[key] = entry
        
        # 高级设置
        advanced_frame = ctk.CTkFrame(form_frame)
        advanced_frame.pack(fill="x", pady=(20, 5))
        
        ctk.CTkLabel(
            advanced_frame,
            text="高级设置",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 10))
        
        # 懒加载开关
        lazy_frame = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        lazy_frame.pack(fill="x", pady=5)
        
        lazy_switch = ctk.CTkSwitch(
            lazy_frame,
            text="启用懒加载",
            command=lambda: self._toggle_lazyload()
        )
        lazy_switch.select() if self.lazyload_enabled else lazy_switch.deselect()
        lazy_switch.pack(side="left", padx=5)
        
        # 批量大小
        batch_frame = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        batch_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            batch_frame,
            text="每批加载数量:",
            width=120,
            anchor="e"
        ).pack(side="left", padx=5)
        
        batch_entry = ctk.CTkEntry(batch_frame, width=60)
        batch_entry.insert(0, str(self.dynamic_batch_size))
        batch_entry.pack(side="left", padx=5)
        
        # 主题设置
        theme_frame = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        theme_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            theme_frame,
            text="主题模式:",
            width=120,
            anchor="e"
        ).pack(side="left", padx=5)
        
        theme_option = ctk.CTkOptionMenu(
            theme_frame,
            values=["System", "Light", "Dark"],
            command=self._set_theme_mode
        )
        theme_option.set(self.config.get("theme_mode", "System"))
        theme_option.pack(side="left", padx=5)
        
        # 保存按钮
        def save_settings():
            for key, entry in entries.items():
                self.config[key] = entry.get().strip()
            
            # 保存高级设置
            self.lazyload_enabled = lazy_switch.get()
            self.dynamic_batch_size = max(1, int(batch_entry.get()))
            self.config.update({
                "lazyload_enabled": self.lazyload_enabled,
                "dynamic_batch_size": self.dynamic_batch_size,
                "theme_mode": theme_option.get()
            })
            
            self._save_config()
            self._log("配置已保存")
            settings.destroy()
            self.refresh_images()
        
        ctk.CTkButton(
            settings,
            text="💾 保存设置",
            command=save_settings,
            height=40,
            font=ctk.CTkFont(size=14)
        ).pack(pady=20)

    def _toggle_lazyload(self):
        """切换懒加载状态"""
        self.lazyload_enabled = not self.lazyload_enabled
        self._log(f"懒加载 {'已启用' if self.lazyload_enabled else '已禁用'}")

    def _set_theme_mode(self, mode):
        """设置主题模式"""
        self.config["theme_mode"] = mode
        ctk.set_appearance_mode(mode)
        self._log(f"主题已切换为: {mode}")

    def _log(self, message):
        """记录日志"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'log_area'):
                self.log_area.insert("end", f"[{timestamp}] {message}\n")
                self.log_area.see("end")
                self.log_area.update()
            else:
                print(f"[{timestamp}] {message}")  # Fallback to console
        except Exception as e:
            print(f"Logging error: {str(e)}")

    def _update_status(self, message):
        """更新状态栏"""
        self.status_label.configure(text=message)

    def _show_progress(self, show=True):
        """显示/隐藏进度条"""
        if show:
            self.progress_bar.start()
            self.progress_bar.pack(side="right", padx=15)
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()

    def _show_about(self):
        """显示关于信息"""
        webbrowser.open("https://blog.fengmayou.top")


if __name__ == "__main__":
    # Windows高DPI适配
    if os.name == "nt":
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
    
    app = ModernImageUploader()
    app.mainloop()