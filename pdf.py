import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QLabel, QLineEdit, QListWidget, 
                             QTextEdit, QGroupBox, QMessageBox, QFileDialog, QSpinBox,
                             QCheckBox, QComboBox)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
import pyautogui
from PIL import Image
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
import time

class CaptureThread(QThread):
    status_update = pyqtSignal(str)
    screenshot_taken = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()
    
    def __init__(self, positions, capture_area, interval, max_clicks, auto_pdf=False, auto_exit=False, capture_mode="region", scroll_after_click=False, move_mouse_away=True, mouse_offset=100):
        super().__init__()
        self.positions = positions
        self.capture_area = capture_area
        self.interval = interval
        self.max_clicks = max_clicks
        self.auto_pdf = auto_pdf
        self.auto_exit = auto_exit
        self.capture_mode = capture_mode
        self.scroll_after_click = scroll_after_click
        self.move_mouse_away = move_mouse_away
        self.mouse_offset = mouse_offset
        self.screenshots = []
        self.is_running = True
        
    def run(self):
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")
        
        if not self.positions:
            self.status_update.emit("错误：没有点击位置")
            self.finished.emit()
            return
            
        if self.max_clicks <= 0:
            self.status_update.emit("错误：最大点击次数必须大于0")
            self.finished.emit()
            return
        
        total_positions = len(self.positions)
        total_clicks = self.max_clicks
        
        self.status_update.emit(f"开始循环执行，共需点击 {total_clicks} 次")
        self.status_update.emit(f"位置数量: {total_positions} 个，将循环使用这些位置")
        
        print(f"Debug: 位置数量: {total_positions}, 总点击次数: {total_clicks}")
        print(f"Debug: 位置列表: {self.positions}")
        print(f"Debug: 移动鼠标: {self.move_mouse_away}, 偏移距离: {self.mouse_offset}")
        
        click_count = 0
        
        while self.is_running and click_count < total_clicks:
            position_index = click_count % total_positions
            x, y = self.positions[position_index]
            
            try:
                self.progress_update.emit(click_count + 1, total_clicks)
                
                cycle_number = (click_count // total_positions) + 1
                position_in_cycle = (click_count % total_positions) + 1
                
                self.status_update.emit(
                    f"第 {click_count + 1}/{total_clicks} 次 "
                    f"(第{cycle_number}轮，位置{position_in_cycle}/{total_positions}): "
                    f"准备点击 ({x}, {y})"
                )
                time.sleep(0.5)
                
                pyautogui.click(x, y)
                self.status_update.emit(
                    f"第 {click_count + 1}/{total_clicks} 次: 已点击 ({x}, {y})"
                )
                
                time.sleep(1)
                
                if self.scroll_after_click:
                    self.status_update.emit(f"第 {click_count + 1} 次: 正在刷新页面...")
                    pyautogui.scroll(-3)
                    time.sleep(0.3)
                    pyautogui.scroll(3)
                    time.sleep(0.5)
                
                remaining_wait = max(0, self.interval - 1.5)
                if remaining_wait > 0:
                    self.status_update.emit(f"第 {click_count + 1} 次: 等待页面加载 ({remaining_wait:.1f}秒)...")
                    time.sleep(remaining_wait)
                
                if self.move_mouse_away:
                    self.status_update.emit(f"第 {click_count + 1} 次: 移动鼠标避免遮挡...")
                    screen_width, screen_height = pyautogui.size()
                    
                    safe_x = max(0, min(screen_width - 10, x + self.mouse_offset))
                    safe_y = max(0, min(screen_height - 10, y + self.mouse_offset))
                    
                    if abs(safe_x - x) < 50 and abs(safe_y - y) < 50:
                        safe_x = max(0, min(screen_width - 10, x - self.mouse_offset))
                        safe_y = max(0, min(screen_height - 10, y - self.mouse_offset))
                    
                    pyautogui.moveTo(safe_x, safe_y)
                    time.sleep(0.3)
                
                self.status_update.emit(f"第 {click_count + 1} 次: 正在截图...")
                
                screenshot = self.take_screenshot()
                if screenshot is None:
                    self.status_update.emit(f"第 {click_count + 1} 次截图失败，跳过")
                    click_count += 1
                    continue
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"screenshots/screenshot_{timestamp}_{click_count + 1:03d}.png"
                screenshot.save(filename)
                
                self.screenshots.append((screenshot, filename))
                self.screenshot_taken.emit(filename)
                
                self.status_update.emit(
                    f"第 {click_count + 1}/{total_clicks} 次截图完成 "
                    f"(第{cycle_number}轮，位置{position_in_cycle})"
                )
                
                click_count += 1
                
                if click_count < total_clicks:
                    next_position_index = click_count % total_positions
                    next_x, next_y = self.positions[next_position_index]
                    next_cycle = (click_count // total_positions) + 1
                    next_pos_in_cycle = (click_count % total_positions) + 1
                    
                    self.status_update.emit(
                        f"准备第 {click_count + 1} 次操作 "
                        f"(第{next_cycle}轮，位置{next_pos_in_cycle}): ({next_x}, {next_y})"
                    )
                    time.sleep(0.5)
                
            except Exception as e:
                error_msg = f"第 {click_count + 1} 次操作出错: {str(e)}"
                self.status_update.emit(error_msg)
                print(f"Debug: {error_msg}")
                click_count += 1
                continue
                
        if self.is_running:
            total_cycles = (click_count - 1) // total_positions + 1 if click_count > 0 else 0
            final_msg = f"所有任务完成！共完成 {len(self.screenshots)} 次点击截图，执行了 {total_cycles} 轮循环"
            self.status_update.emit(final_msg)
            print(f"Debug: {final_msg}")
        else:
            self.status_update.emit("任务被用户停止")
        
        self.finished.emit()
    
    def take_screenshot(self):
        try:
            if self.capture_mode == "full_screen":
                return pyautogui.screenshot()
            elif self.capture_mode == "smart_window":
                screen_width, screen_height = pyautogui.size()
                margin_x = int(screen_width * 0.1)
                margin_y = int(screen_height * 0.1)
                smart_area = (
                    margin_x,
                    margin_y,
                    screen_width - 2 * margin_x,
                    screen_height - 2 * margin_y
                )
                return pyautogui.screenshot(region=smart_area)
            elif self.capture_mode == "top_content":
                screen_width, screen_height = pyautogui.size()
                top_area = (
                    0,
                    0,
                    screen_width,
                    int(screen_height * 0.7)
                )
                return pyautogui.screenshot(region=top_area)
            else:
                return pyautogui.screenshot(region=self.capture_area)
        except Exception as e:
            print(f"截图失败: {e}")
            return None
        
    def stop(self):
        self.is_running = False

class ScreenCaptureApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("循环点击截图生成PDF工具")
        self.setGeometry(100, 100, 900, 800)
        
        self.click_positions = []
        self.capture_area = (100, 100, 800, 600)
        self.screenshots = []
        self.capture_thread = None
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_info)
        self.timer.start(500)
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 配置区域
        config_group = QGroupBox("配置设置")
        config_layout = QVBoxLayout(config_group)
        
        # 截图模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("截图模式:"))
        self.capture_mode_combo = QComboBox()
        self.capture_mode_combo.addItems([
            "指定区域截图",
            "智能窗口截图",
            "顶部内容截图", 
            "全屏截图"
        ])
        self.capture_mode_combo.setCurrentIndex(1)
        self.capture_mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.capture_mode_combo)
        
        self.mode_description = QLabel("智能窗口截图：自动截取屏幕中央80%区域，避免边缘干扰")
        self.mode_description.setStyleSheet("color: gray; font-size: 10px;")
        mode_layout.addWidget(self.mode_description)
        mode_layout.addStretch()
        
        # 屏幕信息显示
        screen_width, screen_height = pyautogui.size()
        self.screen_info_label = QLabel(f"屏幕分辨率: {screen_width} x {screen_height}")
        
        # 截图区域设置
        area_layout = QHBoxLayout()
        area_layout.addWidget(QLabel("截图区域:"))
        self.area_x = QSpinBox()
        self.area_x.setRange(0, screen_width)
        self.area_x.setValue(100)
        self.area_y = QSpinBox()
        self.area_y.setRange(0, screen_height)
        self.area_y.setValue(100)
        self.area_width = QSpinBox()
        self.area_width.setRange(1, screen_width)
        self.area_width.setValue(min(800, screen_width - 200))
        self.area_height = QSpinBox()
        self.area_height.setRange(1, screen_height)
        self.area_height.setValue(min(600, screen_height - 200))
        
        area_layout.addWidget(QLabel("X:"))
        area_layout.addWidget(self.area_x)
        area_layout.addWidget(QLabel("Y:"))
        area_layout.addWidget(self.area_y)
        area_layout.addWidget(QLabel("宽:"))
        area_layout.addWidget(self.area_width)
        area_layout.addWidget(QLabel("高:"))
        area_layout.addWidget(self.area_height)
        
        self.preset_center_btn = QPushButton("设为屏幕中央")
        self.preset_center_btn.clicked.connect(self.set_center_area)
        self.preset_top_btn = QPushButton("设为顶部区域")
        self.preset_top_btn.clicked.connect(self.set_top_area)
        area_layout.addWidget(self.preset_center_btn)
        area_layout.addWidget(self.preset_top_btn)
        area_layout.addStretch()
        
        # 点击间隔设置
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("点击间隔(秒):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        interval_layout.addWidget(self.interval_spin)
        
        self.scroll_cb = QCheckBox("点击后轻微滚动页面(帮助刷新内容)")
        self.scroll_cb.setChecked(True)
        interval_layout.addWidget(self.scroll_cb)
        interval_layout.addStretch()
        
        # 鼠标移动设置
        mouse_layout = QHBoxLayout()
        self.move_mouse_cb = QCheckBox("截图前移动鼠标(避免浮标遮挡)")
        self.move_mouse_cb.setChecked(True)
        mouse_layout.addWidget(self.move_mouse_cb)
        
        mouse_layout.addWidget(QLabel("移动距离:"))
        self.mouse_offset_spin = QSpinBox()
        self.mouse_offset_spin.setRange(50, 500)
        self.mouse_offset_spin.setValue(100)
        self.mouse_offset_spin.setSuffix(" 像素")
        mouse_layout.addWidget(self.mouse_offset_spin)
        mouse_layout.addStretch()
        
        # 循环点击次数设置
        clicks_layout = QHBoxLayout()
        clicks_layout.addWidget(QLabel("总点击次数:"))
        self.max_clicks_spin = QSpinBox()
        self.max_clicks_spin.setRange(1, 9999)
        self.max_clicks_spin.setValue(10)
        clicks_layout.addWidget(self.max_clicks_spin)
        
        self.cycle_info_label = QLabel("程序将循环使用点击位置，直到达到总点击次数")
        self.cycle_info_label.setStyleSheet("color: blue; font-size: 10px;")
        clicks_layout.addWidget(self.cycle_info_label)
        clicks_layout.addStretch()
        
        # PDF生成选项
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(QLabel("PDF布局:"))
        self.pdf_layout_combo = QComboBox()
        self.pdf_layout_combo.addItems([
            "每页一张图片",
            "每页两张图片(上下排列-竖向纸张)",
            "每页两张图片(左右排列-横向纸张)"
        ])
        self.pdf_layout_combo.setCurrentIndex(1)
        pdf_layout.addWidget(self.pdf_layout_combo)
        
        pdf_description = QLabel("上下排列使用竖向A4纸张，左右排列使用横向A4纸张")
        pdf_description.setStyleSheet("color: gray; font-size: 10px;")
        pdf_layout.addWidget(pdf_description)
        pdf_layout.addStretch()
        
        # 自动化选项
        auto_layout = QHBoxLayout()
        self.auto_pdf_cb = QCheckBox("完成后自动生成PDF")
        self.auto_exit_cb = QCheckBox("完成后自动退出程序")
        auto_layout.addWidget(self.auto_pdf_cb)
        auto_layout.addWidget(self.auto_exit_cb)
        auto_layout.addStretch()
        
        config_layout.addLayout(mode_layout)
        config_layout.addWidget(self.screen_info_label)
        config_layout.addLayout(area_layout)
        config_layout.addLayout(interval_layout)
        config_layout.addLayout(mouse_layout)
        config_layout.addLayout(clicks_layout)
        config_layout.addLayout(pdf_layout)
        config_layout.addLayout(auto_layout)
        
        # 点击位置管理
        position_group = QGroupBox("点击位置管理")
        position_layout = QVBoxLayout(position_group)
        
        self.mouse_pos_label = QLabel("当前鼠标位置: (0, 0)")
        position_layout.addWidget(self.mouse_pos_label)
        
        self.position_count_label = QLabel("已添加位置: 0 个")
        self.position_count_label.setStyleSheet("color: green; font-weight: bold;")
        position_layout.addWidget(self.position_count_label)
        
        self.cycle_preview_label = QLabel("循环预览: 请先添加位置")
        self.cycle_preview_label.setStyleSheet("color: orange; font-size: 10px;")
        position_layout.addWidget(self.cycle_preview_label)
        
        button_layout = QHBoxLayout()
        self.add_current_btn = QPushButton("添加当前鼠标位置")
        self.add_current_btn.clicked.connect(self.add_current_position)
        self.add_manual_btn = QPushButton("手动添加位置")
        self.add_manual_btn.clicked.connect(self.add_manual_position)
        self.remove_btn = QPushButton("删除选中位置")
        self.remove_btn.clicked.connect(self.remove_position)
        self.clear_btn = QPushButton("清空所有位置")
        self.clear_btn.clicked.connect(self.clear_positions)
        
        button_layout.addWidget(self.add_current_btn)
        button_layout.addWidget(self.add_manual_btn)
        button_layout.addWidget(self.remove_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        
        self.position_list = QListWidget()
        
        position_layout.addLayout(button_layout)
        position_layout.addWidget(self.position_list)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始循环点击截图")
        self.start_btn.clicked.connect(self.start_capture)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_capture)
        self.stop_btn.setEnabled(False)
        self.pdf_btn = QPushButton("生成PDF")
        self.pdf_btn.clicked.connect(self.generate_pdf)
        self.test_screenshot_btn = QPushButton("测试截图")
        self.test_screenshot_btn.clicked.connect(self.test_screenshot)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.pdf_btn)
        control_layout.addWidget(self.test_screenshot_btn)
        control_layout.addStretch()
        
        # 进度显示
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("进度: 0/0")
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()
        
        # 状态显示
        self.status_label = QLabel("就绪")
        
        # 截图列表
        screenshot_group = QGroupBox("截图列表")
        screenshot_layout = QVBoxLayout(screenshot_group)
        self.screenshot_list = QListWidget()
        screenshot_layout.addWidget(self.screenshot_list)
        
        # 添加到主布局
        layout.addWidget(config_group)
        layout.addWidget(position_group)
        layout.addLayout(control_layout)
        layout.addLayout(progress_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(screenshot_group)
        
        # 初始化界面状态
        self.on_mode_changed("智能窗口截图")
        self.update_position_info()
        
        self.max_clicks_spin.valueChanged.connect(self.update_position_info)
        
    def update_position_info(self):
        count = len(self.click_positions)
        total_clicks = self.max_clicks_spin.value()
        
        self.position_count_label.setText(f"已添加位置: {count} 个")
        
        if count > 0:
            cycles = (total_clicks - 1) // count + 1 if total_clicks > 0 else 0
            remaining = total_clicks % count if count > 0 else 0
            
            if remaining == 0 and total_clicks > 0:
                self.cycle_preview_label.setText(
                    f"循环预览: 将执行 {cycles} 轮完整循环，总共 {total_clicks} 次点击"
                )
            else:
                self.cycle_preview_label.setText(
                    f"循环预览: 将执行 {cycles-1} 轮完整循环 + {remaining} 次，总共 {total_clicks} 次点击"
                )
        else:
            self.cycle_preview_label.setText("循环预览: 请先添加位置")
    
    def on_mode_changed(self, mode_text):
        descriptions = {
            "指定区域截图": "截取指定坐标和尺寸的区域",
            "智能窗口截图": "自动截取屏幕中央80%区域，避免边缘干扰",
            "顶部内容截图": "截取屏幕上方70%区域，适合网页内容",
            "全屏截图": "截取整个屏幕内容"
        }
        
        self.mode_description.setText(descriptions.get(mode_text, ""))
        
        if mode_text == "指定区域截图":
            self.area_x.setEnabled(True)
            self.area_y.setEnabled(True)
            self.area_width.setEnabled(True)
            self.area_height.setEnabled(True)
            self.preset_center_btn.setEnabled(True)
            self.preset_top_btn.setEnabled(True)
        else:
            self.area_x.setEnabled(False)
            self.area_y.setEnabled(False)
            self.area_width.setEnabled(False)
            self.area_height.setEnabled(False)
            self.preset_center_btn.setEnabled(False)
            self.preset_top_btn.setEnabled(False)
    
    def set_center_area(self):
        screen_width, screen_height = pyautogui.size()
        margin_x = int(screen_width * 0.1)
        margin_y = int(screen_height * 0.1)
        
        self.area_x.setValue(margin_x)
        self.area_y.setValue(margin_y)
        self.area_width.setValue(screen_width - 2 * margin_x)
        self.area_height.setValue(screen_height - 2 * margin_y)
    
    def set_top_area(self):
        screen_width, screen_height = pyautogui.size()
        
        self.area_x.setValue(0)
        self.area_y.setValue(0)
        self.area_width.setValue(screen_width)
        self.area_height.setValue(int(screen_height * 0.7))
    
    def test_screenshot(self):
        try:
            mode_text = self.capture_mode_combo.currentText()
            
            if mode_text == "全屏截图":
                screenshot = pyautogui.screenshot()
            elif mode_text == "智能窗口截图":
                screen_width, screen_height = pyautogui.size()
                margin_x = int(screen_width * 0.1)
                margin_y = int(screen_height * 0.1)
                smart_area = (
                    margin_x,
                    margin_y,
                    screen_width - 2 * margin_x,
                    screen_height - 2 * margin_y
                )
                screenshot = pyautogui.screenshot(region=smart_area)
            elif mode_text == "顶部内容截图":
                screen_width, screen_height = pyautogui.size()
                top_area = (0, 0, screen_width, int(screen_height * 0.7))
                screenshot = pyautogui.screenshot(region=top_area)
            else:
                capture_area = (
                    self.area_x.value(),
                    self.area_y.value(),
                    self.area_width.value(),
                    self.area_height.value()
                )
                screenshot = pyautogui.screenshot(region=capture_area)
            
            if not os.path.exists("test_screenshots"):
                os.makedirs("test_screenshots")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_filename = f"test_screenshots/test_{timestamp}.png"
            screenshot.save(test_filename)
            
            QMessageBox.information(self, "成功", f"测试截图已保存: {test_filename}\n截图尺寸: {screenshot.size[0]} x {screenshot.size[1]}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试截图失败: {str(e)}")
    
    def update_info(self):
        x, y = pyautogui.position()
        self.mouse_pos_label.setText(f"当前鼠标位置: ({x}, {y})")
    
    def get_capture_mode(self):
        mode_text = self.capture_mode_combo.currentText()
        if mode_text == "智能窗口截图":
            return "smart_window"
        elif mode_text == "顶部内容截图":
            return "top_content"
        elif mode_text == "全屏截图":
            return "full_screen"
        else:
            return "region"
        
    def add_current_position(self):
        x, y = pyautogui.position()
        self.click_positions.append((x, y))
        self.position_list.addItem(f"位置 {len(self.click_positions)}: ({x}, {y})")
        self.update_position_info()
        
    def add_manual_position(self):
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("添加位置")
        layout = QFormLayout(dialog)
        
        screen_width, screen_height = pyautogui.size()
        x_spin = QSpinBox()
        x_spin.setRange(0, screen_width)
        y_spin = QSpinBox()
        y_spin.setRange(0, screen_height)
        
        layout.addRow("X坐标:", x_spin)
        layout.addRow("Y坐标:", y_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            x, y = x_spin.value(), y_spin.value()
            self.click_positions.append((x, y))
            self.position_list.addItem(f"位置 {len(self.click_positions)}: ({x}, {y})")
            self.update_position_info()
            
    def remove_position(self):
        current_row = self.position_list.currentRow()
        if current_row >= 0:
            self.click_positions.pop(current_row)
            self.position_list.takeItem(current_row)
            self.position_list.clear()
            for i, (x, y) in enumerate(self.click_positions):
                self.position_list.addItem(f"位置 {i+1}: ({x}, {y})")
            self.update_position_info()
                
    def clear_positions(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有位置吗？", 
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.click_positions.clear()
            self.position_list.clear()
            self.update_position_info()
            
    def start_capture(self):
        if not self.click_positions:
            QMessageBox.warning(self, "警告", "请先添加点击位置")
            return
            
        self.capture_area = (
            self.area_x.value(),
            self.area_y.value(),
            self.area_width.value(),
            self.area_height.value()
        )
        
        total_clicks = self.max_clicks_spin.value()
        capture_mode = self.get_capture_mode()
        mode_text = self.capture_mode_combo.currentText()
        
        position_count = len(self.click_positions)
        full_cycles = total_clicks // position_count
        remaining_clicks = total_clicks % position_count
        
        cycle_info = f"将执行 {full_cycles} 轮完整循环"
        if remaining_clicks > 0:
            cycle_info += f" + {remaining_clicks} 次额外点击"
        
        reply = QMessageBox.question(
            self, 
            "确认开始循环", 
            f"循环配置确认:\n"
            f"• 点击位置: {position_count} 个\n"
            f"• 总点击次数: {total_clicks} 次\n"
            f"• 循环方式: {cycle_info}\n"
            f"• 截图模式: {mode_text}\n"
            f"• 点击间隔: {self.interval_spin.value()}秒\n"
            f"• 页面滚动: {'是' if self.scroll_cb.isChecked() else '否'}\n"
            f"• 移动鼠标: {'是' if self.move_mouse_cb.isChecked() else '否'}\n"
            f"• PDF布局: {self.pdf_layout_combo.currentText()}\n"
            f"• 自动生成PDF: {'是' if self.auto_pdf_cb.isChecked() else '否'}\n"
            f"• 自动退出: {'是' if self.auto_exit_cb.isChecked() else '否'}\n\n"
            f"预计总耗时: 约 {total_clicks * self.interval_spin.value()} 秒\n\n"
            f"确定开始循环吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.screenshots.clear()
        self.screenshot_list.clear()
        self.progress_label.setText("进度: 0/0")
        
        self.capture_thread = CaptureThread(
            self.click_positions.copy(),
            self.capture_area,
            self.interval_spin.value(),
            total_clicks,
            self.auto_pdf_cb.isChecked(),
            self.auto_exit_cb.isChecked(),
            capture_mode,
            self.scroll_cb.isChecked(),
            self.move_mouse_cb.isChecked(),
            self.mouse_offset_spin.value()
        )
        
        self.capture_thread.status_update.connect(self.update_status)
        self.capture_thread.screenshot_taken.connect(self.add_screenshot)
        self.capture_thread.progress_update.connect(self.update_progress)
        self.capture_thread.finished.connect(self.capture_finished)
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.capture_thread.start()
        
    def stop_capture(self):
        if self.capture_thread:
            self.capture_thread.stop()
            self.status_label.setText("正在停止...")
            
    def update_progress(self, current, total):
        self.progress_label.setText(f"进度: {current}/{total}")
        
    def capture_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if self.capture_thread:
            self.screenshots = self.capture_thread.screenshots
            
        final_count = len(self.screenshots)
        self.status_label.setText(f"循环任务完成！共截图 {final_count} 张")
        
        if self.auto_pdf_cb.isChecked() and final_count > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_filename = f"auto_output_{timestamp}.pdf"
            try:
                self.create_pdf(pdf_filename)
                self.status_label.setText(f"循环任务完成！共 {final_count} 张截图，PDF已自动生成: {pdf_filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"自动生成PDF失败: {str(e)}")
        
        if self.auto_exit_cb.isChecked():
            QMessageBox.information(self, "完成", f"循环任务已完成，共生成 {final_count} 张截图，程序将自动退出")
            QApplication.quit()
            
    def update_status(self, message):
        self.status_label.setText(message)
        
    def add_screenshot(self, filename):
        self.screenshot_list.addItem(os.path.basename(filename))
        
    def generate_pdf(self):
        if not self.screenshots:
            QMessageBox.warning(self, "警告", "没有截图可生成PDF")
            return
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存PDF文件", "", "PDF files (*.pdf)"
        )
        
        if filename:
            try:
                self.create_pdf(filename)
                QMessageBox.information(self, "成功", f"PDF已保存到: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"生成PDF失败: {str(e)}")
                
    def create_pdf(self, filename):
        """创建PDF文件，支持优化的布局"""
        layout_mode = self.pdf_layout_combo.currentText()
        
        if "横向纸张" in layout_mode:
            # 使用横向A4纸张
            pagesize = landscape(A4)
        else:
            # 使用竖向A4纸张
            pagesize = A4
            
        c = canvas.Canvas(filename, pagesize=pagesize)
        page_width, page_height = pagesize
        
        if layout_mode == "每页一张图片":
            # 每页一张图片
            for i, (screenshot, img_name) in enumerate(self.screenshots):
                if i > 0:
                    c.showPage()
                    
                img_width, img_height = screenshot.size
                
                scale_x = (page_width - 100) / img_width
                scale_y = (page_height - 150) / img_height
                scale = min(scale_x, scale_y)
                
                new_width = img_width * scale
                new_height = img_height * scale
                
                x = (page_width - new_width) / 2
                y = page_height - new_height - 50
                
                temp_path = f"temp_{i}.png"
                screenshot.save(temp_path)
                
                c.drawImage(temp_path, x, y, width=new_width, height=new_height)
                # c.setFont("Helvetica", 12)
                # c.drawString(50, page_height - 30, f"截图 {i+1}: {os.path.basename(img_name)}")
                
                os.remove(temp_path)
                
        elif "上下排列" in layout_mode:
            # 每页两张图片，上下排列（竖向纸张）
            for i in range(0, len(self.screenshots), 2):
                if i > 0:
                    c.showPage()
                
                # 上半部分图片
                screenshot1, img_name1 = self.screenshots[i]
                img_width1, img_height1 = screenshot1.size
                
                # 为上下布局预留更多空间，减少边距
                available_height = (page_height - 120) / 2  # 减少总边距
                margin = 50
                
                scale_x1 = (page_width - 2 * margin) / img_width1
                scale_y1 = available_height / img_height1
                scale1 = min(scale_x1, scale_y1)
                
                new_width1 = img_width1 * scale1
                new_height1 = img_height1 * scale1
                
                x1 = (page_width - new_width1) / 2
                y1 = page_height - new_height1 - margin
                
                temp_path1 = f"temp_{i}_1.png"
                screenshot1.save(temp_path1)
                
                c.drawImage(temp_path1, x1, y1, width=new_width1, height=new_height1)
                # c.setFont("Helvetica", 10)
                # c.drawString(margin, page_height - 30, f"截图 {i+1}: {os.path.basename(img_name1)}")
                
                os.remove(temp_path1)
                
                # 下半部分图片（如果存在）
                if i + 1 < len(self.screenshots):
                    screenshot2, img_name2 = self.screenshots[i + 1]
                    img_width2, img_height2 = screenshot2.size
                    
                    scale_x2 = (page_width - 2 * margin) / img_width2
                    scale_y2 = available_height / img_height2
                    scale2 = min(scale_x2, scale_y2)
                    
                    new_width2 = img_width2 * scale2
                    new_height2 = img_height2 * scale2
                    
                    x2 = (page_width - new_width2) / 2
                    # 修改：第二张图从页面中央开始，而不是紧贴第一张图
                    y2 = page_height / 2 - new_height2 / 2 - 120
                    
                    temp_path2 = f"temp_{i}_2.png"
                    screenshot2.save(temp_path2)
                    
                    c.drawImage(temp_path2, x2, y2, width=new_width2, height=new_height2)
                    # c.drawString(margin, page_height / 2 - 20, f"截图 {i+2}: {os.path.basename(img_name2)}")
                    
                    os.remove(temp_path2)
                    
        elif "左右排列" in layout_mode:
            # 每页两张图片，左右排列（横向纸张）
            for i in range(0, len(self.screenshots), 2):
                if i > 0:
                    c.showPage()
                
                # 左侧图片
                screenshot1, img_name1 = self.screenshots[i]
                img_width1, img_height1 = screenshot1.size
                
                # 横向纸张的优化布局
                margin = 40
                center_gap = 20  # 中间间隔
                available_width = (page_width - 2 * margin - center_gap) / 2
                available_height = page_height - 2 * margin - 40  # 为标题预留空间
                
                scale_x1 = available_width / img_width1
                scale_y1 = available_height / img_height1
                scale1 = min(scale_x1, scale_y1)
                
                new_width1 = img_width1 * scale1
                new_height1 = img_height1 * scale1
                
                # 左侧图片居中对齐
                x1 = margin + (available_width - new_width1) / 2
                y1 = margin + (available_height - new_height1) / 2
                
                temp_path1 = f"temp_{i}_1.png"
                screenshot1.save(temp_path1)
                
                c.drawImage(temp_path1, x1, y1, width=new_width1, height=new_height1)
                # c.setFont("Helvetica", 10)
                # c.drawString(margin, page_height - 25, f"截图 {i+1}")
                
                os.remove(temp_path1)
                
                # 右侧图片（如果存在）
                if i + 1 < len(self.screenshots):
                    screenshot2, img_name2 = self.screenshots[i + 1]
                    img_width2, img_height2 = screenshot2.size
                    
                    scale_x2 = available_width / img_width2
                    scale_y2 = available_height / img_height2
                    scale2 = min(scale_x2, scale_y2)
                    
                    new_width2 = img_width2 * scale2
                    new_height2 = img_height2 * scale2
                    
                    # 右侧图片居中对齐
                    x2 = margin + available_width + center_gap + (available_width - new_width2) / 2
                    y2 = margin + (available_height - new_height2) / 2
                    
                    temp_path2 = f"temp_{i}_2.png"
                    screenshot2.save(temp_path2)
                    
                    c.drawImage(temp_path2, x2, y2, width=new_width2, height=new_height2)
                    # c.drawString(x2, page_height - 25, f"截图 {i+2}")
                    
                    os.remove(temp_path2)
            
        c.save()

def main():
    app = QApplication(sys.argv)
    window = ScreenCaptureApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
