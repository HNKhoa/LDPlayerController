import subprocess
import time
import asyncio
import cv2
import numpy as np
from PIL import Image
import pytesseract
import io
import os

class AutomationRunner:
    def __init__(self, device_id: str):
        # Khởi tạo đối tượng với device_id (ví dụ: emulator-5556)
        self.device_id = device_id

    # Hàm này dùng ADB để chụp ảnh màn hình thiết bị và trả về đối tượng PIL Image
    def adb_screencap(self) -> Image.Image:
        result = subprocess.run([
            "adb", "-s", self.device_id, "exec-out", "screencap", "-p"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            raise RuntimeError(f"ADB screencap failed: {result.stderr.decode()}")

        return Image.open(io.BytesIO(result.stdout))

    # Hàm gửi lệnh ADB để click vào vị trí x, y trên màn hình thiết bị
    def adb_tap(self, x: int, y: int):
        subprocess.run(["adb", "-s", self.device_id, "shell", "input", "tap", str(x), str(y)])

    # Hàm gửi lệnh ADB để nhập văn bản vào thiết bị
    def adb_text(self, text: str):
        safe_text = text.replace(" ", "%s")
        subprocess.run(["adb", "-s", self.device_id, "shell", "input", "text", safe_text])

    # Hàm tìm ảnh mẫu (template) trong ảnh chụp màn hình hiện tại
    def find_image_on_screen(self, template_path: str, threshold=0.8):
        screen = self.adb_screencap().convert("RGB")
        screen_np = np.array(screen)
        screen_gray = cv2.cvtColor(screen_np, cv2.COLOR_RGB2GRAY)

        template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise FileNotFoundError(f"Template not found: {template_path}")

        res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = template.shape
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return center_x, center_y
        else:
            return None

    # Hàm cắt một vùng ảnh từ màn hình và nhận diện văn bản bằng OCR
    def ocr_region(self, x1, y1, x2, y2):
        img = self.adb_screencap().crop((x1, y1, x2, y2))
        return pytesseract.image_to_string(img)

    # Hàm chính đọc file script.txt và thực thi từng dòng lệnh tự động
    async def run_script(self, script_path: str):
        if not os.path.exists(script_path):
            print(f"Script not found: {script_path}")
            return

        with open(script_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Tìm và click vào ảnh mẫu
            if line.startswith("click_image"):
                _, path = line.split(maxsplit=1)
                pos = self.find_image_on_screen(path)
                if pos:
                    self.adb_tap(*pos)
                else:
                    print(f"Image not found: {path}")

            # Click vào toạ độ cụ thể
            elif line.startswith("click_at"):
                _, x, y = line.split()
                self.adb_tap(int(x), int(y))

            # Chờ trong một khoảng thời gian
            elif line.startswith("sleep"):
                _, sec = line.split()
                await asyncio.sleep(float(sec))

            # Gõ văn bản vào thiết bị
            elif line.startswith("write_text"):
                _, *text = line.split()
                self.adb_text(" ".join(text))

            # Đọc văn bản từ vùng ảnh bằng OCR
            elif line.startswith("read_text"):
                _, x1, y1, x2, y2 = line.split()
                result = self.ocr_region(int(x1), int(y1), int(x2), int(y2))
                print(f"OCR Result: {result.strip()}")

            # Nếu ảnh tồn tại thì thực hiện khối lệnh, ngược lại thực hiện else (nếu có)
            elif line.startswith("if_image"):
                _, path = line.split(maxsplit=1)
                condition = self.find_image_on_screen(path) is not None
                block = []
                else_block = []
                i += 1
                depth = 1
                while i < len(lines):
                    if lines[i] == "end_if":
                        break
                    elif lines[i] == "else":
                        depth += 1
                        i += 1
                        while i < len(lines) and lines[i] != "end_if":
                            else_block.append(lines[i])
                            i += 1
                        break
                    else:
                        block.append(lines[i])
                        i += 1
                if condition:
                    await self.run_inline_block(block)
                else:
                    await self.run_inline_block(else_block)
            i += 1

    # Hàm phụ để thực thi khối lệnh trong if hoặc else
    async def run_inline_block(self, block_lines):
        for line in block_lines:
            if line.startswith("click_image"):
                _, path = line.split(maxsplit=1)
                pos = self.find_image_on_screen(path)
                if pos:
                    self.adb_tap(*pos)
            elif line.startswith("click_at"):
                _, x, y = line.split()
                self.adb_tap(int(x), int(y))
            elif line.startswith("sleep"):
                _, sec = line.split()
                await asyncio.sleep(float(sec))
            elif line.startswith("write_text"):
                _, *text = line.split()
                self.adb_text(" ".join(text))
