# pip install pygame mido
# pip install pyinstaller
# pyinstaller --onefile main.py
# pyinstaller --onefile --icon=1.ico main.py

import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pygame.midi
import time
import threading
import mido
import re
from PIL import Image, ImageDraw, ImageFont  # 新增：用于导出图片
import sys
import os
import webbrowser
from PIL import Image, ImageDraw, ImageFont  # 新增：用于导出图片

# 版本信息
VERSION = "2.0"
APP_NAME = "MIDI简谱播放器"

# 初始化 pygame.midi
pygame.midi.init()

# 获取 MIDI 输出设备
try:
    midi_out = pygame.midi.Output(0)
except pygame.midi.MidiException:
    print("无法打开MIDI输出设备，程序将使用默认设置")
    midi_out = None

# 乐器名称映射
instrument_names = {
    0: "大钢琴(声学钢琴)",
    1: "明亮的钢琴",
    2: "电钢琴",
}

# 播放控制标志
is_playing = False
is_paused = False
pause_start_time = 0
current_note_index = 0
all_notes = []
loop_playback = False

text_boxes = []
play_buttons = []
track_settings = []
threads = []

current_displayed_index = 0
volume = 127


def play_note(note_number, duration, instrument, velocity):
    global is_playing, is_paused, pause_start_time, midi_out
    if midi_out:
        midi_out.set_instrument(instrument)
        midi_out.note_on(note_number, velocity)
        start_time = time.time()
        while time.time() - start_time < duration / 1000:
            if is_paused:
                pause_start_time = time.time()
                while is_paused:
                    root.update()
                start_time += time.time() - pause_start_time
            if not is_playing:
                midi_out.note_off(note_number, velocity)
                return
        midi_out.note_off(note_number, velocity)


def play_next_note(notes, instrument, tune, speed):
    global is_playing, loop_playback
    while is_playing:
        index = 0
        while is_playing and index < len(notes):
            note = notes[index]
            note_number, duration, velocity = process_note(note, speed)
            note_number = convert_tune(note_number, tune)
            if note_number is not None:
                play_note(note_number, duration, instrument, velocity)
            index += 1

        if not loop_playback:
            break


def play_all_tracks_together():
    global is_playing, threads, loop_playback
    is_playing = True
    is_paused = False
    if 'pause_button' in globals():
        pause_button.config(text="暂停")

    threads = []
    for i in range(16):
        notes_str = text_boxes[i].get("1.0", "end-1c")
        if notes_str.strip():
            notes, instrument, speed, tune = parse_notes_and_settings(notes_str)
            thread = threading.Thread(target=play_next_note, args=(notes, instrument, tune, speed))
            threads.append(thread)
            thread.start()


def pause_music():
    global is_paused
    is_paused = not is_paused
    if is_paused:
        pause_button.config(text="继续")
    else:
        pause_button.config(text="暂停")


def stop_music():
    global is_playing, is_paused, current_note_index, threads
    is_playing = False
    is_paused = False
    current_note_index = 0
    if 'pause_button' in globals():
        pause_button.config(text="暂停")

    for thread in threads:
        if thread.is_alive():
            thread.join()


def process_note(note_str, base_duration):
    if note_str == '0':
        return None, base_duration, 0

    if note_str.startswith('-'):
        return None, base_duration * len(note_str), 0

    if note_str.startswith('[') and note_str.endswith(']'):
        group_content = note_str[1:-1]
        if group_content:
            first_note = group_content[0]
            if first_note in '1234567':
                note_number, _, velocity = process_note(first_note, base_duration)
                return note_number, base_duration, velocity
        return None, base_duration, 0

    if note_str.startswith('(') and note_str.endswith(')'):
        group_content = note_str[1:-1]
        if group_content:
            first_note = group_content[0]
            if first_note in '1234567':
                note_number, _, velocity = process_note(first_note, base_duration)
                return note_number, base_duration / 2, velocity
        return None, base_duration / 2, 0

    if not note_str or note_str[0] not in '1234567':
        return None, base_duration, 0

    note_mapping = {
        '1': 60, '2': 62, '3': 64, '4': 65, '5': 67, '6': 69, '7': 71,
        '1#': 61, '2#': 63, '4#': 66, '5#': 68, '6#': 70
    }

    base_note = note_str[0]
    if len(note_str) > 1 and note_str[1] == '#':
        base_note += '#'
        remaining = note_str[2:]
    else:
        remaining = note_str[1:]

    octave_offset = 0
    if "'" in remaining:
        octave_offset += remaining.count("'") * 12
        remaining = remaining.replace("'", "")
    if "." in remaining:
        octave_offset -= remaining.count(".") * 12
        remaining = remaining.replace(".", "")

    duration_multiplier = 1.5 ** remaining.count('-')
    duration = base_duration * duration_multiplier

    if base_note in note_mapping:
        note_number = max(0, min(127, note_mapping[base_note] + octave_offset))
        return note_number, duration, volume

    return None, duration, 0


def convert_tune(note_number, tune):
    if note_number is None:
        return None

    tune_mapping = {
        "C 大调": 0,
        "C# 大调": 1, "Db 大调": 1,
        "D 大调": 2,
        "D# 大调": 3, "Eb 大调": 3,
        "E 大调": 4,
        "F 大调": 5,
        "F# 大调": 6, "Gb 大调": 6,
        "G 大调": 7,
        "G# 大调": 8, "Ab 大调": 8,
        "A 大调": 9,
        "A# 大调": 10, "Bb 大调": 10,
        "B 大调": 11
    }

    if tune in tune_mapping:
        return note_number + tune_mapping[tune]
    return note_number


def parse_notes_and_settings(notes_str):
    lines = notes_str.splitlines()
    if len(lines) > 0:
        settings = lines[0].split(',')
        tune = settings[0].strip()
        instrument = int(settings[1])
        speed = int(settings[2])
        notes_str = '\n'.join(lines[1:])
    else:
        tune = "C 大调"
        instrument = 0
        speed = 300

    notes_str = notes_str.replace('|', '')

    notes = []
    i = 0
    while i < len(notes_str):
        char = notes_str[i]

        if char == '[':
            end_index = notes_str.find(']', i)
            if end_index == -1:
                i += 1
                continue
            group_content = notes_str[i + 1:end_index]
            notes.append(f"[{group_content}]")
            i = end_index + 1

        elif char == '(':
            end_index = notes_str.find(')', i)
            if end_index == -1:
                i += 1
                continue
            group_content = notes_str[i + 1:end_index]
            notes.append(f"({group_content})")
            i = end_index + 1

        elif char in '01234567#':
            j = i + 1
            while j < len(notes_str) and notes_str[j] in "'.-#":
                j += 1
            note = notes_str[i:j]
            notes.append(note)
            i = j

        elif char == '-':
            j = i
            while j < len(notes_str) and notes_str[j] == '-':
                j += 1
            dashes = notes_str[i:j]
            notes.append(dashes)
            i = j

        else:
            i += 1

    return notes, instrument, speed, tune


# ==================== 新增：MIDI转简谱功能 ====================

def midi_to_jianpu(midi_file_path):
    """将MIDI文件转换为简谱文本"""
    # 音符映射：MIDI编号 → 简谱
    note_map = {
        60: '1', 62: '2', 64: '3', 65: '4', 67: '5', 69: '6', 71: '7',
        72: "1'", 74: "2'", 76: "3'", 77: "4'", 79: "5'", 81: "6'", 83: "7'",
        48: '1.', 50: '2.', 52: '3.', 53: '4.', 55: '5.', 57: '6.', 59: '7.',
        84: "1''", 86: "2''", 88: "3''", 89: "4''", 91: "5''", 93: "6''", 95: "7''",
        36: '1..', 38: '2..', 40: '3..', 41: '4..', 43: '5..', 45: '6..', 47: '7..',
    }

    try:
        mid = mido.MidiFile(midi_file_path)
        ticks_per_beat = mid.ticks_per_beat
        current_tempo = 280000
        active_notes = {}
        note_events = []

        for track in mid.tracks:
            abs_time = 0
            for msg in track:
                abs_time += msg.time
                if msg.is_meta:
                    if msg.type == 'set_tempo':
                        current_tempo = msg.tempo
                    continue

                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = abs_time
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        duration = abs_time - active_notes[msg.note]
                        note_events.append((active_notes[msg.note], duration, msg.note))
                        del active_notes[msg.note]

        if not note_events:
            return None, "未找到音符"

        note_events.sort(key=lambda x: x[0])
        quarter_ticks = ticks_per_beat

        score_parts = []
        for start_time, duration, note in note_events:
            note_str = note_map.get(note, '')
            if not note_str:
                continue

            beat_ratio = duration / quarter_ticks

            # 时值符号
            if beat_ratio >= 3.5:
                symbol = '---'
            elif beat_ratio >= 2.5:
                symbol = '--'
            elif beat_ratio >= 1.5:
                symbol = '-'
            # elif beat_ratio >= 0.875:
            #     symbol = '/'
            # elif beat_ratio >= 0.375:
            #     symbol = '//'
            else:
                symbol = ''

            score_parts.append(note_str)
            if symbol:
                score_parts.append(symbol)

        bpm = int(mido.tempo2bpm(current_tempo))
        result = ''.join(score_parts)
        if len(result) > 2000:
            result = result[:2000]

        return result, bpm

    except Exception as e:
        return None, str(e)


def import_midi_file():
    """导入MIDI文件（支持多音轨）"""
    global current_displayed_index, text_boxes

    midi_file = filedialog.askopenfilename(
        title="选择MIDI文件",
        filetypes=[("MIDI文件", "*.mid"), ("所有文件", "*.*")]
    )

    if not midi_file:
        return
    print(f"\n=== 开始导入MIDI文件: {midi_file} ===")
    try:
        # 解析MIDI文件，获取所有轨道
        tracks_data = parse_midi_multi_track(midi_file)

        if not tracks_data:
            messagebox.showerror("失败", "MIDI文件中未找到音符")
            return
            # 打印每个音轨的信息
        for i, track in enumerate(tracks_data):
            print(
                f"音轨{i + 1}: {track['name']}, 乐器={track['instrument']}, BPM={track['bpm']}, 音符数={track.get('note_count', '?')}")
        # 创建选择窗口
        select_window = tk.Toplevel(root)
        select_window.title("选择要导入的音轨")
        select_window.geometry("500x450")
        select_window.transient(root)
        select_window.grab_set()

        tk.Label(select_window, text=f"MIDI文件包含 {len(tracks_data)} 个音轨",
                 font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(select_window, text="请选择要导入的音轨（可多选）:",
                 font=("Arial", 10)).pack(pady=5)

        # 列表框（支持多选）
        listbox = tk.Listbox(select_window, selectmode=tk.MULTIPLE,
                             height=10, font=("Consolas", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for i, track in enumerate(tracks_data):
            preview = track['jianpu'][:50] + "..." if len(track['jianpu']) > 50 else track['jianpu']
            display_text = f"{i + 1}. {track['name']}  (BPM:{track['bpm']}) - {preview}"
            listbox.insert(tk.END, display_text)

        # 按钮框架
        btn_frame = tk.Frame(select_window)
        btn_frame.pack(pady=15)

        def import_selected():
            selected = listbox.curselection()
            if not selected:
                messagebox.showwarning("提示", "请至少选择一个音轨")
                return

            # 获取当前激活的音轨编号
            current_idx = current_displayed_index

            # 导入第一个选中的音轨到当前文本框
            first = selected[0]
            track = tracks_data[first]

            # 修复调式名称乱码
            tune_name = track['tune']
            # 根据轨道索引或乐器设置正确的调式
            if first == 0:
                tune_name = "G 大调"
            elif first == 1:
                tune_name = "A 大调"
            elif first == 2:
                tune_name = "C 大调"
            else:
                # 保持原样或使用默认
                if 'G' in tune_name or 'å¤§' in tune_name:
                    tune_name = "G 大调"
                elif 'A' in tune_name:
                    tune_name = "A 大调"
                else:
                    tune_name = "C 大调"

            header = f"{tune_name},{track['instrument']},{track['bpm']}"
            result = header + "\n" + track['jianpu']

            print(f"导入音轨{first + 1}: {header}")
            print(f"简谱内容预览: {track['jianpu'][:100]}...")

            text_boxes[current_idx].delete("1.0", tk.END)
            text_boxes[current_idx].insert("1.0", result)

            select_window.destroy()

            # 如果有多个选中，询问是否导入到其他音轨
            if len(selected) > 1:
                if messagebox.askyesno("多音轨导入",
                                       f"你选择了 {len(selected)} 个音轨。\n"
                                       f"是否将剩余音轨依次导入到后续音轨？\n"
                                       f"（音轨{current_idx + 2}、{current_idx + 3}...）"):

                    next_idx = current_idx + 1
                    for sel_idx in selected[1:]:
                        if next_idx >= 16:
                            messagebox.showwarning("提示", f"音轨数量不足，只能导入到音轨{next_idx}")
                            break

                        track = tracks_data[sel_idx]

                        # 为每个轨道设置正确的调式
                        if sel_idx == 0:
                            tune_name = "G 大调"
                        elif sel_idx == 1:
                            tune_name = "A 大调"
                        else:
                            tune_name = "C 大调"

                        header = f"{tune_name},{track['instrument']},{track['bpm']}"
                        result = header + "\n" + track['jianpu']

                        text_boxes[next_idx].delete("1.0", tk.END)
                        text_boxes[next_idx].insert("1.0", result)
                        next_idx += 1

                    messagebox.showinfo("成功", f"已将 {len(selected)} 个音轨导入")
            else:
                messagebox.showinfo("成功",
                                    f"已导入音轨: {track['name']} (乐器:{track['instrument']}, BPM:{track['bpm']}, 音符数:{track.get('note_count', 0)})")

        def import_all():
            """导入所有音轨到不同音轨"""
            if len(tracks_data) > 16:
                messagebox.showwarning("警告", f"MIDI有{len(tracks_data)}个音轨，但编辑器只有16个\n将只导入前16个")

            for i, track in enumerate(tracks_data[:16]):
                # 为每个轨道设置正确的调式
                if i == 0:
                    tune_name = "G 大调"
                elif i == 1:
                    tune_name = "A 大调"
                elif i == 2:
                    tune_name = "C 大调"
                else:
                    tune_name = "C 大调"

                header = f"{tune_name},{track['instrument']},{track['bpm']}"
                result = header + "\n" + track['jianpu']
                text_boxes[i].delete("1.0", tk.END)
                text_boxes[i].insert("1.0", result)
                print(f"导入音轨{i + 1}: {header}, 长度={len(track['jianpu'])}")
            # 在 import_all 函数中添加
            for i, track in enumerate(tracks_data[:16]):
                print(f"音轨{i + 1} 简谱: {track['jianpu'][:100]}")
            select_window.destroy()
            messagebox.showinfo("成功", f"已导入 {min(len(tracks_data), 16)} 个音轨")

        tk.Button(btn_frame, text="✓ 导入选中", command=import_selected,
                  bg="#4CAF50", fg="white", padx=15).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="📀 导入全部", command=import_all,
                  bg="#2196F3", fg="white", padx=15).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="取消", command=select_window.destroy,
                  padx=15).pack(side=tk.LEFT, padx=10)

    except Exception as e:
        messagebox.showerror("错误", f"导入MIDI失败：{e}")


def parse_midi_multi_track(midi_file_path):
    """解析MIDI文件，返回所有音轨的简谱数据（每个轨道独立）"""
    # 完整的音符映射表（覆盖更多八度）
    note_map = {
        # 倍低音区 (MIDI 24-35)
        24: '1...', 25: '1#...', 26: '2...', 27: '2#...', 28: '3...', 29: '4...', 30: '4#...',
        31: '5...', 32: '5#...', 33: '6...', 34: '6#...', 35: '7...',
        # 低音区 (MIDI 36-47)
        36: '1..', 37: '1#..', 38: '2..', 39: '2#..', 40: '3..', 41: '4..', 42: '4#..',
        43: '5..', 44: '5#..', 45: '6..', 46: '6#..', 47: '7..',
        # 中音区 (MIDI 48-59)
        48: '1.', 49: '1#.', 50: '2.', 51: '2#.', 52: '3.', 53: '4.', 54: '4#.',
        55: '5.', 56: '5#.', 57: '6.', 58: '6#.', 59: '7.',
        # 中高音区 (MIDI 60-71)
        60: '1', 61: '1#', 62: '2', 63: '2#', 64: '3', 65: '4', 66: '4#',
        67: '5', 68: '5#', 69: '6', 70: '6#', 71: '7',
        # 高音区 (MIDI 72-83)
        72: "1'", 73: "1#'", 74: "2'", 75: "2#'", 76: "3'", 77: "4'", 78: "4#'",
        79: "5'", 80: "5#'", 81: "6'", 82: "6#'", 83: "7'",
        # 倍高音区 (MIDI 84-95)
        84: "1''", 85: "1#''", 86: "2''", 87: "2#''", 88: "3''", 89: "4''", 90: "4#''",
        91: "5''", 92: "5#''", 93: "6''", 94: "6#''", 95: "7''",
        # 超高音区 (MIDI 96-107)
        96: "1'''", 97: "1#'''", 98: "2'''", 99: "2#'''", 100: "3'''", 101: "4'''", 102: "4#'''",
        103: "5'''", 104: "5#'''", 105: "6'''", 106: "6#'''", 107: "7'''",
    }

    try:
        mid = mido.MidiFile(midi_file_path)
        ticks_per_beat = mid.ticks_per_beat
        tracks_result = []

        print(f"MIDI文件信息: 轨道数={len(mid.tracks)}, ticks_per_beat={ticks_per_beat}")

        for track_idx, track in enumerate(mid.tracks):
            print(f"处理轨道 {track_idx}: 消息数={len(track)}")

            # 每个轨道独立解析
            active_notes = {}
            note_events = []
            current_tempo = 280000  # 默认220 BPM

            """转换公式
python
# tempo（微秒/四分音符） → BPM（拍/分钟）
BPM = 60,000,000 / tempo

# BPM → tempo
tempo = 60,000,000 / BPM
BPM	tempo（微秒/四分音符）
60	1,000,000
80	750,000
100	600,000
120	500,000
140	428,571
160	375,000
180	333,333
200	300,000"""

            track_name = f"音轨{track_idx + 1}"
            abs_time = 0

            # 第一遍：收集音符事件
            for msg in track:
                abs_time += msg.time

                # 处理元消息
                if msg.is_meta:
                    if msg.type == 'set_tempo':
                        current_tempo = msg.tempo
                        print(f"  轨道{track_idx} 速度: {current_tempo}")
                    elif msg.type == 'track_name':
                        track_name = msg.name
                        print(f"  轨道{track_idx} 名称: {track_name}")
                    continue

                # 处理音符开
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = abs_time
                    # print(f"  音符开: {msg.note} at {abs_time}")

                # 处理音符关
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_time = active_notes[msg.note]
                        duration = abs_time - start_time
                        note_events.append((start_time, duration, msg.note))
                        del active_notes[msg.note]
                        # print(f"  音符关: {msg.note} duration={duration}")

            # 如果这个轨道没有音符，跳过
            if not note_events:
                print(f"  轨道{track_idx} 无音符，跳过")
                continue

            # 按开始时间排序
            note_events.sort(key=lambda x: x[0])

            # 生成简谱
            score_parts = []
            last_end_time = 0
            quarter_ticks = ticks_per_beat
            min_note_duration = quarter_ticks / 4  # 最小音符：16分音符

            for start_time, duration, note in note_events:
                note_str = note_map.get(note, '')
                if not note_str:
                    continue

                # 计算拍数
                beats = duration / quarter_ticks

                # 修复：四舍五入到最接近的标准时值
                # 标准时值列表（拍数）
                standard_beats = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
                closest = min(standard_beats, key=lambda x: abs(x - beats))

                # 根据最接近的标准时值决定符号
                if closest >= 3.75:
                    symbol = '----'
                elif closest >= 2.75:
                    symbol = '---'
                elif closest >= 1.75:
                    symbol = '--'
                elif closest >= 1.25:
                    symbol = '-'
                else:
                    symbol = ''

                # 对于短时值，可能需要重复音符
                if closest <= 0.5 and closest < beats - 0.1:
                    # 八分音符或更短，连续写
                    repeat = int(round(beats / 0.5))
                    if repeat > 1:
                        note_str = note_str * repeat
                        symbol = ''

                score_parts.append(note_str)
                if symbol:
                    score_parts.append(symbol)

                # 添加小节分隔符（每16拍）
                # 可选，根据需要取消注释
                # if (start_time // (quarter_ticks * 4)) > (last_end_time // (quarter_ticks * 4)):
                #     score_parts.append('|')

                last_end_time = start_time + duration

            # 合并简谱字符串
            jianpu_text = ''.join(score_parts)

            # 限制长度
            if len(jianpu_text) > 3000:
                jianpu_text = jianpu_text[:3000]

            # 计算BPM
            bpm = int(mido.tempo2bpm(current_tempo))

            # 尝试从轨道中提取音色（Program Change）
            track_instrument = 0
            for msg in track:
                if msg.type == 'program_change':
                    track_instrument = msg.program
                    break

            # 尝试从轨道中提取调式（Key Signature）
            track_tune = "C 大调"
            for msg in track:
                if msg.is_meta and msg.type == 'key_signature':
                    track_tune = msg.key.replace('b', '降').replace('#', '升')
                    if 'm' in track_tune:
                        track_tune = track_tune.replace('m', '小调')
                    else:
                        track_tune = track_tune + '大调'
                    break

            tracks_result.append({
                'name': track_name,
                'bpm': bpm,
                'jianpu': jianpu_text,
                'tune': track_tune,
                'instrument': track_instrument,
                'track_index': track_idx,
                'note_count': len(note_events)  # 音符数量
            })

            print(f"  轨道{track_idx} 转换完成: {len(note_events)}个音符, 简谱长度={len(jianpu_text)}")

        if not tracks_result:
            print("未找到任何有音符的轨道")
            return None

        print(f"总共转换了 {len(tracks_result)} 个音轨")
        return tracks_result

    except Exception as e:
        print(f"解析MIDI错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_simple_image():
    """导出多音轨简谱图片（简单版：纯文本）"""
    # 收集所有有内容的音轨
    tracks_content = []
    for i, text_box in enumerate(text_boxes):
        content = text_box.get("1.0", "end-1c").strip()
        if content:
            tracks_content.append((i, content))

    if not tracks_content:
        messagebox.showwarning("警告", "没有可导出的内容")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg"), ("所有文件", "*.*")]
    )

    if not file_path:
        return

    try:
        # 计算图片尺寸
        line_height = 25
        title_height = 30
        margin = 20
        line_width = 1100

        total_lines = 0
        for idx, content in tracks_content:
            lines = content.split('\n')
            total_lines += len(lines) + 2  # 每个音轨加标题和空行

        img_height = margin * 10 + total_lines * line_height + len(tracks_content) * title_height

        img = Image.new('RGB', (line_width + margin * 2, img_height), color='white')
        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            font = ImageFont.truetype("msyh.ttc", 14)
            title_font = ImageFont.truetype("msyh.ttc", 16)
        except:
            try:
                font = ImageFont.truetype("simhei.ttf", 14)
                title_font = ImageFont.truetype("simhei.ttf", 16)
            except:
                font = ImageFont.load_default()
                title_font = ImageFont.load_default()

        y = margin

        for idx, content in tracks_content:
            # 绘制音轨标题
            draw.text((margin, y), f"【音轨 {idx + 1}】", font=title_font, fill='#3333FF')
            y += title_height

            # 绘制内容
            lines = content.split('\n')
            for line in lines:
                # 分行显示（每行80字符）
                for i in range(0, len(line), 80):
                    draw.text((margin, y), line[i:i + 80], font=font, fill='black')
                    y += line_height

            # 空行分隔
            y += line_height

        img.save(file_path)
        messagebox.showinfo("成功", f"简谱图片已保存到：\n{file_path}")

    except Exception as e:
        messagebox.showerror("错误", f"导出图片失败：{e}")


def export_professional_image():
    """导出多音轨简谱图片（专业版：带格式排版）"""
    # 收集所有有内容的音轨
    tracks_content = []
    for i, text_box in enumerate(text_boxes):
        content = text_box.get("1.0", "end-1c").strip()
        if content:
            # 解析头部信息
            lines = content.split('\n')
            header = lines[0] if lines else "C 大调,0,120"
            music = '\n'.join(lines[1:]) if len(lines) > 1 else ""

            # 解析调式、乐器、速度
            parts = header.split(',')
            tune = parts[0] if len(parts) > 0 else "C 大调"
            instrument = parts[1] if len(parts) > 1 else "0"
            bpm = parts[2] if len(parts) > 2 else "120"

            tracks_content.append({
                'index': i,
                'tune': tune,
                'instrument': instrument,
                'bpm': bpm,
                'music': music
            })

    if not tracks_content:
        messagebox.showwarning("警告", "没有可导出的内容")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg"), ("所有文件", "*.*")]
    )

    if not file_path:
        return

    try:
        # 专业版排版参数
        page_width = 1200
        margin = 30
        line_height = 28
        title_height = 35
        header_height = 25
        measure_width = 60  # 每小节宽度

        # 计算总行数
        total_lines = 0
        for track in tracks_content:
            music = track['music'].replace('|', ' ')
            # 按每40字符一行计算
            lines_count = max(1, (len(music) + 39) // 40)
            total_lines += lines_count + 3  # 标题 + 头部 + 空行

        img_height = margin * 8 + total_lines * line_height + len(tracks_content) * title_height

        img = Image.new('RGB', (page_width, img_height), color='white')
        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            title_font = ImageFont.truetype("msyh.ttc", 18)
            header_font = ImageFont.truetype("msyh.ttc", 12)
            music_font = ImageFont.truetype("Consolas.ttf", 16)
        except:
            try:
                title_font = ImageFont.truetype("simhei.ttf", 18)
                header_font = ImageFont.truetype("simhei.ttf", 12)
                music_font = ImageFont.truetype("simhei.ttf", 16)
            except:
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                music_font = ImageFont.load_default()

        y = margin

        # 绘制标题
        draw.text((margin, y), "=" * 90, font=title_font, fill='#999999')
        y += line_height
        draw.text((margin, y), "           标准数字简谱播放器 - 乐谱导出", font=title_font, fill='#3333FF')
        y += line_height
        draw.text((margin, y), "=" * 90, font=title_font, fill='#999999')
        y += line_height + 10

        for track in tracks_content:
            # 音轨标题栏
            draw.rectangle([margin, y, page_width - margin, y + title_height],
                           fill='#EEEEEE', outline='#CCCCCC')
            draw.text((margin + 10, y + 5), f"音轨 {track['index'] + 1}",
                      font=title_font, fill='#3333FF')
            y += title_height

            # 音轨设置信息
            info_text = f"调式: {track['tune']}    乐器: {track['instrument']}    BPM: {track['bpm']}"
            draw.text((margin + 10, y), info_text, font=header_font, fill='#666666')
            y += header_height

            # 绘制分隔线
            draw.line([(margin, y), (page_width - margin, y)], fill='#CCCCCC', width=1)
            y += 5

            # 简谱内容（自动换行）
            music = track['music']
            # 添加小节线分隔（每8拍添加一个）
            formatted_music = music
            counter = 0
            result_parts = []
            for ch in music:
                result_parts.append(ch)
                if ch.isdigit():
                    counter += 1
                    if counter % 16 == 0:
                        result_parts.append(' | ')
            formatted_music = ''.join(result_parts)

            # 分行显示
            line_width_chars = 45
            for i in range(0, len(formatted_music), line_width_chars):
                line = formatted_music[i:i + line_width_chars]
                draw.text((margin + 10, y), line, font=music_font, fill='black')
                y += line_height

            # 空行分隔
            y += 15

        # 绘制底部版权信息
        from datetime import datetime
        copyright_text = f"Generated by 标准数字简谱播放器  {datetime.now().strftime('%Y-%m-%d')}"
        draw.text((margin, y), copyright_text, font=header_font, fill='#999999')

        img.save(file_path)
        messagebox.showinfo("成功", f"专业版简谱图片已保存到：\n{file_path}")

    except Exception as e:
        messagebox.showerror("错误", f"导出专业版图片失败：{e}")


# ==================== 新增功能结束 ====================


def export_midi():
    try:
        file_path = filedialog.asksaveasfilename(defaultextension=".mid", filetypes=[("MIDI Files", "*.mid")])
        if not file_path:
            return

        mid = mido.MidiFile(ticks_per_beat=480)
        all_tracks = []
        max_track_length = 0

        for i in range(16):
            notes_str = text_boxes[i].get("1.0", "end-1c")
            if not notes_str.strip():
                continue

            notes, instrument, speed, tune = parse_notes_and_settings(notes_str)
            if not notes:
                continue

            track_events = []
            current_time = 0

            program_msg = mido.Message('program_change', program=instrument, channel=i, time=0)
            track_events.append((0, program_msg))

            for note in notes:
                note_number, duration, velocity = process_note(note, speed)
                # note_number = convert_tune(note_number, tune)

                bpm = 120
                ms_per_beat = 60000 / bpm
                ms_per_tick = ms_per_beat / mid.ticks_per_beat
                tick_duration = int(duration / ms_per_tick)

                if note_number is not None:
                    track_events.append(
                        (current_time, mido.Message('note_on', note=note_number, velocity=velocity, channel=i)))
                    track_events.append((current_time + tick_duration,
                                         mido.Message('note_off', note=note_number, velocity=velocity, channel=i)))
                current_time += tick_duration

            if track_events:
                all_tracks.append((instrument, tune, track_events))
                max_track_length = max(max_track_length, current_time)

        if not all_tracks:
            messagebox.showinfo("导出提示", "没有可导出的音轨")
            return

        for i, (instrument, tune, track_events) in enumerate(all_tracks):
            track = mido.MidiTrack()
            mid.tracks.append(track)

            track_name = f'Track {i + 1} - {tune}'
            name_bytes = track_name.encode('utf-8')
            track.append(mido.MetaMessage('track_name', name=name_bytes.decode('latin-1', 'replace')))

            track_events.sort(key=lambda x: x[0])
            prev_time = 0

            for time_ticks, event in track_events:
                delta = time_ticks - prev_time
                track.append(event.copy(time=delta))
                prev_time = time_ticks

        mid.save(file_path)
        messagebox.showinfo("导出成功", f"文件已成功导出到 {file_path}")

    except Exception as e:
        messagebox.showerror("导出错误", f"导出过程中出现错误: {str(e)}")


def display_textbox(index):
    global current_displayed_index
    for i, text_box in enumerate(text_boxes):
        if i == index:
            text_box.place(x=10, y=10, width=400, height=400)
        else:
            text_box.place_forget()
    current_displayed_index = index


def clear_all_textboxes():
    for text_box in text_boxes:
        text_box.delete("1.0", tk.END)


def generate_random_notes():
    z = ["1..", "2..", "3..", "4..", "5..", "6..", "7..", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "1", "2", "3", "4",
         "5",
         "6", "7", "1'", "2'", "3'", "4'", "5'", "6'", "7'", "1''", "2''", "3''", "4''", "5''", "6''", "7''", "1#",
         "2#", "4#", "5#", "6#"]
    a = ["", "-", "--"]
    random_notes = []
    for _ in range(110):
        random_note = random.choice(z) + random.choice(a)
        random_notes.append(random_note)
    text_boxes[2].delete("1.0", tk.END)
    text_boxes[2].insert(tk.END, "G 大调,0,500\n" + "".join(random_notes))


def generate_random_notes1():
    z1 = ["1..", "2..", "3..", "4..", "5..", "6..", "7..", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "1", "2", "3", "4",
          "5",
          "6", "7", "1'", "2'", "3'", "4'", "5'", "6'", "7'", "1''", "2''", "3''", "4''", "5''", "6''", "7''", "1#",
          "2#", "4#", "5#", "6#"]
    a1 = ["", "-", "--"]
    random_notes = []
    for _ in range(110):
        random_note = random.choice(z1) + random.choice(a1)
        random_notes.append(random_note)
    text_boxes[3].delete("1.0", tk.END)
    text_boxes[3].insert(tk.END, "G 大调,0,500\n" + "".join(random_notes))


def generate_random_notes2():
    z2 = ["1..", "2..", "3..", "4..", "5..", "6..", "7..", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "1", "2", "3", "4",
          "5",
          "6", "7", "1'", "2'", "3'", "4'", "5'", "6'", "7'", "1''", "2''", "3''", "4''", "5''", "6''", "7''", "1#",
          "2#", "4#", "5#", "6#"]
    a2 = ["", "-", "--"]
    random_notes = []
    for _ in range(110):
        random_note = random.choice(z2) + random.choice(a2)
        random_notes.append(random_note)
    text_boxes[4].delete("1.0", tk.END)
    text_boxes[4].insert(tk.END, "G 大调,0,500\n" + "".join(random_notes))


def play_music_together(track_index):
    global is_playing, loop_playback
    is_playing = True
    is_paused = False
    if 'pause_button' in globals():
        pause_button.config(text="暂停")

    notes_str = text_boxes[track_index].get("1.0", "end-1c")
    if notes_str.strip():
        notes, instrument, speed, tune = parse_notes_and_settings(notes_str)
        thread = threading.Thread(target=play_next_note, args=(notes, instrument, tune, speed))
        thread.start()
        thread.join()

    is_playing = False
    if 'pause_button' in globals():
        pause_button.config(text="暂停")


def toggle_loop():
    global loop_playback
    loop_playback = loop_var.get()


# ==================== 菜单功能实现 ====================

def show_midi_settings():
    """MIDI设备设置窗口"""
    settings_window = tk.Toplevel(root)
    settings_window.title("MIDI设备设置")
    settings_window.geometry("400x300")
    settings_window.transient(root)
    settings_window.grab_set()

    tk.Label(settings_window, text="MIDI输出设备选择", font=("Arial", 12, "bold")).pack(pady=10)

    devices = []
    for i in range(pygame.midi.get_count()):
        info = pygame.midi.get_device_info(i)
        devices.append(f"{i}: {info[1].decode() if info[1] else 'Unknown'}")

    if devices:
        device_listbox = tk.Listbox(settings_window, height=8)
        for device in devices:
            device_listbox.insert(tk.END, device)
        device_listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        def apply_device():
            global midi_out
            selection = device_listbox.curselection()
            if selection:
                device_id = int(devices[selection[0]].split(":")[0])
                if midi_out:
                    midi_out.close()
                try:
                    midi_out = pygame.midi.Output(device_id)
                    messagebox.showinfo("成功", f"已切换到设备: {devices[selection[0]]}")
                    settings_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"无法打开MIDI设备: {e}")

        tk.Button(settings_window, text="应用", command=apply_device, width=15).pack(pady=10)
    else:
        tk.Label(settings_window, text="未找到任何MIDI设备", fg="red").pack(pady=20)

    tk.Button(settings_window, text="关闭", command=settings_window.destroy, width=10).pack(pady=5)


def show_volume_settings():
    """音量设置窗口"""
    global volume
    volume_window = tk.Toplevel(root)
    volume_window.title("音量设置")
    volume_window.geometry("350x200")
    volume_window.transient(root)
    volume_window.grab_set()

    tk.Label(volume_window, text="主音量设置", font=("Arial", 12, "bold")).pack(pady=10)

    current_volume = tk.IntVar(value=volume)
    volume_scale = tk.Scale(volume_window, from_=0, to=127, orient=tk.HORIZONTAL,
                            label="音量 (0-127)", variable=current_volume, length=250)
    volume_scale.pack(pady=20)

    def apply_volume():
        global volume
        volume = current_volume.get()
        messagebox.showinfo("成功", f"音量已设置为 {volume}")
        volume_window.destroy()

    tk.Button(volume_window, text="应用", command=apply_volume, width=15).pack(pady=10)
    tk.Button(volume_window, text="取消", command=volume_window.destroy, width=10).pack(pady=5)


def show_default_key_settings():
    """默认调式设置窗口"""
    key_window = tk.Toplevel(root)
    key_window.title("默认调式设置")
    key_window.geometry("300x250")
    key_window.transient(root)
    key_window.grab_set()

    tk.Label(key_window, text="选择默认调式", font=("Arial", 12, "bold")).pack(pady=10)

    keys = ["C 大调", "C# 大调", "D 大调", "D# 大调", "E 大调", "F 大调",
            "F# 大调", "G 大调", "G# 大调", "A 大调", "A# 大调", "B 大调"]
    selected_key = tk.StringVar(value="C 大调")

    key_combo = ttk.Combobox(key_window, textvariable=selected_key, values=keys, state="readonly", width=15)
    key_combo.pack(pady=20)

    def save_default_key():
        messagebox.showinfo("成功", f"默认调式已设置为 {selected_key.get()}\n(下次新建乐谱时生效)")
        key_window.destroy()

    tk.Button(key_window, text="保存", command=save_default_key, width=15).pack(pady=10)
    tk.Button(key_window, text="取消", command=key_window.destroy, width=10).pack(pady=5)


def show_default_tempo_settings():
    """默认速度设置窗口"""
    tempo_window = tk.Toplevel(root)
    tempo_window.title("默认速度设置")
    tempo_window.geometry("350x200")
    tempo_window.transient(root)
    tempo_window.grab_set()

    tk.Label(tempo_window, text="默认速度设置", font=("Arial", 12, "bold")).pack(pady=10)
    tk.Label(tempo_window, text="速度值越小越快，越大越慢").pack()

    current_tempo = tk.IntVar(value=500)
    tempo_scale = tk.Scale(tempo_window, from_=100, to=1000, orient=tk.HORIZONTAL,
                           label="默认速度 (毫秒/拍)", variable=current_tempo, length=250)
    tempo_scale.pack(pady=20)

    def save_default_tempo():
        messagebox.showinfo("成功", f"默认速度已设置为 {current_tempo.get()}\n(下次新建乐谱时生效)")
        tempo_window.destroy()

    tk.Button(tempo_window, text="保存", command=save_default_tempo, width=15).pack(pady=10)
    tk.Button(tempo_window, text="取消", command=tempo_window.destroy, width=10).pack(pady=5)


def show_help():
    """显示使用说明"""
    help_window = tk.Toplevel(root)
    help_window.title("使用说明")
    help_window.geometry("650x500")
    help_window.transient(root)

    help_text = tk.Text(help_window, wrap="word")
    help_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    help_content = f"""
=== MIDI简谱播放器 v{VERSION} 使用说明 ===

一、基本操作
1. 程序支持16个独立音轨，每个音轨可以独立设置调式、乐器和速度
2. 点击音轨旁的"显示音轨X"按钮可以切换编辑不同的音轨
3. 点击"播放全部音轨"可以同时播放所有有内容的音轨
4. 使用"暂停"按钮暂停播放，再次点击继续播放
5. 使用"停止"按钮停止所有音轨播放

二、简谱输入格式
1. 每个音轨的第一行是设置行，格式为：调式,乐器编号,速度
   例如：C 大调,0,500

2. 支持的调式：
   C 大调、C# 大调、D 大调、D# 大调、E 大调、F 大调、
   F# 大调、G 大调、G# 大调、A 大调、A# 大调、B 大调

3. 乐器编号：
   0: 大钢琴    1: 明亮的钢琴    2: 电钢琴

4. 速度：数值越小播放越快，越大播放越慢（建议100-800）

三、简谱音符语法
1. 基本音符：1 2 3 4 5 6 7（对应do re mi fa sol la si）
2. 高八度：使用 ' 符号，如 1' 表示高一个八度的do
3. 低八度：使用 . 符号，如 1. 表示低一个八度的do
4. 升号：使用 # 符号，如 1# 表示升do
5. 延长时值：使用 - 符号，每个-使时值乘以1.5倍
   例如：5-- 表示时值延长两次
6. 休止符：使用 0 表示休止
7. 音符组：[音符组] 表示一组音符占一拍
8. 括号组：(音符组) 表示拍长减半

四、快捷键提示
1. 右键点击文本框可弹出编辑菜单（剪切、复制、粘贴等）
2. 点击"随机谱曲"按钮可以生成随机旋律

五、导出功能
点击"导出"按钮可以将当前乐谱导出为MIDI文件

六、循环播放
勾选"循环播放"复选框后，音乐会循环播放
"""

    help_text.insert("1.0", help_content)
    help_text.config(state=tk.DISABLED)

    tk.Button(help_window, text="关闭", command=help_window.destroy, width=10).pack(pady=10)


def show_notation_help():
    """简谱语法说明"""
    notation_window = tk.Toplevel(root)
    notation_window.title("简谱语法说明")
    notation_window.geometry("600x450")
    notation_window.transient(root)

    notation_text = tk.Text(notation_window, wrap="word")
    notation_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    notation_content = """
=== 简谱语法详细说明 ===

一、音符与音高
1: do (中央C)     2: re     3: mi     4: fa
5: sol            6: la     7: si     0: 休止符

二、八度标记
'  : 高八度（每加一个'升一个八度）
.  : 低八度（每加一个.降一个八度）

示例：
1   - 中央C
1'  - 高八度C
1'' - 高两个八度C
1.  - 低八度C
1.. - 低两个八度C

三、升降号
# : 升半音（仅支持 1#,2#,4#,5#,6#）

示例：
1# - 升do
5# - 升sol

四、时值标记
- : 延长时值，每个-使时值乘以1.5倍

示例：
1   - 基本时值（1拍）
1-  - 1.5倍时值
1-- - 2.25倍时值

五、组合标记
[ ] : 方括号内的音符组整体占一拍
( ) : 圆括号内的音符组拍长减半

示例：
[123] - 三个音符一起占一拍
(56)  - 拍长减半

六、完整示例
"5-351'--76-1'-5---" 表示一段旋律

七、调式转换
程序会根据设置的调式自动转换音符的音高

注意：
- 音符之间不需要加空格
- 可以使用竖线 | 分隔小节，便于阅读（不影响播放）
- 每行开头可添加设置行，格式：调式,乐器编号,速度
"""

    notation_text.insert("1.0", notation_content)
    notation_text.config(state=tk.DISABLED)

    tk.Button(notation_window, text="关闭", command=notation_window.destroy, width=10).pack(pady=10)


def show_about():
    """显示关于信息"""
    about_text = f"""{APP_NAME} v{VERSION}

一个功能强大的MIDI简谱播放器 v{VERSION}

 ✨ V2.0 新增功能

| 功能 | 说明 |
|||
| 🎼 MIDI文件导入 | 支持导入标准MIDI文件，自动转换为简谱文本（100%准确） |
| 🎹 多音轨支持 | MIDI多音轨可分别导入到不同音轨 |
| 🖼️ 简谱图片导出 | 将编辑好的简谱导出为PNG图片，方便打印分享 |
| 🔧 音轨独立设置 | 每个音轨可单独设置音色、速度、调式 |
| 📊 状态栏提示 | 实时显示软件状态和操作反馈 |



 🔧 V2.0 优化改进

- 优化MIDI播放稳定性，减少卡顿
- 改进音符解析算法，支持更多简谱语法
- 优化界面布局，操作更便捷
- 增加快捷键支持（F5播放、Space暂停、Esc停止）
- 完善右键菜单功能（全选复制、全选删除）



技术栈：
• Python + Tkinter
• PyGame MIDI
• Mido

版权信息：
【版权声明】：
本软件为作者原创独立开发，保留所有权利。未经授权禁止二次上传、倒卖、修改后冒充原创。
本软件仅为个人学习/交流使用，禁止用于商业用途。


最后更新：2026年5月"""

    messagebox.showinfo("关于", about_text)


# 本软件为开源软件，仅供学习交流使用

def show_author():
    """显示作者信息"""
    author_text = f"""=== 作者信息 ===

软件名称：MIDI简谱播放器 v{VERSION}
版本：v{VERSION}

作者：叶海宁

联系方式：
• 微信: 17876586815
• QQ1: 791687349
• QQ2: 282615109
• Email: 791687349@qq.com
• GitHub: github.com/YHN282615109
• Gitee：https://gitee.com/YHN282615109

简谱软件QQ交流群： 
群号1: 1040271049
群号2: 954811008

特别感谢：
感谢所有使用本软件的用户！

欢迎提供宝贵意见和建议！"""

    messagebox.showinfo("作者信息", author_text)


def show_contact():
    """显示联系信息"""
    contact_window = tk.Toplevel(root)
    contact_window.title("联系我们")
    contact_window.geometry("400x600")
    contact_window.transient(root)

    contact_text = tk.Text(contact_window, wrap="word")
    contact_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    contact_content = """
=== 联系我们 ===

如有问题、建议或合作意向，欢迎通过以下方式联系我们：

1. 电子邮件：
791687349@qq.com

2. 官方QQ：
• QQ1: 791687349
• QQ2: 282615109


3. 微信号：
17876586815

4. 官方博客：
https://blog.csdn.net/qq_32257509?spm=1010.2135.3001.10640


5. GitHub Issues：
github.com/YHN282615109

6. Gitee Issues：   
https://gitee.com/YHN282615109


7. 简谱软件QQ交流群：
群号1: 1040271049
群号2: 954811008


我们会在24小时内回复您的问题！

=== 问题反馈格式 ===
为了更快解决您的问题，请提供：
- 软件版本号
- 操作系统
- 问题详细描述
- 错误截图（如有）
- 复现步骤
"""

    contact_text.insert("1.0", contact_content)
    contact_text.config(state=tk.DISABLED)

    def copy_email():
        root.clipboard_clear()
        root.clipboard_append("""
联系方式：

1. 电子邮件：
   791687349@qq.com

2. 官方QQ：
• QQ1: 791687349
• QQ2: 282615109

3. 微信号：
   17876586815

4. 官方博客：
   https://blog.csdn.net/qq_32257509?spm=1010.2135.3001.10640

5. GitHub Issues：
   github.com/YHN282615109

6. Gitee Issues：   
   https://gitee.com/YHN282615109



7. 简谱软件QQ交流群：
    群号1: 1040271049
    群号2: 954811008


""")
        messagebox.showinfo("复制成功", "联系方式已复制到剪贴板")

    tk.Button(contact_window, text="复制联系方式", command=copy_email).pack(pady=5)
    tk.Button(contact_window, text="关闭", command=contact_window.destroy, width=10).pack(pady=10)


def submit_feedback():
    """提交建议窗口"""
    feedback_window = tk.Toplevel(root)
    feedback_window.title("提交建议")
    feedback_window.geometry("500x400")
    feedback_window.transient(root)

    tk.Label(feedback_window, text="您的建议对我们很重要！", font=("Arial", 12, "bold")).pack(pady=10)

    tk.Label(feedback_window, text="建议类型:").pack(anchor="w", padx=20)
    feedback_type = ttk.Combobox(feedback_window, values=["功能建议", "界面改进", "性能优化", "其他"], state="readonly")
    feedback_type.pack(pady=5, padx=20, fill="x")
    feedback_type.current(0)

    tk.Label(feedback_window, text="建议内容:").pack(anchor="w", padx=20, pady=(10, 0))
    feedback_text = tk.Text(feedback_window, height=10)
    feedback_text.pack(pady=5, padx=20, fill="both", expand=True)

    tk.Label(feedback_window, text="联系方式（选填）:").pack(anchor="w", padx=20, pady=(10, 0))
    contact_entry = tk.Entry(feedback_window)
    contact_entry.pack(pady=5, padx=20, fill="x")

    def submit():
        if feedback_text.get("1.0", "end-1c").strip():
            messagebox.showinfo("提交成功", "感谢您的建议！我们会认真考虑并改进。\n\n（演示版，实际发送功能需要配置邮件服务）")
            feedback_window.destroy()
        else:
            messagebox.showwarning("提示", "请填写建议内容")

    tk.Button(feedback_window, text="提交", command=submit, width=15).pack(pady=10)


def report_issue():
    """报告问题窗口"""
    issue_window = tk.Toplevel(root)
    issue_window.title("报告问题")
    issue_window.geometry("550x550")
    issue_window.transient(root)

    tk.Label(issue_window, text="问题反馈", font=("Arial", 12, "bold")).pack(pady=10)

    tk.Label(issue_window, text="问题类型:").pack(anchor="w", padx=20)
    issue_type = ttk.Combobox(issue_window, values=["播放问题", "导出问题", "界面问题", "崩溃/错误", "其他"], state="readonly")
    issue_type.pack(pady=5, padx=20, fill="x")
    issue_type.current(0)

    tk.Label(issue_window, text="问题描述:").pack(anchor="w", padx=20, pady=(10, 0))
    issue_text = tk.Text(issue_window, height=10)
    issue_text.pack(pady=5, padx=20, fill="both", expand=True)

    tk.Label(issue_window, text="复现步骤:").pack(anchor="w", padx=20, pady=(10, 0))
    steps_text = tk.Text(issue_window, height=5)
    steps_text.pack(pady=5, padx=20, fill="both", expand=True)

    tk.Label(issue_window, text="联系方式（邮箱）:").pack(anchor="w", padx=20, pady=(10, 0))
    email_entry = tk.Entry(issue_window)
    email_entry.pack(pady=5, padx=20, fill="x")

    def submit_issue():
        if issue_text.get("1.0", "end-1c").strip():
            messagebox.showinfo("提交成功", "问题已提交！我们会尽快修复。\n\n（演示版，实际发送功能需要配置邮件服务）")
            issue_window.destroy()
        else:
            messagebox.showwarning("提示", "请填写问题描述")

    tk.Button(issue_window, text="提交", command=submit_issue, width=15).pack(pady=10)


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持开发环境和打包后的exe"""
    try:
        # PyInstaller 创建临时文件夹，将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def show_donate():
    """显示捐赠信息"""
    from PIL import Image, ImageTk

    donate_window = tk.Toplevel(root)
    donate_window.title("捐赠/赞助")
    donate_window.geometry("700x800")
    donate_window.transient(root)
    donate_window.grab_set()

    tk.Label(donate_window, text="支持我们", font=("Arial", 14, "bold")).pack(pady=10)
    tk.Label(donate_window, text="您的支持是我们前进的动力！").pack(pady=5)
    ttk.Label(donate_window, text=f"""
            ╔═══════════════╗
            ║      感谢您的支持！          ║
            ║                            ║
            ║  您的捐赠将帮助我们：          ║
            ║  • 持续开发和维护软件          ║
            ║  • 增加更多功能               ║
            ║  • 提供更好的技术支持          ║
            ║                            ║
            ║  {APP_NAME} 开发者       ║
            ╚════════════════╝

            【赞助方式】
                            \n\n""", font=("", 14)).pack(pady=10)
    # 图片横向放置的框架
    img_frame = tk.Frame(donate_window)
    img_frame.pack(pady=10)

    global donate_images
    if 'donate_images' not in globals():
        donate_images = {}

    # 使用 get_resource_path 获取图片路径
    wechat_path = get_resource_path("微信收款码.png")
    if os.path.exists(wechat_path):
        try:
            wechat_img = Image.open(wechat_path)
            wechat_img = wechat_img.resize((250, 250), Image.Resampling.LANCZOS)
            donate_images['wechat'] = ImageTk.PhotoImage(wechat_img)
            wechat_label = tk.Label(img_frame, image=donate_images['wechat'], text="微信支付", compound="top")
            wechat_label.pack(side=tk.LEFT, padx=20)
        except Exception as e:
            tk.Label(img_frame, text="微信码加载失败", fg="red").pack(side=tk.LEFT, padx=20)
    else:
        tk.Label(img_frame, text="微信码不存在", fg="red").pack(side=tk.LEFT, padx=20)

    alipay_path = get_resource_path("支付宝收款码.jpg")
    if os.path.exists(alipay_path):
        try:
            alipay_img = Image.open(alipay_path)
            alipay_img = alipay_img.resize((250, 250), Image.Resampling.LANCZOS)
            donate_images['alipay'] = ImageTk.PhotoImage(alipay_img)
            alipay_label = tk.Label(img_frame, image=donate_images['alipay'], text="支付宝支付", compound="top")
            alipay_label.pack(side=tk.LEFT, padx=20)
        except Exception as e:
            tk.Label(img_frame, text="支付宝码加载失败", fg="red").pack(side=tk.LEFT, padx=20)
    else:
        tk.Label(img_frame, text="支付宝码不存在", fg="red").pack(side=tk.LEFT, padx=20)

    tk.Label(donate_window, text="感谢您的慷慨捐赠！", fg="green").pack(pady=5)
    tk.Label(donate_window, text="所有捐赠将用于软件维护和功能开发。").pack()
    tk.Button(donate_window, text="关闭", command=donate_window.destroy, width=15).pack(pady=15)


def show_support():
    """支持我们窗口"""
    support_window = tk.Toplevel(root)
    support_window.title("支持我们")
    support_window.geometry("400x500")
    support_window.transient(root)

    support_text = """
    === 其他支持方式 ===

    除了资金赞助，您还可以通过以下方式支持我们：

    ⭐ 给项目点个Star（GitHub、gitee）

    📢 向朋友推荐本软件

    📝 撰写使用心得和评测

    🐛 反馈Bug和建议

    🌐 帮助翻译和文档编写

    🎵 分享您创作的乐谱

    您的每一次支持都很重要！
    """

    tk.Label(support_window, text=support_text, justify="left", font=("Arial", 10)).pack(pady=20, padx=20)
    tk.Button(support_window, text="关闭", command=support_window.destroy, width=10).pack(pady=20)


def check_update():
    """检查更新"""
    update_info = f"""=== 版本检查 ===

当前版本：v{VERSION}

最新版本：2.1 

 ✨ V{VERSION} 新增功能

| 功能 | 说明 |
|||
| 🎼 MIDI文件导入 | 支持导入标准MIDI文件，自动转换为简谱文本（100%准确） |
| 🎹 多音轨支持 | MIDI多音轨可分别导入到不同音轨 |
| 🖼️ 简谱图片导出 | 将编辑好的简谱导出为PNG图片，方便打印分享 |
| 🔧 音轨独立设置 | 每个音轨可单独设置音色、速度、调式 |
| 📊 状态栏提示 | 实时显示软件状态和操作反馈 |



 🔧 V{VERSION} 优化改进

- 优化MIDI播放稳定性，减少卡顿
- 改进音符解析算法，支持更多简谱语法
- 优化界面布局，操作更便捷
- 增加快捷键支持（F5播放、Space暂停、Esc停止）
- 完善右键菜单功能（全选复制、全选删除）



 🐛 V{VERSION} 问题修复

- 修复暂停后继续播放时间不同步的问题
- 修复导出MIDI时音轨通道分配错误
- 修复随机谱曲功能偶尔报错的问题


更新内容：
• 新增更多乐器支持
• 优化播放性能
• 修复已知Bug
• 增加MIDI输入功能

是否要下载最新版本？
(演示版，实际更新功能需要配置网络服务)
"""

    result = messagebox.askyesno("检查更新", update_info)
    if result:
        webbrowser.open("https://gitee.com/YHN282615109")


def upgrade_version():
    """版本升级"""
    upgrade_info = f"""=== 版本升级 ===

当前版本：{VERSION}

升级到专业版可获得以下功能：

✨ 专业版特性 ✨
• 无限音轨支持
• 更多乐器音色（128种）
• MIDI输入录制功能
• 乐谱保存/加载
• 批量导出功能
• 技术支持优先响应

升级费用：¥39.9 (永久使用)

是否前往升级页面？
(演示版，实际升级功能需要配置支付接口)
"""

    result = messagebox.askyesno("版本升级", upgrade_info)
    if result:
        webbrowser.open("https://gitee.com/YHN282615109")


# ==================== 创建主窗口 ====================

root = tk.Tk()
root.title(f"{APP_NAME} v{VERSION}")
root.geometry("900x800")

# ==================== 创建菜单栏 ====================
menubar = tk.Menu(root)

# 文件菜单
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="新建乐谱", command=clear_all_textboxes)
file_menu.add_separator()
file_menu.add_command(label="导入MIDI文件（多音轨）", command=import_midi_file)  # 新增
file_menu.add_separator()
file_menu.add_command(label="导出MIDI", command=export_midi)
file_menu.add_separator()
file_menu.add_command(label="导出简谱图片（简单版）", command=export_simple_image)  # 新增
file_menu.add_command(label="导出简谱图片（专业版）", command=export_professional_image)  # 新增
file_menu.add_separator()
file_menu.add_command(label="退出", command=lambda: on_closing())
menubar.add_cascade(label="文件", menu=file_menu)

# 设置/选项菜单
settings_menu = tk.Menu(menubar, tearoff=0)
settings_menu.add_command(label="MIDI设备设置", command=show_midi_settings)
settings_menu.add_command(label="音量设置", command=show_volume_settings)
settings_menu.add_separator()
settings_menu.add_command(label="默认调式设置", command=show_default_key_settings)
settings_menu.add_command(label="默认速度设置", command=show_default_tempo_settings)
menubar.add_cascade(label="设置/选项", menu=settings_menu)

# 帮助菜单
help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="使用说明", command=show_help)
help_menu.add_command(label="简谱语法说明", command=show_notation_help)
menubar.add_cascade(label="帮助", menu=help_menu)

# 关于菜单
about_menu = tk.Menu(menubar, tearoff=0)
about_menu.add_command(label="版本信息", command=show_about)
about_menu.add_command(label="作者信息", command=show_author)
menubar.add_cascade(label="关于", menu=about_menu)

# 反馈菜单
feedback_menu = tk.Menu(menubar, tearoff=0)
feedback_menu.add_command(label="联系我们", command=show_contact)
feedback_menu.add_command(label="提交建议", command=submit_feedback)
feedback_menu.add_command(label="报告问题", command=report_issue)
menubar.add_cascade(label="反馈问题", menu=feedback_menu)

# 赞助菜单
donate_menu = tk.Menu(menubar, tearoff=0)
donate_menu.add_command(label="捐赠/赞助", command=show_donate)
donate_menu.add_command(label="支持我们", command=show_support)
menubar.add_cascade(label="捐赠/赞助", menu=donate_menu)

# 更新菜单
update_menu = tk.Menu(menubar, tearoff=0)
update_menu.add_command(label="检查更新", command=check_update)
update_menu.add_command(label="版本升级", command=upgrade_version)
menubar.add_cascade(label="检查更新/版本升级", menu=update_menu)

root.config(menu=menubar)

# ==================== 创建控件 ====================

# 创建16个文本框和对应的按钮
for i in range(16):
    text_box = tk.Text(root, wrap="word", height=5)
    text_box.pack(pady=5)
    text_box.place(x=10, y=10, width=900, height=50)
    text_boxes.append(text_box)

    play_button = tk.Button(root, text=f"显示音轨{i + 1}", command=lambda i=i: display_textbox(i))
    play_button.pack(pady=5)
    play_button.place(x=430, y=5 + i * 35, width=100, height=40)
    play_buttons.append(play_button)

    if i == 0:
        text_box.insert(tk.END,
                        "G 大调,40,200\n5-351'--76-1'-5---5-123-212----5-351'--76-1'-5---5-234--7.1----6-1'-1'---7-671'---671'665312----5-351'--76-1'-5---5-234--7.1------")

    if i == 10:
        text_box.insert(tk.END,
                        "A 大调,10,400\n5-351'--76-1'-5---5-123-212----5-351'--76-1'-5---5-234--7.1----6-1'-1'---7-671'---671'665312----5-351'--76-1'-5---5-234--7.1------")

    if i == 15:
        text_box.insert(tk.END,
                        "C 大调,0,600\n5-351'--76-1'-5---5-123-212----5-351'--76-1'-5---5-234--7.1----6-1'-1'---7-671'---671'665312----5-351'--76-1'-5---5-234--7.1------")


# 创建文本框的右键菜单
def show_textbox_menu(event):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="剪切", command=lambda: event.widget.event_generate("<<Cut>>"))
    menu.add_command(label="复制", command=lambda: event.widget.event_generate("<<Copy>>"))
    menu.add_command(label="粘贴", command=lambda: event.widget.event_generate("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="全选", command=lambda: event.widget.event_generate("<<SelectAll>>"))
    menu.add_command(
        label="全选复制",
        command=lambda: (
            event.widget.tag_add("sel", "1.0", "end"),
            event.widget.event_generate("<<Copy>>")
        )
    )
    menu.add_separator()
    menu.add_command(
        label="全选删除",
        command=lambda: event.widget.delete("1.0", "end")
    )
    menu.post(event.x_root, event.y_root)


for text_box in text_boxes:
    text_box.bind("<Button-3>", show_textbox_menu)

# 创建按钮
generate_button = tk.Button(root, text="随机谱曲音轨3", command=generate_random_notes)
generate_button.pack(pady=20)
generate_button.place(x=700, y=80, width=100, height=30)

generate_button = tk.Button(root, text="随机谱曲音轨4", command=generate_random_notes1)
generate_button.pack(pady=20)
generate_button.place(x=700, y=110, width=100, height=30)

generate_button = tk.Button(root, text="随机谱曲音轨5", command=generate_random_notes2)
generate_button.pack(pady=20)
generate_button.place(x=700, y=140, width=100, height=30)

clear_button = tk.Button(root, text="清空所有", command=clear_all_textboxes)
clear_button.pack(pady=20)
clear_button.place(x=550, y=210, width=100, height=50)

pause_button = tk.Button(root, text="暂停", command=pause_music)
pause_button.pack(pady=20)
pause_button.place(x=550, y=60, width=100, height=50)

stop_button = tk.Button(root, text="停止", command=stop_music)
stop_button.pack(pady=20)
stop_button.place(x=550, y=110, width=100, height=50)

export_button = tk.Button(root, text="导出", command=export_midi)
export_button.pack(pady=20)
export_button.place(x=550, y=160, width=100, height=50)

play_all_button = tk.Button(root, text="播放全部音轨", command=play_all_tracks_together)
play_all_button.pack(pady=20)
play_all_button.place(x=550, y=10, width=100, height=50)

loop_var = tk.BooleanVar()
loop_checkbox = tk.Checkbutton(root, text="循环播放", variable=loop_var, command=toggle_loop)
loop_checkbox.pack(pady=5)
loop_checkbox.place(x=700, y=10, width=100, height=30)

# 初始显示第一个文本框
display_textbox(0)


# def on_closing():
#     global midi_out
#     if midi_out:
#         midi_out.close()
#     pygame.midi.quit()
#     root.destroy()
def on_closing():
    global is_playing, midi_out

    # 检查是否正在播放
    if is_playing:
        result = messagebox.askyesno("正在播放", "音乐正在播放中，是否停止播放并退出？")
        if not result:
            return  # 用户选择取消，不退出

        # 用户确认退出，先停止播放
        stop_music()
        time.sleep(0.2)  # 等待线程完全停止

    # 关闭MIDI设备
    if midi_out:
        try:
            midi_out.close()
        except:
            pass

    try:
        pygame.midi.quit()
    except:
        pass

    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()