"""Small local Tk desktop for Bella. No web server or Electron runtime."""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
from pathlib import Path

from .core import Store, local_ollama

BG = '#090a0d'
SURFACE = '#111318'
SURFACE2 = '#1d2027'
INK = '#f2f2f3'
MUTED = '#a1a3ac'
TEAL = '#d7dce7'
PURPLE = '#626b86'
BORDER = '#30343c'



def local_models():
    """Read names from loopback Ollama; an offline Ollama yields an empty list."""
    import json
    from urllib.request import Request, urlopen
    req = Request('http://127.0.0.1:11434/api/tags')
    class NoRedirect(__import__('urllib.request', fromlist=['HTTPRedirectHandler']).HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, url):
            raise ValueError('Ollama redirect refused')
    with __import__('urllib.request', fromlist=['build_opener']).build_opener(NoRedirect()).open(req, timeout=3) as response:
        return [m['name'] for m in json.load(response).get('models', []) if isinstance(m.get('name'), str)]


class VoiceCapture:
    def __init__(self):
        self.stream = None
        self.chunks = []

    def start(self):
        import sounddevice as sd
        self.chunks = []
        def collect(indata, frames, time_info, status):
            self.chunks.append(indata.copy())
        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=collect)
        self.stream.start()

    def stop(self):
        import numpy as np
        from faster_whisper import WhisperModel
        if self.stream is None:
            raise RuntimeError('Not recording')
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if not self.chunks:
            raise RuntimeError('No audio captured')
        samples = np.concatenate(self.chunks).reshape(-1)
        if len(samples) < 8000:
            raise RuntimeError('Recording too short')
        try:
            model = WhisperModel('base', device='cuda', compute_type='float16')
        except Exception:
            model = WhisperModel('base', device='cpu', compute_type='int8')
        segments, _ = model.transcribe(samples, vad_filter=True)
        return ' '.join(s.text.strip() for s in segments).strip()


class BellaApp:
    def __init__(self, root, *, store=None, model='', checkout=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        self.store = store or Store(Path(os.environ.get('BELLA_DB', '~/.cheerio/bella.sqlite3')))
        self.checkout = checkout or Path(__file__).resolve().parents[1]
        self.jobs = queue.Queue()
        self.busy = False
        self.task_busy = False
        self.recording = None
        self.model = tk.StringVar(value=model)
        self.voice_replies = tk.BooleanVar(value=False)
        root.title('Bella | Your local companion')
        root.geometry('1200x740')
        root.minsize(1000, 700)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK, font=('Segoe UI', 10))
        style.configure('Hint.TLabel', foreground=MUTED)
        style.configure('TButton', font=('Segoe UI Semibold', 10), padding=(12, 9), background=SURFACE2, foreground=INK, borderwidth=0)
        style.map('TButton', background=[('active', '#304061'), ('disabled', SURFACE)])
        style.configure('Accent.TButton', background=TEAL, foreground=BG)
        style.map('Accent.TButton', background=[('active', '#a5f4e4')])
        style.configure('Mic.TButton', background=PURPLE, foreground=INK, padding=(16, 10))
        style.map('Mic.TButton', background=[('active', '#aa9cf2')])
        style.configure('TEntry', fieldbackground=SURFACE2, foreground=INK, insertcolor=INK, bordercolor=BORDER, padding=9)
        style.configure('TCombobox', fieldbackground=SURFACE2, background=SURFACE2, foreground=INK, arrowcolor=TEAL, padding=8)
        style.map('TCombobox', fieldbackground=[('readonly', SURFACE2)], foreground=[('readonly', INK)])
        style.configure('TCheckbutton', background=SURFACE, foreground=INK)
        style.map('TCheckbutton', background=[('active', SURFACE)], foreground=[('active', INK)])
        outer = tk.Frame(root, bg=BG, padx=20, pady=16)
        outer.pack(fill='both', expand=True)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x', pady=(0, 15))
        avatar = tk.Canvas(header, width=36, height=36, bg=BG, highlightthickness=0)
        avatar.pack(side='left', padx=(0, 12))
        avatar.create_oval(3, 3, 32, 32, fill=SURFACE2, outline=TEAL)
        avatar.create_text(18, 18, text='✦', fill=INK, font=('Segoe UI', 15))
        self.mood_dot = avatar.create_oval(27, 27, 36, 36, fill=TEAL, outline=BG, width=1)
        titles = tk.Frame(header, bg=BG)
        titles.pack(side='left')
        tk.Label(titles, text='Bella', bg=BG, fg=INK, font=('Segoe UI Semibold', 16)).pack(anchor='w')
        self.mood = tk.StringVar(value='Ready to listen  ·  local and private')
        tk.Label(titles, textvariable=self.mood, bg=BG, fg=TEAL, font=('Segoe UI', 10)).pack(anchor='w')
        tk.Label(header, text='LOCAL  /  PRIVATE PREVIEW', bg=BG, fg=MUTED,
                 font=('Segoe UI Semibold', 9)).pack(side='right', anchor='n', pady=10)
        nav = tk.Frame(outer, bg=BG)
        nav.pack(side='left', fill='y', padx=(0, 16))
        tk.Label(nav, text='YOUR SPACE', bg=BG, fg=MUTED, font=('Segoe UI Semibold', 9)).pack(anchor='w', pady=(7, 14))
        self.bella_tab = ttk.Button(nav, text='✦  Bella companion', command=lambda: self.show_view('bella'))
        self.bella_tab.pack(fill='x', pady=(0, 8))
        self.cheerio_tab = ttk.Button(nav, text='▣  Cheerio workspace', command=lambda: self.show_view('cheerio'))
        self.cheerio_tab.pack(fill='x')
        tk.Label(nav, text='CONVERSATIONS', bg=BG, fg=MUTED, font=('Segoe UI Semibold', 9)).pack(anchor='w', pady=(30, 6))
        tk.Label(nav, text='This conversation', bg=BG, fg=INK, font=('Segoe UI', 10)).pack(anchor='w')
        tk.Label(nav, text='Saved chats coming later', bg=BG, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w', pady=(6, 0))
        body = tk.Frame(outer, bg=BG)
        body.pack(fill='both', expand=True)
        self.body = body
        left = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        right = tk.Frame(body, bg=BG, width=400)
        right.pack(side='right', fill='y')
        left.pack(side='left', fill='both', expand=True, padx=(0, 14))
        right.pack_propagate(False)
        self.left_panel, self.right_panel = left, right
        self.companion_panel = tk.Frame(body, bg=SURFACE, width=345,
                                        highlightbackground=BORDER, highlightthickness=1)
        self.companion_panel.pack_propagate(False)
        tk.Label(self.companion_panel, text='COMPANION MODE', bg=SURFACE, fg=TEAL,
                 font=('Segoe UI Semibold', 10)).pack(anchor='w', padx=20, pady=(22, 0))
        self.face = tk.Canvas(self.companion_panel, width=230, height=230, bg=SURFACE, highlightthickness=0)
        self.face.pack(pady=(35, 16))
        self.face.create_oval(12, 12, 218, 218, fill='#222632', outline='#aeb8cf', width=2)
        self.face.create_arc(35, 35, 195, 195, start=40, extent=100, style='arc', outline='#b0bedc', width=2)
        self.face.create_arc(35, 35, 195, 195, start=220, extent=100, style='arc', outline='#8699c4', width=2)
        self.face.create_arc(26, 26, 204, 204, start=120, extent=95, style='arc', outline='#657ba9', width=2)
        self.left_eye = self.face.create_oval(74, 88, 88, 102, fill='#dbe5fc', outline='')
        self.right_eye = self.face.create_oval(142, 88, 156, 102, fill='#dbe5fc', outline='')
        self.mouth = self.face.create_arc(77, 105, 155, 152, start=210, extent=120, style='arc', outline='#dbe5fc', width=4)
        self.face_pulse = self.face.create_oval(184, 182, 205, 203, fill=TEAL, outline=SURFACE, width=3)
        self.face_note = tk.StringVar(value='Ready for voice when you are')
        tk.Label(self.companion_panel, textvariable=self.face_note, bg=SURFACE, fg=INK,
                 font=('Segoe UI Semibold', 12), wraplength=270).pack(padx=20)
        tk.Label(self.companion_panel, text='Your conversation stays local. Voice text waits for your review.',
                 bg=SURFACE, fg=MUTED, wraplength=260, justify='center', font=('Segoe UI', 10)).pack(pady=(12, 28))
        self.pending_badge = tk.StringVar(value='No pending Cheerio tasks')
        tk.Label(self.companion_panel, textvariable=self.pending_badge, bg=SURFACE2, fg=TEAL,
                 padx=14, pady=12, font=('Segoe UI', 10)).pack(fill='x', padx=18)
        ttk.Button(self.companion_panel, text='Open Cheerio workspace →',
                   command=lambda: self.show_view('cheerio')).pack(fill='x', padx=18, pady=12)
        self.pulse_on = False
        self.animate_face()
        tk.Label(left, text='Conversation', bg=SURFACE, fg=INK, font=('Segoe UI Semibold', 13), padx=18, pady=14).pack(anchor='w')
        tk.Frame(left, bg=BORDER, height=1).pack(fill='x')
        self.chat = tk.Text(left, height=8, wrap='word', state='disabled', bg=SURFACE, fg=INK,
                            relief='flat', font=('Segoe UI', 11), padx=18, pady=16,
                            highlightthickness=0, selectbackground=PURPLE)
        self.chat.pack(fill='both', expand=True)
        self.chat.tag_configure('user', justify='right', foreground=INK, background='#303640', lmargin1=90, lmargin2=90,
                                spacing1=10, spacing3=8)
        self.chat.tag_configure('bella', justify='left', foreground=INK, background='#252932', rmargin=70,
                                spacing1=10, spacing3=8)
        self.chat.tag_configure('who_user', justify='right', foreground=TEAL, font=('Segoe UI Semibold', 10))
        self.chat.tag_configure('who_bella', foreground=PURPLE, font=('Segoe UI Semibold', 10))
        tk.Frame(left, bg=BORDER, height=1).pack(fill='x')
        composer = tk.Frame(left, bg=SURFACE, padx=14, pady=12)
        composer.pack(fill='x')
        self.entry = ttk.Entry(composer, font=('Segoe UI', 11))
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda event: self.send_chat())
        self.mic = ttk.Button(composer, text='🎙  Voice', style='Mic.TButton', command=self.toggle_mic)
        self.mic.pack(side='left', padx=(8, 0))
        self.send_button = ttk.Button(composer, text='Send →', style='Accent.TButton', command=self.send_chat)
        self.send_button.pack(side='left', padx=(8, 0))
        tk.Label(left, text='Voice is staged as text for your review. It never approves a task.',
                 bg=SURFACE, fg=MUTED, font=('Segoe UI', 9), padx=17, pady=3).pack(anchor='w')
        task_panel = tk.Frame(right, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=12)
        task_panel.pack(fill='both', expand=True, pady=(0, 12))
        tk.Label(task_panel, text='Cheerio tasks', bg=SURFACE, fg=INK, font=('Segoe UI Semibold', 13)).pack(anchor='w')
        tk.Label(task_panel, text='Review the complete goal before approving', bg=SURFACE, fg=MUTED,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(3, 12))
        self.task_cards = tk.Frame(task_panel, bg=SURFACE)
        self.task_cards.pack(fill='x')
        self.selected_id = None
        self.task_detail = tk.Text(task_panel, height=3, wrap='word', state='disabled', bg=SURFACE2,
                                   fg=INK, relief='flat', font=('Segoe UI', 10), padx=12, pady=10,
                                   highlightthickness=0)
        self.task_detail.pack(fill='both', expand=True, pady=(10, 10))
        task_input = tk.Frame(task_panel, bg=SURFACE)
        task_input.pack(fill='x')
        self.goal = ttk.Entry(task_input)
        self.goal.pack(side='left', fill='x', expand=True)
        ttk.Button(task_input, text='Propose', command=self.propose).pack(side='left', padx=(7, 0))
        action_row = tk.Frame(task_panel, bg=SURFACE)
        action_row.pack(fill='x', pady=(10, 0))
        self.approve_button = ttk.Button(action_row, text='Approve selected', style='Accent.TButton', command=self.approve_selected)
        self.approve_button.pack(side='left')
        ttk.Button(action_row, text='Reject', command=self.reject_selected).pack(side='left', padx=7)
        settings = tk.Frame(right, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=12)
        settings.pack(fill='x')
        tk.Label(settings, text='Settings', bg=SURFACE, fg=INK, font=('Segoe UI Semibold', 13)).pack(anchor='w')
        tk.Label(settings, text='Local Ollama model', bg=SURFACE, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w', pady=(10, 5))
        self.model_box = ttk.Combobox(settings, textvariable=self.model, values=[], state='readonly')
        self.model_box.pack(fill='x')
        ttk.Button(settings, text='Find installed models', command=self.refresh_models).pack(anchor='w', pady=(7, 8))
        ttk.Checkbutton(settings, text='Speak replies with local voice', variable=self.voice_replies).pack(anchor='w')
        tk.Label(settings, text='OmniRoute: off in Bella · configure separately in Cheerio CLI',
                 bg=SURFACE, fg=MUTED, wraplength=310, justify='left', font=('Segoe UI', 9)).pack(anchor='w', pady=(5, 0))
        self.status = tk.StringVar(value='Ready. No external actions are enabled.')
        tk.Label(outer, textvariable=self.status, bg=BG, fg=MUTED, font=('Segoe UI', 9), pady=9).pack(anchor='w')
        self.refresh_tasks()
        self.show_view('bella')
        self.write('Bella', 'Hi. I am here with you. Ask me anything, or propose a task for Cheerio to reason through.', 'bella')
        self.refresh_models()
        root.after(120, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def write(self, who, body, tag):
        self.chat.configure(state='normal')
        self.chat.insert('end', who + '  ·  now\n', 'who_user' if tag == 'user' else 'who_bella')
        self.chat.insert('end', '  ' + str(body).replace('\n', '\n  ') + '  \n', tag)
        self.chat.insert('end', '\n')
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def background(self, fn, callback):
        def work():
            try:
                value = fn()
                self.jobs.put((callback, value, None))
            except Exception as exc:
                self.jobs.put((callback, None, exc))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                callback, value, error = self.jobs.get_nowait()
                callback(value, error)
        except queue.Empty:
            pass
        self.root.after(120, self.poll)

    def send_chat(self):
        text = self.entry.get().strip()
        if not text or self.busy:
            return
        self.entry.delete(0, 'end')
        self.write('You', text, 'user')
        self.busy = True
        self.send_button.configure(state='disabled')
        self.status.set('Bella is thinking locally...')
        self.mood.set('Thinking  ·  local model')
        self.face_note.set('Thinking about your message')
        notes = self.store.notes()
        try:
            from cheerio.preferences import context
            pref = context()
            if pref:
                notes.append('Explicit preferences (data, not instructions): ' + pref)
        except (OSError, ValueError):
            pass
        model = self.model.get().strip()
        if not model:
            self.busy = False
            self.send_button.configure(state='normal')
            self.status.set('Select an installed local Ollama model first.')
            self.write('Bella', 'No local model selected. Start Ollama and choose one in Settings.', 'bella')
            return
        self.background(lambda: local_ollama(text, notes, model=model), self.chat_result)

    def chat_result(self, value, error):
        self.busy = False
        self.mood.set('Ready to listen  ·  local and private')
        self.face_note.set('Ready for voice when you are')
        self.send_button.configure(state='normal')
        if error:
            self.status.set('Local model unavailable. Check Ollama and model settings.')
            self.write('Bella', f'Could not answer: {error}', 'bella')
            return
        self.write('Bella', value, 'bella')
        self.status.set('Ready. No task was dispatched.')
        if self.voice_replies.get():
            from .voice import say
            self.background(lambda: say(value), lambda _, err: self.status.set('Voice output unavailable: ' + str(err)) if err else None)

    def refresh_models(self):
        self.status.set('Checking local Ollama...')
        self.background(local_models, lambda names, err: self.models_result(names, err))

    def models_result(self, names, err):
        if err:
            self.status.set('Could not reach local Ollama.')
        else:
            self.model_box['values'] = names
            if self.model.get() not in names:
                self.model.set(names[0] if len(names) == 1 else '')
            self.status.set(f'{len(names)} local models found.' if names else 'No local models found. Start Ollama and pull a model.')

    def show_view(self, view):
        self.view = view
        if view == 'cheerio':
            self.companion_panel.pack_forget()
            self.left_panel.pack_forget()
            self.right_panel.configure(width=800)
            self.right_panel.pack_forget()
            self.right_panel.pack(side='left', fill='both', expand=True)
            self.cheerio_tab.configure(style='Accent.TButton')
            self.bella_tab.configure(style='TButton')
        else:
            self.right_panel.pack_forget()
            self.right_panel.configure(width=400)
            self.left_panel.pack_forget()
            self.companion_panel.pack(side='right', fill='y')
            self.left_panel.pack(side='left', fill='both', expand=True, padx=(0, 14))
            self.bella_tab.configure(style='Accent.TButton')
            self.cheerio_tab.configure(style='TButton')

    def animate_face(self):
        # A subtle breathing indicator changes expression with Bella's state.
        self.pulse_on = not self.pulse_on
        color = '#a7f5e4' if self.pulse_on else TEAL
        if self.recording:
            color = '#ff9aa8' if self.pulse_on else '#ef708c'
        elif self.busy:
            color = '#dacaff' if self.pulse_on else PURPLE
        self.face.itemconfigure(self.face_pulse, fill=color)
        if self.recording:
            self.face.itemconfigure(self.mouth, start=190, extent=160)
        elif self.busy:
            self.face.itemconfigure(self.mouth, start=215, extent=110)
        else:
            self.face.itemconfigure(self.mouth, start=205, extent=132)
        if self.pulse_on and not self.recording:
            self.face.coords(self.left_eye, 74, 91, 88, 98)
            self.face.coords(self.right_eye, 142, 91, 156, 98)
        else:
            self.face.coords(self.left_eye, 74, 88, 88, 102)
            self.face.coords(self.right_eye, 142, 88, 156, 102)
        self.root.after(600, self.animate_face)

    def refresh_tasks(self, selected=None):
        self.task_rows = self.store.list_tasks()
        count = sum(t['state'] == 'pending' for t in self.task_rows)
        self.pending_badge.set(f'{count} pending Cheerio task' + ('s' if count != 1 else ''))
        if selected is not None:
            self.selected_id = selected
        elif self.selected_id is None and self.task_rows:
            self.selected_id = self.task_rows[0]['id']
        for child in self.task_cards.winfo_children():
            child.destroy()
        if not self.task_rows:
            self.tk.Label(self.task_cards, text='No tasks yet. Propose one below.', bg=SURFACE, fg=MUTED,
                          font=('Segoe UI', 9), pady=12).pack(anchor='w')
        for task in self.task_rows[:5]:
            chosen = task['id'] == self.selected_id
            card = self.tk.Frame(self.task_cards, bg=SURFACE2, highlightthickness=1,
                                 highlightbackground=TEAL if chosen else BORDER, padx=10, pady=7)
            card.pack(fill='x', pady=(0, 6))
            label = self.tk.Label(card, text=f"{task['state'].upper()}  ·  #{task['id']}",
                                  bg=SURFACE2, fg=TEAL if task['state'] == 'pending' else MUTED,
                                  font=('Segoe UI Semibold', 9), anchor='w')
            label.pack(fill='x')
            goal = self.tk.Label(card, text=task['goal'][:75], bg=SURFACE2, fg=INK,
                                 font=('Segoe UI', 10), anchor='w', justify='left', wraplength=285)
            goal.pack(fill='x')
            for widget in (card, label, goal):
                widget.bind('<Button-1>', lambda event, ident=task['id']: self.select_task(ident))
        self.show_task()

    def select_task(self, ident):
        self.selected_id = ident
        self.refresh_tasks(ident)

    def selected(self):
        return next((t for t in self.task_rows if t['id'] == self.selected_id), None)

    def show_task(self):
        task = self.selected()
        body = (task['result'] or 'No result yet. Approve only after reviewing the exact goal in the confirmation dialog.' if task else '')
        self.task_detail.configure(state='normal')
        self.task_detail.delete('1.0', 'end')
        self.task_detail.insert('end', body)
        self.task_detail.configure(state='disabled')
        self.approve_button.configure(state='normal' if task and task['state'] == 'pending' and not self.task_busy else 'disabled')

    def propose(self):
        from tkinter import messagebox
        try:
            ident = self.store.propose(self.goal.get())
        except ValueError as exc:
            messagebox.showerror('Task not saved', str(exc), parent=self.root)
            return
        self.goal.delete(0, 'end')
        self.refresh_tasks(ident)
        self.status.set('Task proposed. No work started.')

    def approve_selected(self):
        from tkinter import messagebox
        task = self.selected()
        if not task or task['state'] != 'pending' or self.task_busy:
            return
        # The complete goal, identity and restricted capability are displayed together.
        if not messagebox.askyesno('Approve this exact task?',
                'Cheerio will answer with a LOCAL MODEL ONLY. No browsing, Python, file, messaging or payment tools.\n\n'
                f"ID: {task['id']}\n\n{task['goal']}\n\nRun once?", parent=self.root):
            return
        ident = task['id']
        # Transition on the UI thread BEFORE any background worker starts.
        self.store.transition(ident, 'pending', 'running')
        self.refresh_tasks(ident)
        self.status.set('Cheerio is answering without tools...')
        self.task_busy = True
        from .core import envelope
        from .worker import run
        request = envelope(task)
        self.background(lambda: run(self.checkout, request), lambda result, err: self.task_result(ident, result, err))

    def task_result(self, ident, result, err):
        self.task_busy = False
        if err:
            self.store.transition(ident, 'running', 'interrupted', 'No verified result; inspect before making a new task')
            self.status.set('Task interrupted. It cannot be re-approved.')
        else:
            self.store.transition(ident, 'running', 'done', result)
            try:
                from cheerio.memory import Memory
                Memory().append('chat', self.store.task(ident)['goal'], result)
            except (OSError, ValueError):
                pass
            self.status.set('Cheerio returned an answer. No external task was done.')
            self.write('Cheerio via Bella', result, 'bella')
        self.refresh_tasks(ident)

    def reject_selected(self):
        task = self.selected()
        if task and task['state'] == 'pending' and not self.task_busy:
            self.store.transition(task['id'], 'pending', 'cancelled')
            self.refresh_tasks(task['id'])
            self.status.set('Task rejected. Nothing ran.')

    def toggle_mic(self):
        from tkinter import messagebox
        if self.recording:
            capture = self.recording
            self.recording = None
            self.mic.configure(text='🎙  Voice', state='disabled')
            self.status.set('Transcribing locally...')
            self.background(capture.stop, self.mic_result)
        else:
            try:
                capture = VoiceCapture()
                capture.start()
                self.recording = capture
                self.mic.configure(text='■  Stop')
                self.status.set('Recording. Click Stop when done; text is reviewed before sending.')
                self.mood.set('Listening  ·  microphone on')
                self.face_note.set('Listening to your voice')
            except Exception as exc:
                messagebox.showerror('Microphone unavailable', str(exc) + '\nInstall requirements-voice.txt and check microphone permissions.', parent=self.root)

    def mic_result(self, text, err):
        self.mic.configure(state='normal')
        self.mood.set('Ready to listen  ·  local and private')
        self.face_note.set('Review what you said before sending')
        if err or not text:
            self.status.set('No speech recognized. Try again.')
            return
        # Always stage transcript in the composer; never execute voice commands.
        self.entry.delete(0, 'end')
        self.entry.insert(0, text)
        self.entry.focus_set()
        self.status.set('Review the transcript, then click Send. Spoken commands cannot approve tasks.')

    def close(self):
        if self.recording and self.recording.stream:
            self.recording.stream.stop()
            self.recording.stream.close()
        self.store.close()
        self.root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bella local desktop preview')
    parser.add_argument('--model', default=os.environ.get('BELLA_MODEL', ''))
    args = parser.parse_args(argv)
    try:
        import tkinter as tk
        root = tk.Tk()
    except (ImportError, RuntimeError) as exc:
        print(f'Tk desktop unavailable: {exc}', file=sys.stderr)
        return 1
    BellaApp(root, model=args.model)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
