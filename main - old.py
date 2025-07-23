import os
import json
import threading
import requests
import base64
import re
from datetime import datetime
from tkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog
from urllib.parse import quote, urlparse
from enum import Enum, auto
import io

CONFIG_FILE = "config.json"

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class SortMode(Enum):
    NAME_ASC = auto()
    NAME_DESC = auto()
    DATE_ASC = auto()
    DATE_DESC = auto()

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class GitHubImageUploader(Tk):
    def __init__(self):
        super().__init__()
        self.title("GitHub图床管理器")
        self.geometry("900x600")
        self.config_data = load_config()
        self.sort_mode = SortMode.DATE_DESC
        self.images_data = []
        self.current_selected_image = None
        
        self.create_widgets()
        self.refresh_image_previews()
        self.apply_theme()

    def create_widgets(self):
        # 主容器
        main_frame = Frame(self)
        main_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # 顶部控制栏
        control_frame = Frame(main_frame)
        control_frame.pack(fill=X, pady=5)
        
        # 操作按钮
        btn_frame = Frame(control_frame)
        btn_frame.pack(side=LEFT)
        Button(btn_frame, text="上传图片", command=self.select_files).pack(side=LEFT, padx=2)
        Button(btn_frame, text="设置", command=self.open_settings).pack(side=LEFT, padx=2)
        Button(btn_frame, text="刷新", command=self.refresh_image_previews).pack(side=LEFT, padx=2)
        
        # 排序选项
        sort_frame = Frame(control_frame)
        sort_frame.pack(side=LEFT, padx=10)
        Label(sort_frame, text="排序:").pack(side=LEFT)
        
        self.sort_var = StringVar()
        self.sort_var.set("日期 ▼")
        sort_options = ["名称 ▲", "名称 ▼", "日期 ▲", "日期 ▼"]
        sort_menu = OptionMenu(sort_frame, self.sort_var, *sort_options, command=self.change_sort_mode)
        sort_menu.pack(side=LEFT)
        
        # 搜索框
        search_frame = Frame(control_frame)
        search_frame.pack(side=RIGHT)
        Label(search_frame, text="搜索:").pack(side=LEFT)
        self.search_entry = Entry(search_frame, width=25)
        self.search_entry.pack(side=LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.search_images)
        Button(search_frame, text="清除", command=self.clear_search).pack(side=LEFT, padx=2)
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, orient=HORIZONTAL, length=300, mode="determinate")
        self.progress.pack(pady=5)
        
        # 日志区域
        log_frame = Frame(main_frame)
        log_frame.pack(fill=X, padx=5, pady=5)
        self.text = Text(log_frame, height=5)
        scrollbar = Scrollbar(log_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # 图片展示区域
        image_container = Frame(main_frame)
        image_container.pack(fill=BOTH, expand=True)
        
        self.image_canvas = Canvas(image_container, bd=0, highlightthickness=0)
        self.scrollbar = Scrollbar(image_container, orient=VERTICAL, command=self.image_canvas.yview)
        self.image_frame = Frame(self.image_canvas)
        
        self.image_frame.bind(
            "<Configure>",
            lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))
        
        self.window_id = self.image_canvas.create_window((0, 0), window=self.image_frame, anchor="nw")
        self.image_canvas.bind("<Configure>", self.on_canvas_configure)
        self.image_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.image_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        
        # 拖放区域 (宽度与窗口一致)
        self.drop_area = Frame(self.image_frame, bd=2, relief=SOLID)
        self.drop_area.pack(fill=X, padx=10, pady=10)
        
        Label(self.drop_area, 
             text="拖放图片文件到这里\n(或点击选择文件)",
             padx=50,
             pady=50,
             cursor="hand2").pack(expand=True)
        
        self.drop_area.bind("<Button-1>", self.select_files)
        
        # 右键菜单
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="复制链接", command=self.copy_image_url)
        self.context_menu.add_command(label="复制Markdown", command=self.copy_image_markdown)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="重命名", command=self.rename_image)
        self.context_menu.add_command(label="删除", command=self.delete_image)
        
        # 绑定鼠标滚轮滚动
        self.image_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # 底部状态栏或操作按钮区
        bottom_frame = Frame(main_frame)
        bottom_frame.pack(fill=X, pady=5, anchor=SE)

        Button(bottom_frame, text="关于", command=self.show_about).pack(side=RIGHT, padx=5)


    def on_mousewheel(self, event):
        self.image_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_canvas_configure(self, event):
        self.image_canvas.itemconfig(self.window_id, width=event.width)

    def change_sort_mode(self, mode_str):
        if mode_str == "名称 ▲":
            self.sort_mode = SortMode.NAME_ASC
        elif mode_str == "名称 ▼":
            self.sort_mode = SortMode.NAME_DESC
        elif mode_str == "日期 ▲":
            self.sort_mode = SortMode.DATE_ASC
        elif mode_str == "日期 ▼":
            self.sort_mode = SortMode.DATE_DESC
        self.display_images()

    def search_images(self, event=None):
        search_term = self.search_entry.get().lower()
        if not search_term:
            self.display_images()
            return
            
        filtered = [img for img in self.images_data if search_term in img["name"].lower()]
        self.display_images(filtered)

    def clear_search(self):
        self.search_entry.delete(0, END)
        self.display_images()

    def display_images(self, images_data=None):
        if images_data is None:
            images_data = self.images_data
            
        for widget in self.image_frame.winfo_children():
            if widget != self.drop_area:
                widget.destroy()
        
        if not images_data:
            return
            
        if self.sort_mode == SortMode.NAME_ASC:
            images_data.sort(key=lambda x: x["name"].lower())
        elif self.sort_mode == SortMode.NAME_DESC:
            images_data.sort(key=lambda x: x["name"].lower(), reverse=True)
        elif self.sort_mode == SortMode.DATE_ASC:
            images_data.sort(key=lambda x: x["date"])
        elif self.sort_mode == SortMode.DATE_DESC:
            images_data.sort(key=lambda x: x["date"], reverse=True)
        
        row_frame = None
        for i, img_data in enumerate(images_data):
            if i % 4 == 0:
                row_frame = Frame(self.image_frame)
                row_frame.pack(fill=X, pady=5)
            
            self.create_image_preview(row_frame, img_data)

    def create_image_preview(self, parent_frame, img_data):
        frame = Frame(parent_frame, bd=1, relief=SOLID, padx=5, pady=5)
        frame.pack(side=LEFT, padx=5)
        
        if PIL_AVAILABLE and img_data.get("photo"):
            img_label = Label(frame, image=img_data["photo"])
            img_label.image = img_data["photo"]
            img_label.pack()
        
        name_label = Label(frame, text=img_data["name"], wraplength=150)
        name_label.pack()
        
        frame.url = img_data["display_url"]
        frame.raw_url = img_data["raw_url"]
        frame.name = img_data["name"]
        frame.img_data = img_data
        
        frame.bind("<Button-3>", self.show_context_menu)
        if PIL_AVAILABLE:
            img_label.bind("<Button-3>", self.show_context_menu)
        name_label.bind("<Button-3>", self.show_context_menu)
        
        frame.bind("<Button-1>", lambda e: self.copy_image_markdown(img_data["display_url"], img_data["name"]))
        if PIL_AVAILABLE:
            img_label.bind("<Button-1>", lambda e: self.copy_image_markdown(img_data["display_url"], img_data["name"]))
        name_label.bind("<Button-1>", lambda e: self.copy_image_markdown(img_data["display_url"], img_data["name"]))

    def refresh_image_previews(self):
        self.images_data = []
        
        for widget in self.image_frame.winfo_children():
            if widget != self.drop_area:
                widget.destroy()
                
        try:
            raw_urls = github_list_images(self.config_data)
            
            for raw_url in raw_urls:
                display_url = replace_domain(raw_url, self.config_data.get("custom_domain", ""))
                filename = os.path.basename(raw_url)
                
                img_data = {
                    "name": filename,
                    "display_url": display_url,
                    "raw_url": raw_url,
                    "date": datetime.now(),
                    "photo": None
                }
                
                if PIL_AVAILABLE:
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        response = requests.get(raw_url, headers=headers, stream=True, timeout=5)
                        
                        if response.status_code == 200:
                            img = Image.open(io.BytesIO(response.content))
                            img.thumbnail((150, 150))
                            img_data["photo"] = ImageTk.PhotoImage(img)
                    except Exception as e:
                        self.log(f"图片预览失败: {filename} -> {str(e)}")
                
                self.images_data.append(img_data)
            
            self.display_images()
                    
        except Exception as e:
            self.log(f"远程加载失败: {str(e)}")

    def select_files(self, event=None):
        files = filedialog.askopenfilenames(
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp")])
        if files:
            self.upload_files(files)

    def upload_files(self, files):
        def run():
            total = len(files)
            self.progress["maximum"] = total
            self.progress["value"] = 0

            start_time = datetime.now()

            for index, filepath in enumerate(files):
                filename = os.path.basename(filepath)
                self.log(f"[{index+1}/{total}] 开始上传: {filename}")
                try:
                    path = self.config_data.get("path", "").strip("/")
                    upload_path = f"{path}/{filename}" if path else filename
                    self.log(f"上传路径: {upload_path}")
                    
                    raw_url = github_upload(filepath, self.config_data)
                    display_url = replace_domain(raw_url, self.config_data.get("custom_domain", ""))
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = round((index + 1) / elapsed, 2) if elapsed > 0 else 0
                    self.log(f"上传成功: {display_url} [速度: {speed} 张/秒]")
                    
                    img_data = {
                        "name": filename,
                        "display_url": display_url,
                        "raw_url": raw_url,
                        "date": datetime.now(),
                        "photo": None
                    }
                    
                    if PIL_AVAILABLE:
                        try:
                            img = Image.open(filepath)
                            img.thumbnail((150, 150))
                            img_data["photo"] = ImageTk.PhotoImage(img)
                        except Exception as e:
                            self.log(f"本地图片预览失败: {filename} -> {str(e)}")
                    
                    self.images_data.append(img_data)
                    
                except Exception as e:
                    self.log(f"上传失败: {filename} -> {str(e)}")
                self.progress["value"] += 1

            self.display_images()

        threading.Thread(target=run, daemon=True).start()

    def show_context_menu(self, event):
        widget = event.widget
        while widget and not hasattr(widget, 'img_data'):
            widget = widget.master
        
        if widget and hasattr(widget, 'img_data'):
            self.current_selected_image = widget
            self.context_menu.post(event.x_root, event.y_root)

    def copy_image_url(self):
        if self.current_selected_image:
            url = self.current_selected_image.url
            self.clipboard_clear()
            self.clipboard_append(url)
            self.log(f"已复制图片链接: {url}")

    def copy_image_markdown(self, url=None, name=None):
        if url is None and self.current_selected_image:
            url = self.current_selected_image.url
            name = self.current_selected_image.name
            
        if url and name:
            markdown = f"![{name}]({url})"
            self.clipboard_clear()
            self.clipboard_append(markdown)
            self.log(f"已复制Markdown: {markdown}")

    def rename_image(self):
        if not self.current_selected_image:
            return

        old_name = self.current_selected_image.name
        new_name = simpledialog.askstring("重命名图片", "输入新的文件名:", initialvalue=old_name)

        if new_name and new_name != old_name:
            # 合规性检查
            if not re.match(r'^[\w\-\.]+$', new_name):
                messagebox.showwarning("非法文件名", "文件名只能包含字母、数字、下划线、短横线和点号。")
                return
            if len(new_name.strip()) == 0:
                messagebox.showwarning("非法文件名", "文件名不能为空或全为空格。")
                return
            if len(new_name) > 255:
                messagebox.showwarning("文件名过长", "文件名不能超过 255 个字符。")
                return

            try:
                self.log(f"开始重命名: {old_name} -> {new_name}")

                new_raw_url = github_rename_image(
                    self.current_selected_image.raw_url, 
                    new_name, 
                    self.config_data
                )

                new_display_url = replace_domain(new_raw_url, self.config_data.get("custom_domain", ""))
                self.log(f"重命名成功，新URL: {new_display_url}")

                self.current_selected_image.name = new_name
                self.current_selected_image.url = new_display_url
                self.current_selected_image.raw_url = new_raw_url
                self.current_selected_image.img_data["name"] = new_name
                self.current_selected_image.img_data["display_url"] = new_display_url
                self.current_selected_image.img_data["raw_url"] = new_raw_url

                for child in self.current_selected_image.winfo_children():
                    if isinstance(child, Label) and not hasattr(child, "image"):
                        child.config(text=new_name)

                self.log(f"重命名成功: {old_name} -> {new_name}")

            except Exception as e:
                messagebox.showerror("重命名失败", str(e))
                self.log(f"重命名失败: {str(e)}")

    def delete_image(self):
        if not self.current_selected_image:
            return
            
        if messagebox.askyesno("确认删除", f"确定要删除图片 '{self.current_selected_image.name}' 吗？"):
            try:
                github_delete_image(self.current_selected_image.raw_url, self.config_data)
                
                self.images_data = [img for img in self.images_data 
                                   if img["raw_url"] != self.current_selected_image.raw_url]
                
                self.current_selected_image.destroy()
                self.log(f"已删除图片: {self.current_selected_image.name}")
                
            except Exception as e:
                messagebox.showerror("删除失败", str(e))
                self.log(f"删除失败: {str(e)}")
#----------------------设置窗口start---------------------------
    def open_settings(self):
        win = Toplevel(self)
        win.title("设置")
        win.geometry("400x480")

        Label(win, text="GitHub Token:").pack(anchor=W, padx=10, pady=5)
        token_entry = Entry(win)
        token_entry.pack(fill=X, padx=10)
        token_entry.insert(0, self.config_data.get("token", ""))

        Label(win, text="仓库名 (user/repo):").pack(anchor=W, padx=10, pady=5)
        repo_entry = Entry(win)
        repo_entry.pack(fill=X, padx=10)
        repo_entry.insert(0, self.config_data.get("repo", ""))

        Label(win, text="上传路径 (相对于仓库根目录):").pack(anchor=W, padx=10, pady=5)
        path_entry = Entry(win)
        path_entry.pack(fill=X, padx=10)
        path_entry.insert(0, self.config_data.get("path", ""))

        Label(win, text="自定义域名 (可选):").pack(anchor=W, padx=10, pady=5)
        domain_entry = Entry(win)
        domain_entry.pack(fill=X, padx=10)
        domain_entry.insert(0, self.config_data.get("custom_domain", ""))

        Label(win, text="分支 (默认: main):").pack(anchor=W, padx=10, pady=5)
        branch_entry = Entry(win)
        branch_entry.pack(fill=X, padx=10)
        branch_entry.insert(0, self.config_data.get("branch", "main"))

        def save():
            self.config_data["token"] = token_entry.get().strip()
            self.config_data["repo"] = repo_entry.get().strip()
            self.config_data["path"] = path_entry.get().strip()
            self.config_data["custom_domain"] = domain_entry.get().strip()
            self.config_data["branch"] = branch_entry.get().strip() or "main"
            save_config(self.config_data)
            self.log("配置已保存")
            win.destroy()
            self.refresh_image_previews()

        def export_config_json():
            filepath = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON 文件", "*.json")],
                title="导出配置为 JSON"
            )
            if not filepath:
                return
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=4, ensure_ascii=False)
                self.log(f"配置已导出到 {filepath}")
            except Exception as e:
                messagebox.showerror("导出失败", str(e))

        def export_config_qrcode():
            try:
                import qrcode
                from PIL import ImageTk, Image
                config_json = json.dumps(self.config_data, ensure_ascii=False)
                qr = qrcode.make(config_json)

                top = Toplevel(win)
                top.title("配置二维码")

                img = ImageTk.PhotoImage(qr)
                lbl = Label(top, image=img)
                lbl.image = img
                lbl.pack(padx=10, pady=10)

                def save_qr():
                    save_path = filedialog.asksaveasfilename(
                        defaultextension=".png",
                        filetypes=[("PNG 图片", "*.png")],
                        title="保存二维码图片"
                    )
                    if save_path:
                        qr.save(save_path)
                        self.log(f"二维码已保存到 {save_path}")

                Button(top, text="保存二维码为图片", command=save_qr).pack(pady=5)
            except ImportError:
                messagebox.showinfo("二维码库缺失", "未安装 qrcode 库，二维码未生成。")

        def import_config():
            filepath = filedialog.askopenfilename(
                filetypes=[("JSON 文件", "*.json")],
                title="导入配置 JSON"
            )
            if not filepath:
                return
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    new_config = json.load(f)
                self.config_data.update(new_config)
                save_config(self.config_data)
                self.log("配置已导入")
                win.destroy()
                self.refresh_image_previews()
            except Exception as e:
                messagebox.showerror("导入失败", str(e))

        Button(win, text="保存配置", command=save).pack(pady=10)
        Button(win, text="导出配置为 JSON 文件", command=export_config_json).pack(pady=5)
        Button(win, text="导出配置为二维码", command=export_config_qrcode).pack(pady=5)
        Button(win, text="从 JSON 导入配置", command=import_config).pack(pady=5)

#----------------------设置窗口End---------------------------
#----------------------关于start---------------------------
    def show_about(self):
        top = Toplevel(self)
        top.title("关于")
        top.geometry("400x360")
        top.resizable(False, False)

        theme = self.config_data.get("theme", "light")
        bg = "#2e2e2e" if theme == "dark" else "#ffffff"
        fg = "#ffffff" if theme == "dark" else "#000000"
        top.configure(bg=bg)

        # 顶部 logo（可选）
        try:
            from PIL import Image, ImageTk
            logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path).resize((64, 64))
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = Label(top, image=logo_photo, bg=bg)
                logo_label.image = logo_photo
                logo_label.pack(pady=(10, 5))
        except Exception:
            pass

        # 作者头像 + 文字信息
        info_frame = Frame(top, bg=bg)
        info_frame.pack(pady=5)

        try:
            avatar_path = os.path.join(os.path.dirname(__file__), "avatar.jpg")
            if os.path.exists(avatar_path):
                avatar_img = Image.open(avatar_path).resize((48, 48))
                avatar_photo = ImageTk.PhotoImage(avatar_img)
                avatar_label = Label(info_frame, image=avatar_photo, bg=bg)
                avatar_label.image = avatar_photo
                avatar_label.pack(side=LEFT, padx=10)
        except Exception:
            pass

        text_frame = Frame(info_frame, bg=bg)
        text_frame.pack(side=LEFT)
        Label(text_frame, text="GitHub 图床管理器", font=("Arial", 14, "bold"), bg=bg, fg=fg).pack(anchor=W)
        Label(text_frame, text="版本：v1.0", bg=bg, fg=fg).pack(anchor=W)
        Label(text_frame, text="作者：FengJiayou", bg=bg, fg=fg).pack(anchor=W)

        # 简介 + 开源声明
        Label(
            top,
            text="支持拖拽上传、批量上传、配置导入导出、二维码导出等功能。",
            wraplength=320,
            justify=LEFT,
            bg=bg,
            fg=fg
        ).pack(padx=10, pady=(10, 5))

        # 开源声明
        Label(
            top,
            text="本项目遵循 MIT 开源协议，任何人均可自由使用、修改、分发。",
            wraplength=340,
            justify=LEFT,
            bg=bg,
            fg=fg
        ).pack(padx=10, pady=(5, 2))

        # 项目地址（可点击复制）
        import webbrowser
        def copy_repo_url():
            webbrowser.open("https://github.com/fengjiayou/GitHubImageUploader")


        Button(
            top,
            text="访问 GitHub 项目地址",
            command=copy_repo_url,
            bg="#4a90e2" if theme == "light" else "#1f6feb",
            fg="#ffffff",
            relief=FLAT
        ).pack(pady=10)

        def copy_blog_url():
            webbrowser.open("https://blog.fengmayou.top")


        Button(
            top,
            text="访问作者的博客",
            command=copy_blog_url,
            bg="#4a90e2" if theme == "light" else "#1f6feb",
            fg="#ffffff",
            relief=FLAT
        ).pack(pady=10)

#----------------------关于End---------------------------
    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text.insert(END, f"[{timestamp}] {msg}\n")
        self.text.see(END)
        print(msg)

    def apply_theme(self):
        theme = self.config_data.get("theme", "light")
        if theme == "dark":
            bg = "#2e2e2e"
            fg = "#ffffff"
            entry_bg = "#4a4a4a"
            button_bg = "#3a3a3a"
        else:
            bg = "#ffffff"
            fg = "#000000"
            entry_bg = "#ffffff"
            button_bg = "#f0f0f0"
            
        self.configure(bg=bg)
        self.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.image_canvas.configure(bg=bg)
        self.image_frame.configure(bg=bg)
        
        for widget in self.winfo_children():
            if isinstance(widget, Frame):
                widget.configure(bg=bg)
                for child in widget.winfo_children():
                    if isinstance(child, (Label, Button)):
                        child.configure(bg=button_bg, fg=fg)
                    elif isinstance(child, Entry):
                        child.configure(bg=entry_bg, fg=fg)

def replace_domain(url, domain):
    if not domain:
        return url
    parsed = urlparse(url)
    path = parsed.path
    if "/main/" in path:
        path = path.split("/main/", 1)[1]
    return domain.rstrip("/") + "/" + path.lstrip("/")

def github_upload(file_path, config):
    token = config.get("token")
    repo = config.get("repo")
    path = config.get("path", "").strip("/")
    branch = config.get("branch", "main")
    
    if not token or not repo:
        raise ValueError("请先在设置中填写GitHub Token和仓库名")

    filename = os.path.basename(file_path)
    upload_path = f"{path}/{filename}" if path else filename
    
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    url = f"https://api.github.com/repos/{repo}/contents/{upload_path}"
    
    data = {
        "message": f"upload {filename}",
        "content": content,
        "branch": branch
    }
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        return response.json()["content"]["download_url"]
    else:
        error_msg = response.json().get("message", "上传失败")
        if "errors" in response.json():
            error_details = response.json()["errors"][0]["message"]
            error_msg += f" ({error_details})"
        raise Exception(error_msg)

def get_api_path_from_url(url, config):
    match = re.search(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)", url)
    if match:
        return match.groups()[3]
    
    if config.get("custom_domain"):
        domain = config["custom_domain"]
        if url.startswith(domain):
            relative_path = url[len(domain):].lstrip("/")
            if "/main/" in relative_path:
                relative_path = relative_path.split("/main/", 1)[1]
            return relative_path
    
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    if "/main/" in path:
        path = path.split("/main/", 1)[1]
    return path

def github_delete_image(url, config):
    token = config.get("token")
    repo = config.get("repo")
    branch = config.get("branch", "main")
    
    if not token or not repo:
        raise ValueError("请先在设置中填写GitHub Token和仓库名")
    
    file_path = get_api_path_from_url(url, config)
    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {"ref": branch}
    
    response = requests.get(api_url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"获取文件信息失败: {response.status_code}")
    
    sha = response.json().get("sha")
    if not sha:
        raise Exception("无法获取文件SHA值")
    
    data = {
        "message": f"delete {os.path.basename(file_path)}",
        "sha": sha,
        "branch": branch
    }
    response = requests.delete(api_url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"删除失败: {response.status_code}")
    return True

def github_rename_image(old_url, new_name, config):
    token = config.get("token")
    repo = config.get("repo")
    branch = config.get("branch", "main")

    if not token or not repo:
        raise ValueError("请先在设置中填写GitHub Token和仓库名")

    old_path = get_api_path_from_url(old_url, config)
    api_url = f"https://api.github.com/repos/{repo}/contents/{old_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {"ref": branch}

    response = requests.get(api_url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"获取文件信息失败: {response.status_code}")

    file_info = response.json()
    sha = file_info.get("sha")
    content = file_info.get("content")
    encoding = file_info.get("encoding")

    if not sha or not content or not encoding:
        raise Exception("无法获取文件完整信息")

    if encoding == "base64":
        file_content = base64.b64decode(content)
    else:
        raise Exception(f"不支持的编码格式: {encoding}")

    old_dir = os.path.dirname(old_path)
    new_path = f"{old_dir}/{new_name}" if old_dir else new_name

    # 上传新文件
    new_url = f"https://api.github.com/repos/{repo}/contents/{new_path}"
    data = {
        "message": f"rename {os.path.basename(old_path)} to {new_name}",
        "content": base64.b64encode(file_content).decode("utf-8"),
        "branch": branch
    }

    put_resp = requests.put(new_url, headers=headers, json=data)
    if put_resp.status_code not in [200, 201]:
        try:
            error_msg = put_resp.json().get("message", "")
        except:
            error_msg = ""
        raise Exception(f"重命名失败: {put_resp.status_code} {error_msg}")

    # 删除旧文件
    del_data = {
        "message": f"delete old file {os.path.basename(old_path)}",
        "sha": sha,
        "branch": branch
    }
    del_resp = requests.delete(api_url, headers=headers, json=del_data)
    if del_resp.status_code != 200:
        raise Exception(f"重命名成功但删除旧文件失败: {del_resp.status_code}")

    raw_download_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{new_path}"
    return raw_download_url

    
def github_list_images(config):
    token = config.get("token")
    repo = config.get("repo")
    path = config.get("path", "").strip("/")
    branch = config.get("branch", "main")
    
    if not token or not repo:
        raise ValueError("请先在设置中填写GitHub Token和仓库名")

    url = f"https://api.github.com/repos/{repo}/contents/{path}" if path else f"https://api.github.com/repos/{repo}/contents"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {"ref": branch}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        items = response.json()
        if isinstance(items, list):
            return [item["download_url"] for item in items if item["type"] == "file"]
        raise Exception("API返回格式错误，期望列表")
    else:
        error_msg = f"获取远程文件失败: {response.status_code}"
        try:
            error_details = response.json().get("message", "未知错误")
            error_msg += f" - {error_details}"
        except:
            pass
        raise Exception(error_msg)

if __name__ == "__main__":
    app = GitHubImageUploader()
    app.mainloop()