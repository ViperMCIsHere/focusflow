"""
FocusFlow — robust fancy to-do (safe version)

- Normalizes stale/unknown task file formats (strings, missing keys, older schema)
- Uses a stable schema: id, title, category, priority, due, created_ts (float seconds)
- Sorts reliably and won't crash on missing fields
- Uses explicit card background colors so animations don't rely on internal widget attributes
- Compatible with customtkinter v5+
"""

import customtkinter as ctk
from datetime import datetime
import json
import os
import time
import random
from tkcalendar import Calendar
import tkinter as tk

# ---------------- CONFIG ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DATA_FILE = "tasks.json"
CATEGORIES = ["Work", "Personal", "Study", "Other"]
PRIORITIES = ["Low", "Medium", "High"]

# explicit card colors so we can safely animate without calling internal attributes
CARD_BG = {
    "dark": "#2b2b2b",   # card background in dark mode
    "light": "#f3f3f3"   # card background in light mode
}
FLASH_COLOR = "#2ecc71"  # green flash for newly added tasks


# ---------------- Helpers ----------------
def now_ts() -> float:
    return time.time()


def ensure_int_id(value=None) -> int:
    """Return a stable int id (ms)"""
    if isinstance(value, (int, float)):
        return int(value)
    return int(now_ts() * 1000) + random.randint(0, 999)


def parse_created_ts(raw) -> float:
    """
    Accept:
      - numeric (int/float) -> timestamp seconds
      - ISO datetime string -> parsed
      - other -> fallback to now
    """
    if raw is None:
        return now_ts()
    if isinstance(raw, (int, float)):
        # assume seconds (or ms if huge)
        if raw > 1e12:  # looks like ms
            return float(raw) / 1000.0
        return float(raw)
    if isinstance(raw, str):
        # try ISO first
        try:
            dt = datetime.fromisoformat(raw)
            return dt.timestamp()
        except Exception:
            # try numeric string
            try:
                num = float(raw)
                if num > 1e12:
                    return num / 1000.0
                return num
            except Exception:
                return now_ts()
    return now_ts()


def normalize_task(raw_item) -> dict:
    """Convert any raw entry (string/dict) into normalized schema."""
    # if it's a plain string, treat it as the title
    if isinstance(raw_item, str):
        return {
            "id": ensure_int_id(),
            "title": raw_item,
            "category": "Other",
            "priority": "Medium",
            "due": "",
            "created_ts": now_ts()
        }

    if not isinstance(raw_item, dict):
        # last resort: stringify
        return {
            "id": ensure_int_id(),
            "title": str(raw_item),
            "category": "Other",
            "priority": "Medium",
            "due": "",
            "created_ts": now_ts()
        }

    # now it's a dict: map old keys to new schema safely
    title = raw_item.get("title") or raw_item.get("text") or raw_item.get("name") or str(raw_item.get("task") or raw_item.get("t") or "Untitled")
    category = raw_item.get("category") or raw_item.get("cat") or "Other"
    priority = raw_item.get("priority") or raw_item.get("prio") or "Medium"
    due = raw_item.get("due") or raw_item.get("due_date") or raw_item.get("deadline") or ""
    created_raw = raw_item.get("created_ts") or raw_item.get("created") or raw_item.get("timestamp") or raw_item.get("time")
    created_ts = parse_created_ts(created_raw)
    id_val = ensure_int_id(raw_item.get("id") or raw_item.get("uid") or raw_item.get("identifier"))

    # final normalized dict
    return {
        "id": id_val,
        "title": str(title),
        "category": category if category in CATEGORIES else "Other",
        "priority": priority if priority in PRIORITIES else "Medium",
        "due": str(due),
        "created_ts": created_ts
    }


# ---------------- The App ----------------
class FancyTodoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FocusFlow — Fancy To-Do v1.0")
        self.geometry("720x760")
        self.minsize(640, 520)

        # tasks store (normalized)
        self.tasks = []
        self._load_tasks()

        # UI
        self._build_ui()

        # initial render
        self.render_tasks()

    # ------- storage -------
    def _load_tasks(self):
        """Load file, normalize every entry to our schema. If file missing/corrupted -> start empty."""
        if not os.path.exists(DATA_FILE):
            self.tasks = []
            return

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            # corrupted file -> backup and start empty
            try:
                os.replace(DATA_FILE, DATA_FILE + ".bak")
            except Exception:
                pass
            self.tasks = []
            return

        # raw should be a list; if it's a dict or other, convert safely
        if isinstance(raw, dict):
            # maybe older schema stored by id mapping: convert values
            items = list(raw.values())
        elif isinstance(raw, list):
            items = raw
        else:
            items = [raw]

        normalized = []
        seen_ids = set()
        for it in items:
            t = normalize_task(it)
            # ensure id uniqueness
            while t["id"] in seen_ids:
                t["id"] = ensure_int_id()
            seen_ids.add(t["id"])
            normalized.append(t)

        self.tasks = normalized

    def _save_tasks(self):
        """Save current tasks list (in our normalized schema)."""
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # fail silently but print to console for debugging
            print("Error saving tasks:", e)

    # ------- UI build -------
    def _build_ui(self):
        # Header
        header = ctk.CTkLabel(self, text="FocusFlow v1.0", font=("Segoe UI Semibold", 30))
        header.pack(pady=(18, 2))

        sub = ctk.CTkLabel(self, text="Clean · Smart · Focused", font=("Segoe UI", 13))
        sub.pack(pady=(0, 14))

        # Input container
        entry_container = ctk.CTkFrame(self)
        entry_container.pack(fill="x", padx=20, pady=(0, 16))

        # configure grid inside
        entry_container.grid_columnconfigure(0, weight=1)
        entry_container.grid_columnconfigure(1, weight=0)
        entry_container.grid_columnconfigure(2, weight=0)

        self.title_entry = ctk.CTkEntry(entry_container, placeholder_text="What needs to be done?", height=38)
        self.title_entry.grid(row=0, column=0, columnspan=3, padx=(12, 12), pady=(12, 8), sticky="ew")

        # Category and priority and due
        self.category_var = ctk.StringVar(value=CATEGORIES[0])
        self.priority_var = ctk.StringVar(value=PRIORITIES[1])

        self.category_menu = ctk.CTkOptionMenu(entry_container, values=CATEGORIES, variable=self.category_var)
        self.category_menu.grid(row=1, column=0, padx=(12, 8), pady=(6, 12), sticky="ew")

        self.priority_menu = ctk.CTkOptionMenu(entry_container, values=PRIORITIES, variable=self.priority_var)
        self.priority_menu.grid(row=1, column=1, padx=(8, 8), pady=(6, 12), sticky="ew")

        self.due_entry = ctk.CTkEntry(entry_container, placeholder_text="Due (YYYY-MM-DD)", height=34)
        self.due_entry.grid(row=1, column=2, padx=(8, 12), pady=(6, 12), sticky="ew")

        # Add button
        self.add_button = ctk.CTkButton(entry_container, text="+ Add Task", command=self.add_task)
        self.add_button.grid(row=2, column=0, columnspan=3, padx=(12, 12), pady=(0, 12), sticky="ew")

        # Task list area
        self.task_list_frame = ctk.CTkScrollableFrame(self, label_text="Your Tasks", width=600, height=420)
        self.task_list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        # bottom controls
        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", padx=20, pady=(0, 18))
        self.mode_switch = ctk.CTkSwitch(controls, text="Light / Dark", command=self.toggle_theme)
        self.mode_switch.pack(side="right")

        # ensure the card default is consistent with current theme
        self.card_bg_color = CARD_BG[ctk.get_appearance_mode().lower() or "dark"]

    # ------- actions -------
    def add_task(self):
        title = self.title_entry.get().strip()
        if not title:
            return

        category = self.category_var.get() if self.category_var.get() in CATEGORIES else "Other"
        priority = self.priority_var.get() if self.priority_var.get() in PRIORITIES else "Medium"
        due = self.due_entry.get().strip()

        task = {
            "id": ensure_int_id(),
            "title": title,
            "category": category,
            "priority": priority,
            "due": due,
            "created_ts": now_ts()
        }
        self.tasks.append(task)
        self._save_tasks()

        # clear UI inputs
        self.title_entry.delete(0, "end")
        self.due_entry.delete(0, "end")

        # re-render and flash newly added
        self.render_tasks(animated_id=task["id"])

    def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        self._save_tasks()
        self.render_tasks()

    # ------- rendering -------
    def render_tasks(self, animated_id=None):
        # clear children
        for w in self.task_list_frame.winfo_children():
            w.destroy()

        if not self.tasks:
            ctk.CTkLabel(self.task_list_frame, text="No tasks yet — add one!", font=("Segoe UI", 14)).pack(pady=18)
            return

        # sort descending by created_ts (fallback to 0)
        def ts_of(t):
            try:
                return float(t.get("created_ts", 0) or 0)
            except Exception:
                return 0.0

        tasks_sorted = sorted(self.tasks, key=ts_of, reverse=True)

        # use explicit card background so we can animate safely
        theme = ctk.get_appearance_mode().lower()
        card_bg = CARD_BG.get(theme, CARD_BG["dark"])

        for task in tasks_sorted:
            card = ctk.CTkFrame(self.task_list_frame, corner_radius=10, fg_color=card_bg)
            card.pack(fill="x", padx=12, pady=8)

            # title row
            title_text = task.get("title") or "Untitled"
            title_label = ctk.CTkLabel(card, text=title_text, font=("Segoe UI Semibold", 13), anchor="w")
            title_label.pack(fill="x", padx=12, pady=(10, 2))

            # meta row (category, priority, due)
            cat = task.get("category") or "Other"
            prio = task.get("priority") or "Medium"
            due = task.get("due") or ""
            created_ts = task.get("created_ts") or now_ts()
            created_str = datetime.fromtimestamp(parse_created_ts(created_ts)).strftime("%Y-%m-%d %H:%M")

            meta_text = f"Category: {cat}  •  Priority: {prio}"
            if due:
                meta_text += f"  •  Due: {due}"
            meta_text += f"  •  Added: {created_str}"

            meta_label = ctk.CTkLabel(card, text=meta_text, font=("Segoe UI", 11), anchor="w")
            meta_label.pack(fill="x", padx=12, pady=(0, 10))

            # bottom row with delete
            bottom = ctk.CTkFrame(card)
            bottom.pack(fill="x", padx=8, pady=(0, 10))
            del_btn = ctk.CTkButton(bottom, text="✕ Delete", width=96, fg_color="#c0392b",
                                    hover_color="#e74c3c", command=lambda tid=task.get("id"): self.delete_task(tid))
            del_btn.pack(side="right", padx=8)

            # animate if needed: flash background to green then back
            if animated_id is not None and task.get("id") == animated_id:
                # set flash, then restore to card_bg
                try:
                    card.configure(fg_color=FLASH_COLOR)
                    self.after(300, lambda c=card, bg=card_bg: c.configure(fg_color=bg))
                except Exception:
                    # fallback: ignore animation if framework doesn't allow changing color
                    pass

    # ------- theme toggle -------
    def toggle_theme(self):
        curr = ctk.get_appearance_mode().lower()
        new = "light" if curr == "dark" else "dark"
        ctk.set_appearance_mode(new)
        # update stored card color and rerender
        self.card_bg_color = CARD_BG.get(new, CARD_BG["dark"])
        self.render_tasks()
    # ------------- calendar --------------
    def open_calendar(self):
        """Open calendar window with due task highlights."""
        TaskCalendar(self, self.tasks)


# ---------------- run ----------------
if __name__ == "__main__":
    app = FancyTodoApp()
    app.mainloop()
# -------------- ADDON: TASK CALENDAR VIEW --------------
# Paste this *below* the main app code in fancy_todo_safe.py



class TaskCalendar(ctk.CTkToplevel):
    """A popup monthly calendar that highlights task due dates."""

    def __init__(self, master, tasks):
        super().__init__(master)
        self.title("📅 FocusFlow Calendar")
        self.geometry("460x420")
        self.resizable(False, False)
        self.tasks = tasks

        # convert root dark/light mode to Calendar compatible background
        theme = ctk.get_appearance_mode().lower()
        bg = "#1e1e1e" if theme == "dark" else "#ffffff"
        fg = "#ffffff" if theme == "dark" else "#000000"

        self.cal = Calendar(
            self,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            background=bg,
            foreground=fg,
            headersbackground=bg,
            headersforeground=fg,
            normalbackground=bg,
            normalforeground=fg,
            weekendbackground=bg,
            weekendforeground=fg,
            selectbackground="#0078D7",
            selectforeground="#ffffff",
        )
        self.cal.pack(padx=20, pady=20, fill="both", expand=True)

        self.info_label = ctk.CTkLabel(self, text="Hover a date to see tasks", font=("Segoe UI", 12))
        self.info_label.pack(pady=(0, 12))

        self.tooltip = tk.StringVar()
        self.tooltip_label = ctk.CTkLabel(self, textvariable=self.tooltip, font=("Segoe UI", 11), wraplength=400)
        self.tooltip_label.pack(pady=(0, 10))

        # highlight due dates with small marks
        self._mark_due_dates()

        # bind mouse hover
        self.cal.bind("<<CalendarSelected>>", self._on_date_select)

    def _mark_due_dates(self):
        """Mark calendar cells with dots for due tasks."""
        for task in self.tasks:
            due = task.get("due")
            if not due:
                continue
            try:
                # verify format YYYY-MM-DD
                datetime.strptime(due, "%Y-%m-%d")
            except Exception:
                continue

            # add a small colored mark (use calendar event)
            prio = task.get("priority", "Medium")
            color = "#2ecc71" if prio == "Low" else "#f39c12" if prio == "Medium" else "#e74c3c"
            self.cal.calevent_create(datetime.strptime(due, "%Y-%m-%d"), task.get("title", ""), tags=prio)
            self.cal.tag_config(prio, background=color)

    def _on_date_select(self, event):
        """Show tasks for the selected date."""
        date = self.cal.get_date()
        tasks_due = [t for t in self.tasks if t.get("due") == date]

        if not tasks_due:
            self.tooltip.set(f"No tasks due on {date}.")
            return

        lines = [f"📅 Tasks due on {date}:"]
        for t in tasks_due:
            lines.append(f" • {t.get('title', 'Untitled')}  ({t.get('priority', 'Medium')})")
        self.tooltip.set("\n".join(lines))


# -------------- INTEGRATION BUTTON --------------
# Add this helper function to FancyTodoApp class (paste inside class, e.g. after toggle_theme):



# Then add this button inside the UI after your dark/light switch:
# (place it in the _build_ui method, near self.mode_switch)
# Example:
#     self.calendar_button = ctk.CTkButton(controls, text="📅 Calendar", command=self.open_calendar)
#     self.calendar_button.pack(side="left", padx=8)

# That’s all! 🎉
