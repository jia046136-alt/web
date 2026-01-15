import os
import sys
import time
import json
import threading
import ctypes
import re
import winreg
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# ================= 0. 核心工具: 资源路径定位器 =================
def resource_path(relative_path):
    """获取资源的绝对路径 (核心修复: 解决打包后找不到文件的问题)"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================= 全局配置 =================
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")
CONFIG_FILE = "config.json"
APP_REGISTRY_NAME = "WeiboSuperTopicAutoSignV3Pro"

# ================= 模块1: 电源管理 =================
class PowerManagement:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    VK_LWIN = 0x5B
    VK_X = 0x58
    VK_U = 0x55
    VK_S = 0x53
    KEYEVENTF_KEYUP = 0x0002

    @staticmethod
    def prevent_sleep():
        """阻止系统休眠"""
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                PowerManagement.ES_CONTINUOUS | 
                PowerManagement.ES_SYSTEM_REQUIRED | 
                PowerManagement.ES_DISPLAY_REQUIRED
            )
        except: pass

    @staticmethod
    def allow_sleep():
        """允许系统休眠"""
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(PowerManagement.ES_CONTINUOUS)
        except: pass

    @staticmethod
    def execute_sleep_macro():
        """物理强制休眠宏"""
        ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, 0, 0)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, 0, 0)
        time.sleep(0.2)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_LWIN, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_X, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        time.sleep(1.0)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_U, 0, 0, 0)
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_U, 0, PowerManagement.KEYEVENTF_KEYUP, 0)
        time.sleep(0.5)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_S, 0, 0, 0)
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(PowerManagement.VK_S, 0, PowerManagement.KEYEVENTF_KEYUP, 0)

# ================= 模块2: 安全睡眠弹窗 =================
class SafetySleepWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_cancel, on_timeout):
        super().__init__(parent)
        self.on_cancel = on_cancel
        self.on_timeout = on_timeout
        self.remaining_time = 60
        self.is_running = True
        self.title("准备待机")
        self.geometry("420x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        try: self.after(200, lambda: self.iconbitmap(resource_path("logo.ico")))
        except: pass

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 420) // 2
        y = (screen_height - 250) // 2
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.cancel_sleep)

        self.label_status = ctk.CTkLabel(self, text="✅ 任务完成，准备待机", font=("Microsoft YaHei", 20, "bold"), text_color="#2E8B57")
        self.label_status.pack(pady=(30, 10))
        self.label_timer = ctk.CTkLabel(self, text=f"⏳ {self.remaining_time} 秒后进入睡眠...", font=("Microsoft YaHei", 16))
        self.label_timer.pack(pady=10)
        self.btn_cancel = ctk.CTkButton(self, text="🚫 取消 (我在用电脑)", fg_color="#FF6347", hover_color="#CD5C5C", width=200, height=45, font=("Microsoft YaHei", 14, "bold"), command=self.cancel_sleep)
        self.btn_cancel.pack(pady=20)
        self.timer_loop()

    def timer_loop(self):
        if not self.is_running: return
        if self.remaining_time > 0:
            self.label_timer.configure(text=f"⏳ {self.remaining_time} 秒后进入睡眠...")
            self.remaining_time -= 1
            self.after(1000, self.timer_loop)
        else:
            self.is_running = False
            self.destroy()
            self.on_timeout()

    def cancel_sleep(self):
        self.is_running = False
        self.destroy()
        self.on_cancel()

# ================= 模块3: 主程序逻辑 =================
class WeiboCheckInApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        try:
            myappid = 'yuanjia.weibo.helper.v3.3.final'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except: pass

        self.title("微博超话助手 V3.3 Pro+")
        self.geometry("800x780") # 稍微调高一点高度以容纳新开关
        
        try:
            icon_path = resource_path("logo.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Icon Error: {e}")
        
        self.config = self.load_config()
        self.is_running = False
        self.tray_icon = None
        self.row_widgets = [] 

        self.setup_ui()
        self.load_rows_from_config()
        self.sync_registry_switch()
        
        # [核心] 启动时根据配置决定是否应用防休眠
        self.update_power_state()

        self.monitor_thread = threading.Thread(target=self.smart_monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    def load_config(self):
        default_config = {
            "targets": [], 
            "auto_sleep": False, 
            "prevent_sleep": True, # 任务运行时防休眠
            "keep_awake_global": False, # [新增] 全局防休眠
            "auto_start": False, 
            "visible_mode": False, 
            "last_checkin_date": "1970-01-01"
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 兼容性处理
                    if "target_urls" in data:
                        old_urls = re.findall(r'http[s]?://[^\s]+', data["target_urls"])
                        data["targets"] = [{"url": u, "note": "旧数据"} for u in old_urls]
                        del data["target_urls"]
                    return {**default_config, **data}
            except: pass
        return default_config

    def save_config(self):
        current_targets = []
        for row in self.row_widgets:
            u = row["url_entry"].get().strip()
            n = row["note_entry"].get().strip()
            if u: current_targets.append({"url": u, "note": n})
        self.config["targets"] = current_targets
        self.config["auto_sleep"] = self.switch_sleep.get()
        self.config["prevent_sleep"] = self.switch_prevent_sleep.get()
        self.config["keep_awake_global"] = self.switch_keep_awake_global.get() # 保存新开关
        self.config["visible_mode"] = self.switch_visible.get()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
        return len(current_targets)

    # [新增] 统一的电源状态管理
    def update_power_state(self):
        """根据当前开关状态和运行状态，决定是否阻止休眠"""
        global_awake = self.switch_keep_awake_global.get()
        task_awake = self.is_running and self.switch_prevent_sleep.get()
        
        if global_awake:
            PowerManagement.prevent_sleep()
            if not self.is_running:
                self.status_indicator.configure(text="● ⚡ 待机中 (始终保持唤醒)", text_color="#FF8C00")
        elif task_awake:
            PowerManagement.prevent_sleep()
            self.status_indicator.configure(text="● ⚡ 运行中 (高性能防休眠)", text_color="#FF8C00")
        else:
            PowerManagement.allow_sleep()
            if self.is_running:
                self.status_indicator.configure(text="● ▶️ 运行中", text_color="#17a2b8")
            else:
                self.status_indicator.configure(text="● ✅ 系统就绪", text_color="#28a745")

    def setup_ui(self):
        # Header
        self.frame_banner = ctk.CTkFrame(self, fg_color="#E02020", corner_radius=0, height=80)
        self.frame_banner.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.frame_banner, text="Weibo Check-In Pro", font=("Arial Black", 22), text_color="white").pack(side="left", padx=25, pady=20)
        ctk.CTkLabel(self.frame_banner, text="稳定 · 智能 · 可视化", font=("Microsoft YaHei", 12, "bold"), text_color="#FFD1D1").pack(side="right", padx=25, pady=20)

        # 状态灯
        self.frame_status = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_status.pack(padx=20, fill="x", pady=(0, 5))
        self.status_indicator = ctk.CTkLabel(self.frame_status, text="● 系统就绪", font=("Microsoft YaHei", 12, "bold"), text_color="#28a745")
        self.status_indicator.pack(side="left", padx=5)

        # 操作栏
        self.frame_actions = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_actions.pack(padx=20, pady=5, fill="x")
        self.btn_add = ctk.CTkButton(self.frame_actions, text="➕ 新增超话", width=120, fg_color="transparent", border_width=2, border_color="#555", text_color="#333", hover_color="#eee", command=lambda: self.add_row_ui())
        self.btn_add.pack(side="left", padx=(0, 10))
        self.btn_save = ctk.CTkButton(self.frame_actions, text="💾 保存配置", width=120, fg_color="#6c757d", hover_color="#5a6268", command=self.manual_save)
        self.btn_save.pack(side="left")

        # 列表
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="任务列表", height=240, label_font=("Microsoft YaHei", 12, "bold"))
        self.scroll_frame.pack(padx=20, pady=10, fill="x")

        # 开关区域 (重新布局以容纳新开关)
        self.frame_switches = ctk.CTkFrame(self)
        self.frame_switches.pack(pady=5, padx=20, fill="x")
        
        # 行1
        self.frame_sw1 = ctk.CTkFrame(self.frame_switches, fg_color="transparent")
        self.frame_sw1.pack(fill="x", pady=2)
        self.switch_autostart = ctk.CTkSwitch(self.frame_sw1, text="开机自启", command=self.toggle_autostart)
        self.switch_autostart.pack(side="left", padx=20)
        self.switch_sleep = ctk.CTkSwitch(self.frame_sw1, text="任务完成后自动待机")
        self.switch_sleep.pack(side="left", padx=20)
        if self.config.get("auto_sleep"): self.switch_sleep.select()

        # 行2
        self.frame_sw2 = ctk.CTkFrame(self.frame_switches, fg_color="transparent")
        self.frame_sw2.pack(fill="x", pady=2)
        self.switch_prevent_sleep = ctk.CTkSwitch(self.frame_sw2, text="任务运行时保持唤醒", command=self.update_power_state)
        self.switch_prevent_sleep.pack(side="left", padx=20)
        if self.config.get("prevent_sleep", True): self.switch_prevent_sleep.select()
        
        self.switch_visible = ctk.CTkSwitch(self.frame_sw2, text="显示浏览器 (调试用)")
        self.switch_visible.pack(side="left", padx=20)
        if self.config.get("visible_mode"): self.switch_visible.select()

        # 行3 (新功能)
        self.frame_sw3 = ctk.CTkFrame(self.frame_switches, fg_color="transparent")
        self.frame_sw3.pack(fill="x", pady=2)
        self.switch_keep_awake_global = ctk.CTkSwitch(self.frame_sw3, text="🛡️ 软件运行时始终保持唤醒 (挂机推荐)", font=("Microsoft YaHei", 12, "bold"), text_color="#E02020", command=self.update_power_state)
        self.switch_keep_awake_global.pack(side="left", padx=20)
        if self.config.get("keep_awake_global", False): self.switch_keep_awake_global.select()

        # 日志
        self.textbox_log = ctk.CTkTextbox(self, height=100, font=("Consolas", 10), fg_color="#f8f9fa", text_color="#333", border_width=1, border_color="#ddd")
        self.textbox_log.pack(pady=5, padx=20, fill="both", expand=True)
        self.btn_run = ctk.CTkButton(self, text="🚀 立即启动", height=45, font=("Microsoft YaHei", 15, "bold"), fg_color="#E02020", hover_color="#B01010", command=lambda: threading.Thread(target=self.manual_run).start())
        self.btn_run.pack(pady=15, padx=20, fill="x")

    def add_row_ui(self, url="", note=""):
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        entry_url = ctk.CTkEntry(row_frame, placeholder_text="粘贴超话链接...", width=380)
        entry_url.pack(side="left", padx=(0, 5), fill="x", expand=True)
        if url: entry_url.insert(0, url)
        entry_note = ctk.CTkEntry(row_frame, placeholder_text="备注", width=120)
        entry_note.pack(side="left", padx=(0, 5))
        if note: entry_note.insert(0, note)
        btn_del = ctk.CTkButton(row_frame, text="🗑️", width=40, fg_color="#dc3545", hover_color="#c82333", command=lambda: self.delete_row_ui(row_frame))
        btn_del.pack(side="left")
        self.row_widgets.append({"frame": row_frame, "url_entry": entry_url, "note_entry": entry_note})

    def delete_row_ui(self, frame_obj):
        for item in self.row_widgets:
            if item["frame"] == frame_obj:
                item["frame"].destroy()
                self.row_widgets.remove(item)
                break

    def load_rows_from_config(self):
        targets = self.config.get("targets", [])
        if not targets: self.add_row_ui()
        for t in targets: self.add_row_ui(t.get("url", ""), t.get("note", ""))
        self.log_msg(f"📂 已加载 {len(targets)} 个任务")

    def manual_save(self):
        count = self.save_config()
        self.log_msg(f"💾 配置保存成功: {count} 个任务")

    def sync_registry_switch(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_REGISTRY_NAME)
            self.switch_autostart.select()
            self.config["auto_start"] = True
            winreg.CloseKey(key)
        except:
            self.switch_autostart.deselect()
            self.config["auto_start"] = False

    def toggle_autostart(self):
        is_on = self.switch_autostart.get()
        app_path = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if is_on:
                winreg.SetValueEx(key, APP_REGISTRY_NAME, 0, winreg.REG_SZ, app_path)
                self.log_msg("✅ 开机自启：已开启")
            else:
                try: winreg.DeleteValue(key, APP_REGISTRY_NAME)
                except: pass
                self.log_msg("❎ 开机自启：已关闭")
            winreg.CloseKey(key)
            self.config["auto_start"] = is_on
            self.save_config()
        except Exception as e:
            self.log_msg(f"❌ 注册表错误: {e}")
            self.switch_autostart.toggle()

    def smart_monitor_loop(self):
        time.sleep(3)
        self.log_msg("🛡️ 智能监测服务启动")
        while True:
            try:
                today = time.strftime("%Y-%m-%d")
                last_date = self.config.get("last_checkin_date", "1970-01-01")
                if today != last_date:
                    self.log_msg(f"📅 新的一天 ({today})，准备开始...")
                    time.sleep(10)
                    if self.execute_batch_task():
                        self.log_msg("🎉 自动任务全部成功")
                        self.config["last_checkin_date"] = today
                        self.save_config()
                        if self.switch_sleep.get():
                            self.after(0, self.trigger_safety_sleep)
                    else:
                        self.log_msg("⚠️ 任务未全通，30分钟后重试...")
                        time.sleep(1800)
                        continue
                time.sleep(60)
            except Exception as e:
                self.log_msg(f"监测异常: {e}")
                time.sleep(60)

    def manual_run(self):
        self.save_config()
        self.log_msg("🔧 手动任务启动...")
        if self.execute_batch_task():
            today = time.strftime("%Y-%m-%d")
            self.config["last_checkin_date"] = today
            self.save_config()
            self.log_msg("✅ 手动执行完成")
            if self.switch_sleep.get():
                self.after(0, self.trigger_safety_sleep)

    def execute_batch_task(self):
        if self.is_running:
            self.log_msg("⚠️ 任务运行中，请勿重复操作")
            return False
        
        self.is_running = True
        
        # [修改] 使用统一的状态管理器
        self.update_power_state()

        targets = self.config.get("targets", [])
        if not targets:
            self.log_msg("❌ 任务列表为空")
            self.is_running = False
            self.update_power_state() # 恢复状态
            return False
            
        self.log_msg(f"📋 队列任务数: {len(targets)}")
        driver = None
        all_success = True
        
        try:
            options = Options()
            if not self.switch_visible.get():
                options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--log-level=3")
            options.add_argument("--mute-audio")
            user_data = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data')
            options.add_argument(f"--user-data-dir={user_data}")
            options.add_argument("--profile-directory=Default")
            
            try: service = Service(EdgeChromiumDriverManager().install())
            except: 
                self.log_msg("⚠️ 驱动联网获取失败，使用本地默认...")
                service = Service()
            
            service.creation_flags = 0x08000000 
            driver = webdriver.Edge(service=service, options=options)
            
            for i, item in enumerate(targets):
                url = item.get("url", "")
                note = item.get("note", "未知")
                if not url: continue
                self.log_msg(f"👉 [{i+1}/{len(targets)}] {note}")
                try:
                    driver.get(url)
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(2)
                    xpath = "//a[contains(text(),'签到')] | //div[contains(text(),'签到')] | //span[contains(text(),'签到')]"
                    btns = driver.find_elements(By.XPATH, xpath)
                    clicked = False
                    for btn in btns:
                        txt = btn.text
                        if "已" not in txt and "等级" not in txt and btn.is_displayed():
                            driver.execute_script("arguments[0].click();", btn)
                            self.log_msg(f"   🖱️ 签到成功")
                            clicked = True
                            time.sleep(2)
                            break
                    if not clicked:
                        if "已签" in driver.page_source: self.log_msg(f"   ℹ️ 今日已签")
                        else: self.log_msg(f"   ⚠️ 未找到按钮")
                except Exception as e:
                    self.log_msg(f"   ❌ 错误: {str(e)[:30]}")
                    all_success = False
                time.sleep(1)
        except Exception as e:
            self.log_msg(f"❌ 浏览器错误: {e}")
            all_success = False
        finally:
            if driver: driver.quit()
            self.is_running = False
            # [修改] 任务结束，调用状态管理器恢复状态
            # (如果全局开关开着，它会继续防睡；如果全局关着，它会允许睡)
            self.update_power_state()
            
        return all_success

    def trigger_safety_sleep(self):
        SafetySleepWindow(self, lambda: self.log_msg("👋 用户中止待机"), lambda: PowerManagement.execute_sleep_macro())

    def log_msg(self, msg):
        full_msg = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        self.textbox_log.insert("end", full_msg)
        self.textbox_log.see("end")

    def hide_to_tray(self):
        self.withdraw()
        if not self.tray_icon: self.create_tray_icon()

    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()

    def quit_app(self, icon, item):
        self.save_config()
        self.tray_icon.stop()
        self.destroy()
        sys.exit()

    def create_tray_icon(self):
        try:
            icon_path = resource_path("logo.ico")
            image = Image.open(icon_path)
        except:
            image = Image.new('RGB', (64, 64), color=(224, 32, 32))
            draw = ImageDraw.Draw(image)
            draw.rectangle((16, 16, 48, 48), fill="white")
        menu = (pystray.MenuItem('显示主界面', self.show_window, default=True), pystray.MenuItem('退出', self.quit_app))
        self.tray_icon = pystray.Icon("weibo_helper_v3_3", image, "微博助手", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

if __name__ == "__main__":
    try:
        myappid = 'yuanjia.weibo.helper.v3.3.final'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except: pass
    app = WeiboCheckInApp()
    app.mainloop()