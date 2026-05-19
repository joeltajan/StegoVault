"""
StegoVault Matrix Pro v3.1
Premium PyQt6 application with Interactive Results, Image Previews,
Drag-and-Drop, and Unified Payload bundling.
"""

import sys
import os
import threading
import datetime
import ctypes
import io
import shutil
import zipfile
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QLineEdit, QFileDialog, 
                             QMessageBox, QStackedWidget, QProgressBar, QTextEdit, 
                             QListWidget, QFrame, QScrollArea, QSplitter)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject, QMimeData
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QIcon, QFont, QColor, QImage

import stego_core

# ── Matrix Theme ─────────────────────────────────────────────────────────────
QSS_THEME = """
QWidget {
    background-color: #000000;
    color: #00E5FF;
    font-family: 'Consolas', 'Courier New', monospace;
}
QFrame#sidebar {
    background-color: #050505;
    border-right: 1px solid #111111;
}
QFrame#card {
    background-color: #0A0A0A;
    border: 1px solid #222222;
    border-radius: 2px;
}
QLineEdit {
    background-color: #000000;
    border: 1px solid #333333;
    color: #00E5FF;
    padding: 8px;
    font-size: 13px;
}
QLineEdit:focus { border: 1px solid #00E5FF; }
QPushButton {
    background-color: #0A0A0A;
    color: #00E5FF;
    border: 1px solid #333333;
    padding: 10px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #111111;
    border: 1px solid #00E5FF;
}
QPushButton:pressed {
    background-color: #00E5FF;
    color: #000000;
}
QPushButton#navBtn {
    border: none;
    text-align: left;
    padding-left: 20px;
    font-size: 14px;
}
QPushButton#navBtn:checked {
    background-color: #111111;
    color: #FFFFFF;
    border-left: 3px solid #00E5FF;
}
QProgressBar {
    border: 1px solid #333333;
    background-color: #050505;
    text-align: center;
    color: #FFFFFF;
}
QProgressBar::chunk {
    background-color: #00E5FF;
}
QListWidget {
    background-color: #000000;
    border: 1px solid #222222;
    color: #00E5FF;
}
QTextEdit {
    background-color: #050505;
    color: #01ffeb;
    border: 1px solid #222222;
    font-size: 12px;
}
QLabel#preview {
    background-color: #050505;
    border: 1px dashed #222222;
}
"""

# ── Worker Thread for non-blocking UI ─────────────────────────────────────────
class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    log = pyqtSignal(str, str)

class Worker(threading.Thread):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.daemon = True
    
    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs, signals=self.signals)
            self.signals.finished.emit(res)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.signals.error.emit(str(e))

# ── Custom Widgets ────────────────────────────────────────────────────────────

class DragDropArea(QFrame):
    file_dropped = pyqtSignal(str)
    
    def __init__(self, icon_text, subtitle):
        super().__init__()
        self.setObjectName("card")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet("font-size: 32px;")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("color: #555555; font-size: 11px;")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.sub_lbl)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self.setStyleSheet("background-color: #111111; border: 1px solid #00E5FF;")
            event.accept()
        else:
            event.ignore()
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            self.file_dropped.emit(path)
            break 

class MatrixApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("MatrixMain")
        self.setWindowTitle("STEGO_VAULT // MATRIX_PROTOCOL v3.1")
        self.setFixedSize(1100, 780)
        self.setStyleSheet(QSS_THEME)
        
        # Windows: Screen Capture Protection
        try:
            if os.name == 'nt':
                ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception: pass
        
        self.current_carrier_path = None
        self.payload_files = []
        self.temp_extract_dir = os.path.join(tempfile.gettempdir(), "stegovault_temp")
        if os.path.exists(self.temp_extract_dir):
            shutil.rmtree(self.temp_extract_dir, ignore_errors=True)
        os.makedirs(self.temp_extract_dir, exist_ok=True)
        
        self.init_ui()
        self.log("SYS_READY // ENCRYPTION_LAYER_ARMED", "success")

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 20, 0, 20)
        
        logo = QLabel("〼 MATRIX")
        logo.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px; margin-left: 20px;")
        side_layout.addWidget(logo)
        
        self.btn_enc = QPushButton("[ ENCODE_MODE ]")
        self.btn_dec = QPushButton("[ DECODE_MODE ]")
        for b in [self.btn_enc, self.btn_dec]:
            b.setObjectName("navBtn")
            b.setCheckable(True)
            b.setFixedHeight(50)
            side_layout.addWidget(b)
        
        self.btn_enc.setChecked(True)
        self.btn_enc.clicked.connect(lambda: self.switch_page(0))
        self.btn_dec.clicked.connect(lambda: self.switch_page(1))
        
        side_layout.addStretch()
        
        status_box = QFrame()
        status_box.setStyleSheet("background: #0A0A0A; border-top: 1px solid #111111; padding: 10px;")
        status_layout = QVBoxLayout(status_box)
        status_layout.addWidget(QLabel("PROTECTION: ACTIVE"))
        status_layout.addWidget(QLabel("REDACTION: FULL"))
        side_layout.addWidget(status_box)
        
        main_layout.addWidget(self.sidebar)
        
        # Pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_encode_page())
        self.pages.addWidget(self.build_decode_page())
        main_layout.addWidget(self.pages)

    def switch_page(self, idx):
        self.pages.setCurrentIndex(idx)
        self.btn_enc.setChecked(idx == 0)
        self.btn_dec.setChecked(idx == 1)

    # ── ENCODE PAGE ──────────────────────────────────────────────────────────
    def build_encode_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 15)
        
        title = QLabel("> PROTOCOL // DATA_INJECTION")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)
        
        # Carrier Row
        carrier_row = QHBoxLayout()
        self.carrier_drop = DragDropArea("🖼", "DRAG CARRIER OR CLICK")
        self.carrier_drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.carrier_drop.mousePressEvent = lambda e: self.browse_carrier()
        self.carrier_drop.file_dropped.connect(self.set_carrier)
        carrier_row.addWidget(self.carrier_drop, 2)
        
        self.carrier_preview = QLabel()
        self.carrier_preview.setObjectName("preview")
        self.carrier_preview.setFixedSize(140, 140)
        self.carrier_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.carrier_preview.setText("PREVIEW")
        carrier_row.addWidget(self.carrier_preview)
        layout.addLayout(carrier_row)
        
        
        # Bundle workspace
        bundle_frame = QFrame()
        bundle_frame.setObjectName("card")
        bundle_layout = QHBoxLayout(bundle_frame)
        
        # Text input
        text_pane = QVBoxLayout()
        text_pane.addWidget(QLabel("PROTECTED_TEXT_MANIFEST"))
        self.payload_text = QTextEdit()
        self.payload_text.setPlaceholderText("ENTER SECRET MESSAGE...")
        self.payload_text.textChanged.connect(self.update_capacity)
        text_pane.addWidget(self.payload_text)
        bundle_layout.addLayout(text_pane, 2)
        
        # File list
        file_pane = QVBoxLayout()
        file_pane.addWidget(QLabel("FILE_WORKSPACE (DRAG FILES HERE)"))
        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.dragEnterEvent = self._file_list_dragEnter
        self.file_list.dropEvent = self._file_list_drop
        file_pane.addWidget(self.file_list)
        
        file_btns = QHBoxLayout()
        btn_add_f = QPushButton("[ ADD ]")
        btn_rem_f = QPushButton("[ REMOVE ]")
        btn_clr_f = QPushButton("[ CLEAR ]")
        btn_add_f.clicked.connect(self.add_payload_files)
        btn_rem_f.clicked.connect(self.remove_selected_file)
        btn_clr_f.clicked.connect(self.clear_payload_files)
        for b in [btn_add_f, btn_rem_f, btn_clr_f]: file_btns.addWidget(b)
        file_pane.addLayout(file_btns)
        
        bundle_layout.addLayout(file_pane, 3)
        layout.addWidget(bundle_frame)
        
        # Capacity Indicators (Moved here)
        self.lbl_cap = QLabel("WORKSPACE_CAPACITY: --")
        self.lbl_cap.setStyleSheet("font-size: 13px; font-weight: bold; color: #555555; margin-top: 5px;")
        layout.addWidget(self.lbl_cap)
        
        self.cap_bar = QProgressBar()
        self.cap_bar.setFixedHeight(12)
        layout.addWidget(self.cap_bar)
        
        # Commit section
        commit_frame = QFrame()
        commit_frame.setObjectName("card")
        commit_layout = QVBoxLayout(commit_frame)
        commit_layout.setContentsMargins(15, 12, 15, 12)
        
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("SAVE_AS :"))
        self.out_name_field = QLineEdit()
        self.out_name_field.setText(f"VAULT_{datetime.datetime.now().strftime('%H%M%S')}.png")
        r1.addWidget(self.out_name_field)
        
        r1.addWidget(QLabel("  KEY :"))
        self.enc_pass = QLineEdit()
        self.enc_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.enc_pass.setPlaceholderText("ENCRYPTION_PASSPHRASE")
        r1.addWidget(self.enc_pass)
        commit_layout.addLayout(r1)
        
        self.btn_run_enc = QPushButton("[ EXECUTE_INJECTION_PROTOCOL ]")
        self.btn_run_enc.setStyleSheet("background-color: #00E5FF; color: #000000; font-size: 14px; height: 40px;")
        self.btn_run_enc.clicked.connect(self.run_encode)
        commit_layout.addWidget(self.btn_run_enc)
        layout.addWidget(commit_frame)
        
        # Progress & Status (Moved up)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFixedHeight(90)
        self.terminal.setStyleSheet("font-size: 11px; background: #000000; border: 1px solid #111111;")
        layout.addWidget(self.terminal)

        return page

    # ── DECODE PAGE ──────────────────────────────────────────────────────────
    def build_decode_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 15)
        
        title = QLabel("> PROTOCOL // DATA_EXTRACTION")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title)
        
        # Input row
        in_row = QHBoxLayout()
        self.dec_drop = DragDropArea("📡", "DRAG ENCODED OR CLICK")
        self.dec_drop.setFixedHeight(150)
        self.dec_drop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dec_drop.mousePressEvent = lambda e: self.browse_stego_dialog()
        self.dec_drop.file_dropped.connect(self.set_dec_img)
        in_row.addWidget(self.dec_drop, 2)
        
        self.dec_preview = QLabel()
        self.dec_preview.setObjectName("preview")
        self.dec_preview.setFixedSize(120, 120)
        self.dec_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dec_preview.setText("PREVIEW")
        in_row.addWidget(self.dec_preview)
        layout.addLayout(in_row)
        
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("card")
        ctrl_layout = QHBoxLayout(ctrl_frame)
        
        self.dec_pass = QLineEdit()
        self.dec_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.dec_pass.setPlaceholderText("DECRYPTION_PASSPHRASE")
        ctrl_layout.addWidget(self.dec_pass)
        
        self.btn_run_dec = QPushButton("[ INITIALIZE_DECRYPT ]")
        self.btn_run_dec.clicked.connect(self.run_decode)
        ctrl_layout.addWidget(self.btn_run_dec)
        layout.addWidget(ctrl_frame)
        
        # Results section (Splitter)
        results_header = QLabel("EXTRACTED_CONTENT_INTERCEPTED")
        results_header.setStyleSheet("color: #FFFFFF; font-weight: bold; margin-top: 10px;")
        layout.addWidget(results_header)
        
        res_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Files
        f_box = QFrame()
        f_box.setObjectName("card")
        f_layout = QVBoxLayout(f_box)
        f_layout.addWidget(QLabel("DETECTION_MANIFEST (FILES)"))
        self.dec_results_list = QListWidget()
        f_layout.addWidget(self.dec_results_list)
        self.btn_export = QPushButton("[ EXPORT_SELECTED_AS ]")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_selected)
        f_layout.addWidget(self.btn_export)
        res_splitter.addWidget(f_box)
        
        # Right: Text
        t_box = QFrame()
        t_box.setObjectName("card")
        t_layout = QVBoxLayout(t_box)
        t_layout.addWidget(QLabel("RECOVERED_MANIFEST (TEXT)"))
        self.dec_results_text = QTextEdit()
        self.dec_results_text.setReadOnly(True)
        t_layout.addWidget(self.dec_results_text)
        res_splitter.addWidget(t_box)
        
        layout.addWidget(res_splitter)
        
        return page

    # ── Main Logic ─────────────────────────────────────────────────────────────
    def log(self, msg, level="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        color = "#00E5FF" if level == "info" else "#FFFFFF"
        if level == "success": color = "#00FF00"
        if level == "error": color = "#FF3333"
        html = f"<span style='color: #444;'>[{ts}]</span> <span style='color: {color};'>{msg}</span>"
        self.terminal.append(html)

    def browse_carrier(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Carrier Image", "", "Images (*.png *.bmp)")
        if p: self.set_carrier(p)

    def browse_stego_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Encoded Image", "", "Images (*.png *.bmp)")
        if p: self.set_dec_img(p)

    def set_carrier(self, path):
        self.current_carrier_path = path
        self._update_preview(path, self.carrier_preview)
        self.update_capacity()
        self.log(f"CARRIER_LOADED: {Path(path).name}", "info")

    def set_dec_img(self, path):
        self._update_preview(path, self.dec_preview)
        self.log(f"STEGO_MEDIUM_LOADED: {Path(path).name}", "info")
        # Find path field... normally we'd have a variable but we use the widget. 
        # I'll just store it internally.
        self._target_stego_path = path

    def _update_preview(self, path, label_widget):
        pix = QPixmap(path)
        if not pix.isNull():
            label_widget.setPixmap(pix.scaled(label_widget.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label_widget.setText("ERR")

    def _file_list_dragEnter(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def _file_list_drop(self, event):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p not in self.payload_files:
                self.payload_files.append(p)
                self.file_list.addItem(f" {Path(p).name} ({os.path.getsize(p)//1024}KB)")
        self.update_capacity()

    def add_payload_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files to Payload")
        for p in paths:
            if p not in self.payload_files:
                self.payload_files.append(p)
                self.file_list.addItem(f" {Path(p).name} ({os.path.getsize(p)//1024}KB)")
        self.update_capacity()

    def remove_selected_file(self):
        idx = self.file_list.currentRow()
        if idx >= 0:
            del self.payload_files[idx]
            self.file_list.takeItem(idx)
        self.update_capacity()

    def clear_payload_files(self):
        self.payload_files.clear()
        self.file_list.clear()
        self.update_capacity()

    def update_capacity(self):
        if not self.current_carrier_path: return
        try:
            total_cap = stego_core.get_capacity(self.current_carrier_path)
            text_size = len(self.payload_text.toPlainText().encode())
            files_size = sum(os.path.getsize(p) for p in self.payload_files if os.path.exists(p))
            est_total = text_size + files_size + 2048
            pct = min(100, int((est_total / total_cap) * 100))
            self.cap_bar.setValue(pct)
            self.lbl_cap.setText(f"PAYLOAD: {est_total/1024:.1f} KB  /  IMAGE_LIMIT: {total_cap/1024:.1f} KB")
            if pct > 90: self.cap_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF3333; }")
            else: self.cap_bar.setStyleSheet("")
        except Exception: pass

    # ── THREADED ENCODE ────────────────────────────────────────────────────────
    def run_encode(self):
        carrier = self.current_carrier_path
        pw = self.enc_pass.text()
        text = self.payload_text.toPlainText()
        out_name = self.out_name_field.text().strip()
        
        if not carrier: self.log("ERR: NULL_CARRIER", "error"); return
        if not pw: self.log("ERR: NULL_KEY", "error"); return
        if not text and not self.payload_files: self.log("ERR: NULL_DATA", "error"); return
        
        if not out_name.lower().endswith((".png", ".bmp")): out_name += ".png"
        output_path = os.path.join(os.getcwd(), out_name)
        
        self.btn_run_enc.setDisabled(True)
        self.log("INIT_INJECTION...", "info")

        def task(signals):
            signals.log.emit("BUILDING_BUNDLE...", "info")
            fname, bundle_data = stego_core.create_payload_bundle(text, self.payload_files)
            signals.log.emit("ENCRYPTING...", "info")
            payload = stego_core.encrypt_payload(pw, fname, bundle_data)
            signals.log.emit(f"BIT_WRITING: {len(payload):,} B...", "info")
            stego_core.encode_to_image(carrier, payload, output_path)
            return output_path

        worker = Worker(task)
        worker.signals.log.connect(self.log)
        worker.signals.finished.connect(lambda p: [self.log(f"SUCCESS: {Path(p).name}", "success"), self.btn_run_enc.setEnabled(True)])
        worker.signals.error.connect(lambda e: [self.log(f"FATAL: {e}", "error"), self.btn_run_enc.setEnabled(True)])
        worker.start()

    # ── THREADED DECODE ────────────────────────────────────────────────────────
    def run_decode(self):
        if not hasattr(self, '_target_stego_path'):
            self.log("ERR: NO_MEDIUM_LOADED", "error"); return
        img = self._target_stego_path
        pw = self.dec_pass.text()
        if not pw: self.log("ERR: NULL_KEY", "error"); return
        
        self.btn_run_dec.setDisabled(True)
        self.log("INIT_DECRYPT...", "info")
        self.dec_results_list.clear()
        self.dec_results_text.clear()

        def task(signals):
            signals.log.emit("READING_BITS...", "info")
            raw_payload = stego_core.decode_from_image(img)
            signals.log.emit("AUTH_VERIFYING...", "info")
            fname, data = stego_core.decrypt_payload(pw, raw_payload)
            
            # Reset temp dir
            if os.path.exists(self.temp_extract_dir):
                shutil.rmtree(self.temp_extract_dir, ignore_errors=True)
            os.makedirs(self.temp_extract_dir, exist_ok=True)
            
            files_found = []
            note_content = ""
            
            if fname == "bundle.zip":
                with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
                    zf.extractall(self.temp_extract_dir)
                    flist = zf.namelist()
                    if "NOTE.txt" in flist:
                        note_content = zf.read("NOTE.txt").decode('utf-8', errors='ignore')
                        flist.remove("NOTE.txt")
                    files_found = flist
            else:
                out_path = os.path.join(self.temp_extract_dir, fname)
                with open(out_path, "wb") as f: f.write(data)
                files_found = [fname]
                
            return {"files": files_found, "note": note_content}

        worker = Worker(task)
        worker.signals.log.connect(self.log)
        worker.signals.finished.connect(self._on_decode_finished)
        worker.signals.error.connect(lambda e: [self.log(f"AUTH_FAIL: {e}", "error"), self.btn_run_dec.setEnabled(True)])
        worker.start()

    def _on_decode_finished(self, results):
        self.btn_run_dec.setEnabled(True)
        self.log("EXTRACTION_COMPLETE", "success")
        
        if results["note"]:
            self.dec_results_text.setPlainText(results["note"])
        
        for f in results["files"]:
            self.dec_results_list.addItem(f)
            
        self.btn_export.setEnabled(len(results["files"]) > 0)
        
        if results["note"]:
            QMessageBox.information(self, "MANIFEST_RECOVERED", f"HIDDEN_TEXT_MANIFEST: \n\n{results['note']}")
        else:
            QMessageBox.information(self, "VAULT_OPEN", "DECRYPT_SUCCESSFUL.\nFILES_ARE_READY_IN_WORKSPACE.")

    def export_selected(self):
        items = self.dec_results_list.selectedItems()
        target_dir = QFileDialog.getExistingDirectory(self, "SELECT_EXPORT_DESTINATION")
        if not target_dir: return
        
        success = 0
        for item in items:
            name = item.text()
            src = os.path.join(self.temp_extract_dir, name)
            dst = os.path.join(target_dir, name)
            try:
                shutil.copy2(src, dst)
                success += 1
            except Exception as e:
                self.log(f"EXPORT_ERR: {name} -> {e}", "error")
        
        if success == len(items):
             self.log(f"EXPORT_COMPLETE: {success} FILES_COMMITTED", "success")
        else:
             # Just export all if none selected
             if not items:
                 for root, _, files in os.walk(self.temp_extract_dir):
                     for f in files:
                         shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
                 self.log("EXPORT_COMPLETE: ALL_FILES_COMMITTED", "success")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MatrixApp()
    window.show()
    sys.exit(app.exec())
