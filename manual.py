import subprocess
import logging
import asyncio
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor
from general import close_ld, start_ld, run_ldplayer_command, load_paths_and_urls_from_config
import time
import cv2
import numpy as np
from PIL import ImageGrab
import pyautogui
import os

logging.basicConfig(level=logging.INFO)

paths = load_paths_and_urls_from_config('urls_config.ini')
adb_path = paths['adb_path']
ldplayer_path = paths['ldplayer_path']


async def start_ld_async(index):
    await start_ld(ldplayer_path, index)


async def close_ld_async(index):
    await close_ld(ldplayer_path, index)


async def run_command_async():
    await asyncio.to_thread(run_ldplayer_command, ldplayer_path, "sortWnd")


async def click_on_templates_in_first_window():
    templates = ["icon/template1.png", "icon/template2.png", "icon/template3.png"]
    region = (0, 0, 1024, 768)

    for template in templates:
        await click_on_template_in_region(template, region)
        await asyncio.sleep(2)


async def click_on_template_in_region(template_path, region, timeout=60, interval=5):
    start_time = time.time()
    template = cv2.imread(template_path, 0)
    w, h = template.shape[::-1]

    while time.time() - start_time < timeout:
        screen = np.array(ImageGrab.grab(bbox=region))
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.8)

        for pt in zip(*loc[::-1]):
            pyautogui.click(region[0] + pt[0] + w / 2, region[1] + pt[1] + h / 2)
            logging.info(f"Clicked on template at location: {pt} in region: {region}")
            return

        await asyncio.sleep(interval)


async def run_script_from_file(script_path):
    with open(script_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("click_image"):
            _, image_path = line.split(" ", 1)
            region = (0, 0, 1024, 768)
            await click_on_template_in_region(image_path.strip(), region)

        elif line.startswith("click_at"):
            _, x, y = line.split()
            pyautogui.click(int(x), int(y))

        elif line.startswith("sleep"):
            _, duration = line.split()
            await asyncio.sleep(float(duration))

        elif line.startswith("write_text"):
            _, *text_parts = line.split()
            text = " ".join(text_parts)
            pyautogui.write(text)

        else:
            logging.warning(f"Unknown command: {line}")


def start_ld_callback():
    indices_str = index_entry.get()
    indices = indices_str.split()
    for index in indices:
        if index.isdigit():
            asyncio.run_coroutine_threadsafe(start_ld_async(int(index)), loop)


def close_ld_callback():
    indices_str = index_entry.get()
    indices = indices_str.split()
    for index in indices:
        if index.isdigit():
            asyncio.run_coroutine_threadsafe(close_ld_async(int(index)), loop)


def run_command_callback():
    asyncio.run_coroutine_threadsafe(run_command_async(), loop)


def click_on_templates_callback():
    asyncio.run_coroutine_threadsafe(click_on_templates_in_first_window(), loop)


def run_script_callback():
    script_path = script_entry.get()
    asyncio.run_coroutine_threadsafe(run_script_from_file(script_path), loop)


def capture_image_callback():
    try:
        import io
        import re
        from PIL import Image

        def wait_for_device(expected_names, timeout=10):
            for _ in range(timeout * 2):
                result = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
                lines = result.stdout.strip().splitlines()
                for line in lines:
                    if line.endswith("\tdevice"):
                        for name in expected_names:
                            if name in line:
                                return line.split()[0]
                time.sleep(0.5)
            return None

        x1_str = capture_x1_entry.get()
        y1_str = capture_y1_entry.get()
        width_str = capture_x2_entry.get()
        height_str = capture_y2_entry.get()
        filename = capture_name_entry.get().strip()

        if not all([x1_str, y1_str, width_str, height_str, filename]):
            logging.error("All coordinates and filename must be provided.")
            return

        x1 = int(x1_str)
        y1 = int(y1_str)
        width = int(width_str)
        height = int(height_str)

        if width <= 0 or height <= 0:
            logging.error("Width and height must be positive numbers.")
            return

        x2 = x1 + width
        y2 = y1 + height

        filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        if not filename.lower().endswith('.png'):
            filename += '.png'

        ld_indices_str = index_entry.get()
        if not ld_indices_str.strip():
            logging.error("Please enter at least one LDPlayer index in the main input field.")
            return

        try:
            ld_index = int(ld_indices_str.strip().split()[0])
        except ValueError:
            logging.error("Invalid LDPlayer index input.")
            return

        expected_port = 5554 + ld_index * 2
        expected_names = [f"127.0.0.1:{expected_port}", f"emulator-{expected_port}"]

        device_id = wait_for_device(expected_names)

        if not device_id:
            logging.error(f"Could not detect ADB device for LD index {ld_index} (port {expected_port}) after waiting.")
            return

        logging.info(f"Using ADB device: {device_id} for LD index {ld_index}")

        result = subprocess.run(
            [adb_path, "-s", device_id, "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            logging.error(f"ADB screencap failed: {result.stderr.decode()}")
            return

        image_data = result.stdout
        image = Image.open(io.BytesIO(image_data))

        cropped = image.crop((x1, y1, x2, y2))

        folder = "img"
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        cropped.save(filepath)
        logging.info(f"Saved cropped image to {filepath}")

    except ValueError as ve:
        logging.error(f"Invalid number input: {ve}")
    except Exception as e:
        logging.error(f"Failed to capture image: {e}")


def capture_fullscreen_and_open_paint():
    try:
        import io
        from PIL import Image

        ld_indices_str = index_entry.get()
        if not ld_indices_str.strip():
            logging.error("Please enter at least one LDPlayer index.")
            return

        try:
            ld_index = int(ld_indices_str.strip().split()[0])
        except ValueError:
            logging.error("Invalid LDPlayer index input.")
            return

        expected_port = 5554 + ld_index * 2
        device_id = f"emulator-{expected_port}"

        logging.info(f"Using ADB device: {device_id} for LD index {ld_index}")

        subprocess.run([adb_path, "connect", f"127.0.0.1:{expected_port}"], capture_output=True)

        result = subprocess.run(
            [adb_path, "-s", device_id, "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            logging.error(f"ADB screencap failed: {result.stderr.decode()}")
            return

        image_data = result.stdout
        image = Image.open(io.BytesIO(image_data))

        folder = "screenshot"
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"ldplayer_{ld_index}_full.png")
        image.save(filepath)

        logging.info(f"Saved full screenshot to {filepath}")

        subprocess.Popen(["mspaint", filepath])
        logging.info("Opened screenshot in Paint.")

    except Exception as e:
        logging.error(f"Failed to capture fullscreen: {e}")


# Setup Tkinter
root = tk.Tk()
root.title("LDPlayer Controller")

index_label = ttk.Label(root, text="LDPlayer Indices (space-separated):")
index_label.grid(column=0, row=0, padx=10, pady=10)
index_entry = ttk.Entry(root)
index_entry.grid(column=1, row=0, padx=10, pady=10)

start_button = ttk.Button(root, text="Start LDPlayer", command=start_ld_callback)
start_button.grid(column=0, row=1, columnspan=2, padx=10, pady=10)

command_button = ttk.Button(root, text="Sort Windows", command=run_command_callback)
command_button.grid(column=0, row=2, columnspan=2, padx=10, pady=10)

click_templates_button = ttk.Button(root, text="Click Syn", command=click_on_templates_callback)
click_templates_button.grid(column=0, row=3, columnspan=2, padx=10, pady=10)

quit_button = ttk.Button(root, text="Quit LDPlayer", command=close_ld_callback)
quit_button.grid(column=0, row=4, columnspan=2, padx=10, pady=10)

script_label = ttk.Label(root, text="Script file:")
script_label.grid(column=0, row=5, padx=10, pady=10)
script_entry = ttk.Entry(root)
script_entry.insert(0, "actions.txt")
script_entry.grid(column=1, row=5, padx=10, pady=10)

script_button = ttk.Button(root, text="Run Script", command=run_script_callback)
script_button.grid(column=0, row=6, columnspan=2, padx=10, pady=10)

capture_label = ttk.Label(root, text="Capture (x1 y1 width height), Filename and LDPlayer Index:")
capture_label.grid(column=0, row=7, columnspan=2, padx=10, pady=10)

capture_x1_entry = ttk.Entry(root, width=5)
capture_x1_entry.grid(column=0, row=8, padx=5)
capture_y1_entry = ttk.Entry(root, width=5)
capture_y1_entry.grid(column=0, row=9, padx=5)
capture_x2_entry = ttk.Entry(root, width=5)
capture_x2_entry.grid(column=1, row=8, padx=5)
capture_y2_entry = ttk.Entry(root, width=5)
capture_y2_entry.grid(column=1, row=9, padx=5)

capture_name_entry = ttk.Entry(root)
capture_name_entry.insert(0, "template_new.png")
capture_name_entry.grid(column=0, row=10, columnspan=2, padx=10, pady=5)

capture_button = ttk.Button(root, text="Capture Image", command=capture_image_callback)
capture_button.grid(column=0, row=12, columnspan=2, padx=10, pady=10)

fullscreen_button = ttk.Button(root, text="Capture Fullscreen", command=capture_fullscreen_and_open_paint)
fullscreen_button.grid(column=0, row=13, columnspan=2, padx=10, pady=10)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
executor = ThreadPoolExecutor()

def run_tk(root):
    try:
        while True:
            root.update()
            loop.run_until_complete(asyncio.sleep(0.1))
    except tk.TclError as e:
        if "application has been destroyed" not in str(e):
            raise

executor.submit(run_tk, root)
root.mainloop()
