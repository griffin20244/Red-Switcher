import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageOps

OUTPUT_FORMATS = ("PNG", "JPG", "BMP", "ICO", "TGA")
INPUT_PATTERN = "*.png *.jpg *.jpeg *.bmp *.ico *.tga"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICO_MAX = 256
WINDOW_WIDTH = 420

BG = "#181818"
PANEL = "#222222"
BUTTON = "#333333"
BUTTON_HOVER = "#444444"
ACCENT = "#D94343"
ACCENT_DARK = "#B83232"
TEXT = "#EEEEEE"
MUTED = "#999999"
SUCCESS = "#78C091"

FONT = "Segoe UI"

APP_DIR = Path(__file__).resolve().parent

# Window title-bar icon
WINDOW_ICON_PATH = APP_DIR / "icon2.ico"

# The executable icon is set through PyInstaller's --icon option.
EXE_ICON_PATH = APP_DIR / "icon.ico"


def enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Conversion logic
# --------------------------------------------------------------------------

def has_alpha(image):
    return (
        image.mode in ("RGBA", "LA", "PA")
        or "transparency" in image.info
    )


def flatten_on_white(image):
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def pad_to_square(image):
    side = max(image.size)

    if image.size == (side, side):
        return image

    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(
        image,
        ((side - image.width) // 2, (side - image.height) // 2),
    )
    return canvas


def unique_path(directory, stem, extension):
    path = directory / f"{stem}_converted.{extension}"
    counter = 1

    while path.exists():
        path = directory / f"{stem}_converted_{counter}.{extension}"
        counter += 1

    return path


def save_ico(image, path, multi_size, size):
    base = pad_to_square(image.convert("RGBA"))

    if base.width > ICO_MAX:
        base = base.resize(
            (ICO_MAX, ICO_MAX),
            Image.Resampling.LANCZOS,
        )

    if multi_size:
        sizes = [s for s in ICO_SIZES if s <= base.width]

        if base.width not in sizes:
            sizes.append(base.width)
    else:
        base = base.resize(
            (size, size),
            Image.Resampling.LANCZOS,
        )
        sizes = [base.width]

    base.save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )


def convert_image(source, fmt, output_dir, ico_multi, ico_size):
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original)
        image.load()

    output_dir.mkdir(parents=True, exist_ok=True)

    extension = "jpg" if fmt == "JPG" else fmt.lower()
    path = unique_path(output_dir, source.stem, extension)

    if fmt == "JPG":
        rgb = (
            flatten_on_white(image)
            if has_alpha(image)
            else image.convert("RGB")
        )
        rgb.save(
            path,
            format="JPEG",
            quality=95,
            subsampling=0,
        )

    elif fmt == "PNG":
        if image.mode not in (
            "1", "L", "LA", "P", "RGB", "RGBA", "I;16"
        ):
            image = image.convert(
                "RGBA" if has_alpha(image) else "RGB"
            )

        image.save(path, format="PNG")

    elif fmt == "BMP":
        image = image.convert(
            "RGBA" if has_alpha(image) else "RGB"
        )
        image.save(path, format="BMP")

    elif fmt == "TGA":
        image = image.convert(
            "RGBA" if has_alpha(image) else "RGB"
        )
        image.save(
            path,
            format="TGA",
            compression="tga_rle",
        )

    elif fmt == "ICO":
        save_ico(image, path, ico_multi, ico_size)

    else:
        raise ValueError(f"Unsupported format: {fmt}")

    return path


# --------------------------------------------------------------------------
# User interface
# --------------------------------------------------------------------------

class RedSwitcher(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Red Switcher")
        self.configure(bg=BG)
        self.resizable(False, False)

        # Set the window icon from icon2.ico.
        if WINDOW_ICON_PATH.is_file():
            try:
                self.iconbitmap(default=str(WINDOW_ICON_PATH))
            except tk.TclError:
                try:
                    self.iconbitmap(str(WINDOW_ICON_PATH))
                except tk.TclError:
                    pass

        self.source = None
        self.output_folder = None
        self.results = queue.Queue()

        self.output_format = tk.StringVar(value="PNG")
        self.ico_multi = tk.BooleanVar(value=True)
        self.ico_size = tk.StringVar(value="256")

        self._build_ui()

        self.output_format.trace_add(
            "write", self._on_format_change
        )
        self.ico_multi.trace_add(
            "write", self._on_multi_change
        )

        self._fit_window(center=True)

    # ---- Building blocks -------------------------------------------------

    def _section_title(self, parent, text):
        tk.Label(
            parent,
            text=text,
            font=(FONT, 9, "bold"),
            fg=TEXT,
            bg=BG,
        ).pack(anchor="w")

    def _button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BUTTON,
            fg=TEXT,
            activebackground=BUTTON_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            font=(FONT, 8),
            cursor="hand2",
            padx=10,
            pady=4,
        )

    def _path_row(self, parent, placeholder, button_text, command):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=(3, 8))

        label = tk.Label(
            row,
            text=placeholder,
            font=(FONT, 8),
            fg=MUTED,
            bg=PANEL,
            anchor="w",
            padx=8,
            pady=5,
        )
        label.pack(side="left", fill="x", expand=True)

        self._button(
            row, button_text, command
        ).pack(side="right", padx=(6, 0))

        return label

    def _build_logo(self, parent):
        canvas = tk.Canvas(
            parent,
            width=32,
            height=32,
            bg=BG,
            highlightthickness=0,
        )

        canvas.create_arc(
            4, 4, 28, 28,
            start=35,
            extent=285,
            style="arc",
            outline=ACCENT,
            width=3,
        )

        canvas.create_line(
            21, 3, 28, 5, 24, 11,
            fill=ACCENT,
            width=2,
        )

        canvas.create_line(
            11, 29, 4, 27, 8, 21,
            fill=ACCENT,
            width=2,
        )

        return canvas

    def _build_ui(self):
        main = tk.Frame(
            self,
            bg=BG,
            padx=16,
            pady=12,
        )
        main.pack(fill="both", expand=True)

        header = tk.Frame(main, bg=BG)
        header.pack(anchor="w", fill="x")

        self._build_logo(header).pack(
            side="left",
            padx=(0, 8),
        )

        tk.Label(
            header,
            text="Red Switcher",
            font=(FONT, 15, "bold"),
            fg=ACCENT,
            bg=BG,
        ).pack(side="left")

        tk.Label(
            main,
            text="Simple image format converter",
            font=(FONT, 8),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(0, 10))

        # Image
        self._section_title(main, "Image")

        self.file_label = self._path_row(
            main,
            "No image selected",
            "Browse",
            self.select_image,
        )

        # Output format
        self._section_title(main, "Output format")

        self.format_menu = tk.OptionMenu(
            main,
            self.output_format,
            *OUTPUT_FORMATS,
        )

        self.format_menu.config(
            bg=PANEL,
            fg=TEXT,
            activebackground=BUTTON,
            activeforeground=TEXT,
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=(FONT, 9),
            anchor="w",
            padx=8,
            pady=3,
        )

        self.format_menu["menu"].config(
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="white",
            font=(FONT, 9),
        )

        self.format_menu.pack(
            fill="x",
            pady=(3, 8),
        )

        # ICO options
        self.options = tk.Frame(main, bg=BG)
        self.options.pack(fill="x")
        self._build_ico_options()

        # Output folder
        self._section_title(main, "Output folder")

        self.folder_label = self._path_row(
            main,
            "Same as source image",
            "Choose",
            self.select_folder,
        )

        # Convert button
        self.convert_button = tk.Button(
            main,
            text="Convert",
            command=self.start_conversion,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            disabledforeground="#EEBBBB",
            relief="flat",
            bd=0,
            font=(FONT, 10, "bold"),
            cursor="hand2",
            pady=7,
        )

        self.convert_button.pack(
            fill="x",
            pady=(2, 6),
        )

        self.status_label = tk.Label(
            main,
            text="Ready",
            font=(FONT, 8),
            fg=MUTED,
            bg=BG,
            anchor="w",
        )
        self.status_label.pack(anchor="w")

    def _build_ico_options(self):
        self.ico_frame = tk.Frame(
            self.options,
            bg=BG,
        )

        tk.Label(
            self.ico_frame,
            text="ICO options",
            font=(FONT, 9, "bold"),
            fg=TEXT,
            bg=BG,
        ).pack(anchor="w")

        tk.Checkbutton(
            self.ico_frame,
            text="Multi-size icon (16 – 256 px)",
            variable=self.ico_multi,
            bg=BG,
            fg=TEXT,
            activebackground=BG,
            activeforeground=TEXT,
            selectcolor=PANEL,
            highlightthickness=0,
            bd=0,
            font=(FONT, 8),
            cursor="hand2",
        ).pack(anchor="w", pady=(2, 0))

        size_row = tk.Frame(
            self.ico_frame,
            bg=BG,
        )
        size_row.pack(
            fill="x",
            pady=(2, 8),
        )

        tk.Label(
            size_row,
            text="Single size (px, max 256):",
            font=(FONT, 8),
            fg=MUTED,
            bg=BG,
        ).pack(side="left")

        self.size_entry = tk.Entry(
            size_row,
            textvariable=self.ico_size,
            width=6,
            bg=PANEL,
            fg=TEXT,
            disabledbackground=BG,
            disabledforeground=MUTED,
            insertbackground=TEXT,
            relief="flat",
            font=(FONT, 9),
            justify="center",
        )

        self.size_entry.pack(
            side="left",
            padx=(8, 0),
            ipady=2,
        )

        self._on_multi_change()

    # ---- Window helpers --------------------------------------------------

    def _fit_window(self, center=False):
        self.update_idletasks()
        height = self.winfo_reqheight()

        if center:
            x = (self.winfo_screenwidth() - WINDOW_WIDTH) // 2
            y = (self.winfo_screenheight() - height) // 2
            self.geometry(
                f"{WINDOW_WIDTH}x{height}+{x}+{y}"
            )
        else:
            self.geometry(
                f"{WINDOW_WIDTH}x{height}"
            )

    def _set_status(self, text, color=MUTED):
        self.status_label.config(
            text=text,
            fg=color,
        )

    # ---- Events ----------------------------------------------------------

    def _on_format_change(self, *_):
        if self.output_format.get() == "ICO":
            self.ico_frame.pack(fill="x")
        else:
            self.ico_frame.pack_forget()

        self._fit_window()

    def _on_multi_change(self, *_):
        self.size_entry.config(
            state=(
                "disabled"
                if self.ico_multi.get()
                else "normal"
            )
        )

    def select_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Supported images", INPUT_PATTERN),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            with Image.open(path) as image:
                image.verify()

            with Image.open(path) as image:
                width, height = image.size

        except Exception as error:
            messagebox.showerror(
                "Invalid image",
                f"Could not open this image.\n\n{error}",
            )
            return

        self.source = Path(path)

        self.file_label.config(
            text=f"{self.source.name}  ({width} × {height})",
            fg=TEXT,
        )

        self._set_status("Image selected")

    def select_folder(self):
        folder = filedialog.askdirectory(
            title="Choose output folder"
        )

        if folder:
            self.output_folder = Path(folder)

            self.folder_label.config(
                text=str(self.output_folder),
                fg=TEXT,
            )

    # ---- Conversion ------------------------------------------------------

    def _read_ico_size(self):
        try:
            size = int(self.ico_size.get())
        except ValueError:
            raise ValueError(
                "Size must be a whole number."
            )

        if not 1 <= size <= ICO_MAX:
            raise ValueError(
                f"Size must be between 1 and {ICO_MAX}."
            )

        return size

    def start_conversion(self):
        if self.source is None:
            messagebox.showwarning(
                "No image",
                "Please select an image first.",
            )
            return

        fmt = self.output_format.get()
        multi = self.ico_multi.get()
        size = ICO_MAX

        if fmt == "ICO" and not multi:
            try:
                size = self._read_ico_size()
            except ValueError as error:
                messagebox.showerror(
                    "Invalid size",
                    str(error),
                )
                return

        output_dir = (
            self.output_folder
            or self.source.parent
        )

        self.convert_button.config(
            state="disabled",
            text="Converting...",
        )

        self._set_status("Converting...")

        threading.Thread(
            target=self._worker,
            args=(
                self.source,
                fmt,
                output_dir,
                multi,
                size,
            ),
            daemon=True,
        ).start()

        self.after(100, self._poll_result)

    def _worker(self, source, fmt, output_dir, multi, size):
        try:
            path = convert_image(
                source,
                fmt,
                output_dir,
                multi,
                size,
            )
            self.results.put(("ok", path))

        except Exception as error:
            self.results.put(("error", error))

    def _poll_result(self):
        try:
            status, value = self.results.get_nowait()

        except queue.Empty:
            self.after(100, self._poll_result)
            return

        self.convert_button.config(
            state="normal",
            text="Convert",
        )

        if status == "ok":
            self._set_status(
                "Conversion complete",
                SUCCESS,
            )

            messagebox.showinfo(
                "Success",
                f"Image converted successfully.\n\n{value}",
            )

        else:
            self._set_status(
                "Conversion failed",
                ACCENT,
            )

            messagebox.showerror(
                "Conversion error",
                f"Could not convert the image.\n\n{value}",
            )


if __name__ == "__main__":
    enable_dpi_awareness()
    RedSwitcher().mainloop()