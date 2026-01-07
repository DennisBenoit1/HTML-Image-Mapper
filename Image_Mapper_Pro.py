import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import json
import os
import re
import shutil
from string import Template


MACRO_FILE = "macros.json"


class ImageMapper:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Page Image Mapper with Macros + Import")

        # ----------------------------
        # DATA STRUCTURES
        # ----------------------------
        self.pages = {}  # page_name -> {path, image, hotspots}
        self.current_page = None
        self.temp_rect = None
        self.start_x = None
        self.start_y = None

        # Load macros from disk
        self.macros = self.load_macros()

        # ----------------------------
        # GUI LAYOUT (Three-Pane Editor)
        # ----------------------------
        self.root.geometry("1400x900")

        # LEFT PANEL — Pages list
        self.left_frame = tk.Frame(self.root, width=240)
        self.left_frame.pack(side="left", fill="y")

        tk.Label(self.left_frame, text="Pages", font=("Arial", 12, "bold")).pack(pady=4)
        self.page_listbox = tk.Listbox(self.left_frame, width=25)
        self.page_listbox.pack(fill="y", expand=True)
        self.page_listbox.bind("<<ListboxSelect>>", self.on_page_select)

        self.btn_add_page = tk.Button(self.left_frame, text="Add Page", command=self.add_page)
        self.btn_add_page.pack(pady=5)

        self.btn_import_html = tk.Button(self.left_frame, text="Import HTML", command=self.import_html)
        self.btn_import_html.pack(pady=5)

        # CENTER PANEL — Canvas
        self.center_frame = tk.Frame(self.root)
        self.center_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(self.center_frame, cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # RIGHT PANEL — Hotspot Inspector + Macros
        self.right_frame = tk.Frame(self.root, width=300)
        self.right_frame.pack(side="right", fill="y")

        tk.Label(self.right_frame, text="Hotspots", font=("Arial", 12, "bold")).pack(pady=4)
        self.hotspot_listbox = tk.Listbox(self.right_frame, width=45)
        self.hotspot_listbox.pack(fill="y", expand=True)
        self.hotspot_listbox.bind("<<ListboxSelect>>", self.on_hotspot_select)

        # Hotspot Edit Buttons
        self.btn_edit_hotspot = tk.Button(
            self.right_frame, text="Edit Hotspot Target", command=self.edit_hotspot
        )
        self.btn_edit_hotspot.pack(pady=3)

        self.btn_delete_hotspot = tk.Button(
            self.right_frame, text="Delete Hotspot", command=self.delete_hotspot
        )
        self.btn_delete_hotspot.pack(pady=3)

        # Macro Buttons
        tk.Label(self.right_frame, text="Macros", font=("Arial", 12, "bold")).pack(pady=10)

        self.btn_save_macro = tk.Button(
            self.right_frame, text="Save Current Page as Macro", command=self.save_macro
        )
        self.btn_save_macro.pack(pady=3)

        self.btn_apply_macro = tk.Button(
            self.right_frame, text="Apply Macro to Page", command=self.apply_macro
        )
        self.btn_apply_macro.pack(pady=3)

        # Export Button
        self.btn_export = tk.Button(self.right_frame, text="Export HTML", command=self.export_html)
        self.btn_export.pack(pady=10)

    # ============================================================
    # MACRO LOAD/SAVE
    # ============================================================
    def load_macros(self):
        if not os.path.exists(MACRO_FILE):
            return {}
        try:
            with open(MACRO_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_macros_to_disk(self):
        with open(MACRO_FILE, "w") as f:
            json.dump(self.macros, f, indent=4)
    # ============================================================
    # PAGE MANAGEMENT
    # ============================================================
    def add_page(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")]
        )
        if not path:
            return

        page_name = os.path.basename(path)

        if page_name not in self.pages:
            img = Image.open(path)
            self.pages[page_name] = {"path": path, "image": img, "hotspots": []}
            self.page_listbox.insert("end", page_name)

        self.select_page(page_name)

    def select_page(self, page_name):
        self.current_page = page_name
        self.page_listbox.selection_clear(0, "end")
        idx = list(self.pages.keys()).index(page_name)
        self.page_listbox.selection_set(idx)
        self.page_listbox.activate(idx)
        self.load_canvas_image()
        self.refresh_hotspot_list()

    def on_page_select(self, event):
        selection = self.page_listbox.curselection()
        if selection:
            page_name = self.page_listbox.get(selection[0])
            self.select_page(page_name)

    # ============================================================
    # CANVAS / IMAGE DISPLAY
    # ============================================================
    def load_canvas_image(self):
        self.canvas.delete("all")
        page = self.pages[self.current_page]
        self.tk_img = ImageTk.PhotoImage(page["image"])
        self.canvas.config(width=self.tk_img.width(), height=self.tk_img.height())
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.draw_hotspots()

    def on_mouse_down(self, event):
        if not self.current_page:
            return
        self.start_x = event.x
        self.start_y = event.y

    def on_mouse_drag(self, event):
        if self.temp_rect:
            self.canvas.delete(self.temp_rect)
        self.temp_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y, outline="red"
        )

    def on_mouse_up(self, event):
        if not self.temp_rect or not self.current_page:
            return

        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y

        target_path = filedialog.askopenfilename(
            title="Select Target Image for Hotspot",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")]
        )
        if not target_path:
            self.canvas.delete(self.temp_rect)
            self.temp_rect = None
            return

        target_name = os.path.basename(target_path)

        # Auto-add target page if missing (your Option A)
        if target_name not in self.pages:
            img = Image.open(target_path)
            self.pages[target_name] = {"path": target_path, "image": img, "hotspots": []}
            self.page_listbox.insert("end", target_name)

        # Add hotspot
        hotspot = {"coords": (x1, y1, x2, y2), "target": target_name}
        self.pages[self.current_page]["hotspots"].append(hotspot)

        self.temp_rect = None
        self.draw_hotspots()
        self.refresh_hotspot_list()

    # ============================================================
    # HOTSPOT HANDLING
    # ============================================================
    def draw_hotspots(self):
        if not self.current_page:
            return
        for hs in self.pages[self.current_page]["hotspots"]:
            x1, y1, x2, y2 = hs["coords"]
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue")

    def refresh_hotspot_list(self):
        self.hotspot_listbox.delete(0, "end")
        if not self.current_page:
            return
        for idx, hs in enumerate(self.pages[self.current_page]["hotspots"]):
            x1, y1, x2, y2 = hs["coords"]
            target = hs["target"]
            self.hotspot_listbox.insert(
                "end", f"{idx+1}: ({x1},{y1},{x2},{y2}) → {target}"
            )

    def on_hotspot_select(self, event):
        pass

    def edit_hotspot(self):
        selection = self.hotspot_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        hs = self.pages[self.current_page]["hotspots"][idx]

        new_target = filedialog.askopenfilename(
            title="Select New Target Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif")]
        )
        if not new_target:
            return

        new_target_name = os.path.basename(new_target)

        # Auto-add page if not exists
        if new_target_name not in self.pages:
            img = Image.open(new_target)
            self.pages[new_target_name] = {"path": new_target, "image": img, "hotspots": []}
            self.page_listbox.insert("end", new_target_name)

        hs["target"] = new_target_name
        self.refresh_hotspot_list()

    def delete_hotspot(self):
        selection = self.hotspot_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        self.pages[self.current_page]["hotspots"].pop(idx)
        self.load_canvas_image()
        self.refresh_hotspot_list()

    # ============================================================
    # MACROS — SAVE & APPLY
    # ============================================================
    def save_macro(self):
        if not self.current_page:
            messagebox.showerror("Error", "No page loaded.")
            return

        hotspots = self.pages[self.current_page]["hotspots"]
        if not hotspots:
            messagebox.showerror("Error", "No hotspots to save as a macro.")
            return

        name = simpledialog.askstring("Macro Name", "Enter a name for this macro:")
        if not name:
            return

        self.macros[name] = hotspots.copy()
        self.save_macros_to_disk()
        messagebox.showinfo("Saved", f"Macro '{name}' saved.")

    def apply_macro(self):
        if not self.macros:
            messagebox.showerror("Error", "No macros available.")
            return

        macro_names = list(self.macros.keys())
        name = simpledialog.askstring(
            "Apply Macro",
            "Enter Macro Name:\n" + "\n".join(macro_names)
        )
        if not name or name not in self.macros:
            return

        macro_hotspots = self.macros[name]

        # Option A — Add on top of existing hotspots
        for hs in macro_hotspots:
            target_name = hs["target"]

            # Auto-add missing pages
            if target_name not in self.pages:
                target_path = os.path.join(os.getcwd(), target_name)
                if not os.path.exists(target_path):
                    messagebox.showinfo(
                        "Missing Image",
                        f"Image '{target_name}' not found. Please locate it."
                    )
                    target_path = filedialog.askopenfilename(
                        title=f"Locate {target_name}",
                        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif")]
                    )
                img = Image.open(target_path)
                self.pages[target_name] = {"path": target_path, "image": img, "hotspots": []}
                self.page_listbox.insert("end", target_name)

            # Add the hotspot
            self.pages[self.current_page]["hotspots"].append(hs.copy())

        self.load_canvas_image()
        self.refresh_hotspot_list()
        messagebox.showinfo("Macro Applied", f"Macro '{name}' applied to this page.")
    # ============================================================
    # EXPORT HTML SIMULATOR
    # ============================================================
    def export_html(self):
        if not self.pages:
            messagebox.showerror("Error", "No pages to export.")
            return

        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if not export_dir:
            return

        # Copy images
        for page_name, page in self.pages.items():
            src = page["path"]
            dst = os.path.join(export_dir, os.path.basename(src))
            shutil.copy(src, dst)

        # Build JS array for hotspots
        areas_js = []
        for page_name, page_data in self.pages.items():
            for hs in page_data["hotspots"]:
                x1, y1, x2, y2 = hs["coords"]
                areas_js.append(
                    "{x1:%d, y1:%d, x2:%d, y2:%d, target:'%s', base:'%s'}" %
                    (x1, y1, x2, y2, hs["target"], page_name)
                )
        areas_js_str = "[" + ",".join(areas_js) + "]"

        first_page = list(self.pages.keys())[0]

        # HTML Template
        template = Template("""
<!DOCTYPE html>
<html>
<head>
<title>Image Map Simulator</title>
<style>
#container { position: relative; display: inline-block; }
#mainImage { display: block; }
.area {
    position: absolute;
    border: 2px solid rgba(255,0,0,0.25);
    cursor: pointer;
    z-index: 10;
}
</style>
<script>
let areas = $areas_js;

function loadImage(img) {
    const main = document.getElementById("mainImage");
    main.src = img;
    main.onload = () => redrawHotspots(img);
}

function redrawHotspots(baseImg) {
    const container = document.getElementById("container");
    document.querySelectorAll(".area").forEach(a => a.remove());

    areas.filter(a => a.base === baseImg).forEach(hs => {
        let div = document.createElement("div");
        div.className = "area";
        div.style.left = hs.x1 + "px";
        div.style.top = hs.y1 + "px";
        div.style.width = (hs.x2 - hs.x1) + "px";
        div.style.height = (hs.y2 - hs.y1) + "px";
        div.onclick = () => loadImage(hs.target);
        container.appendChild(div);
    });
}

window.onload = () => loadImage("$first_page");
</script>
</head>

<body>
<div id="container">
    <img id="mainImage" src="">
</div>
</body>
</html>
""")

        html = template.substitute(
            areas_js=areas_js_str,
            first_page=first_page
        )

        with open(os.path.join(export_dir, "index.html"), "w") as f:
            f.write(html)

        messagebox.showinfo("Export Complete", "The HTML simulator was created successfully!")

    # ============================================================
    # IMPORT HTML BACK INTO THE EDITOR
    # ============================================================
    def import_html(self):
        html_path = filedialog.askopenfilename(
            title="Import HTML Simulator",
            filetypes=[("HTML Files", "*.html")]
        )
        if not html_path:
            return

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Extract `areas = [...]`
        match = re.search(r"areas\s*=\s*(\[[^\]]*\])", html)
        if not match:
            messagebox.showerror("Error", "Could not find hotspot data in HTML.")
            return

        areas_text = match.group(1)

        # Convert JS objects to python dict-safe format
        areas_text = areas_text.replace("'", '"')

        # Add quotes around keys (JS → JSON)
        areas_text = re.sub(r"(\w+):", r'"\1":', areas_text)

        try:
            areas = json.loads(areas_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse hotspot data:\n{e}")
            return

        # Reset editor state
        self.pages = {}
        self.page_listbox.delete(0, "end")

        html_dir = os.path.dirname(html_path)

        # Rebuild pages & load images
        for hs in areas:
            base = hs["base"]

            if base not in self.pages:
                img_path = os.path.join(html_dir, base)

                if not os.path.exists(img_path):
                    messagebox.showwarning(
                        "Missing Image",
                        f"Image '{base}' not found. Please locate it."
                    )
                    img_path = filedialog.askopenfilename(
                        title=f"Locate {base}",
                        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif")]
                    )

                img = Image.open(img_path)
                self.pages[base] = {"path": img_path, "image": img, "hotspots": []}
                self.page_listbox.insert("end", base)

        # Rebuild hotspots
        for hs in areas:
            base = hs["base"]
            coords = (hs["x1"], hs["y1"], hs["x2"], hs["y2"])
            target = hs["target"]

            # Ensure target pages exist
            if target not in self.pages:
                target_path = os.path.join(html_dir, target)
                if not os.path.exists(target_path):
                    messagebox.showwarning(
                        "Missing Image",
                        f"Target image '{target}' is missing. Please locate it."
                    )
                    target_path = filedialog.askopenfilename(
                        title=f"Locate {target}",
                        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif")]
                    )
                img = Image.open(target_path)
                self.pages[target] = {"path": target_path, "image": img, "hotspots": []}
                self.page_listbox.insert("end", target)

            self.pages[base]["hotspots"].append({"coords": coords, "target": target})

        first_page = list(self.pages.keys())[0]
        self.select_page(first_page)
        messagebox.showinfo("Import Complete", "HTML successfully imported into the editor!")

# ============================================================
# MAIN ENTRYPOINT
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageMapper(root)
    root.mainloop()
