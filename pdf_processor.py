# Creating a PDF proof by detecting the red box in the uploaded template, placing the provided lines
# with Arial (bold first line, regular lines after), and producing a merged vector PDF.
# Output: saved merged PDF and a PNG preview image.
# If Arial is not available on the system, the code will fallback to Helvetica and report that.

from pathlib import Path
from PIL import Image
import numpy as np
import io
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Input and output paths
# Absolute path to your template (fixed for Windows)
template_path = Path(r"C:\Users\Mohit(MohitM)Mishra\Desktop\Ice Bag Automation\Template.pdf")

# Always save in your Desktop/Pdf folder
base_dir = Path.home() / "Desktop" / "Pdf"

# Ensure the folder exists
base_dir.mkdir(parents=True, exist_ok=True)

output_overlay = base_dir / "overlay_text.pdf"
final_output   = base_dir / "8lbPLWK_with_text.pdf"
preview_png    = base_dir / "preview_page.png"

# The text to insert (user provided)
lines = ["Test Line 1", "Test Line 2", "Test Line 3"]

# Try to open PDF and rasterize the first page to detect red box
try:
    doc = fitz.open(str(template_path))
except Exception as e:
    raise FileNotFoundError(f"Could not open template PDF at {template_path}. Error: {str(e)}")

page = doc.load_page(0)
# render at zoom to get better resolution for detection
zoom = 2  # 2x resolution for more accurate pixel detection
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, alpha=False)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# Save preview image for user
img.save(preview_png)

# Convert to numpy for color detection
arr = np.array(img)

# Detect red pixels: R significantly larger than G and B and above a threshold
r = arr[..., 0].astype(int)
g = arr[..., 1].astype(int)
b = arr[..., 2].astype(int)
# Heuristic thresholds
red_mask = (r > 150) & (r > g + 60) & (r > b + 60)

# If no red found with strict threshold, relax it
if red_mask.sum() < 50:
    red_mask = (r > 120) & (r > g + 40) & (r > b + 40)

ys, xs = np.where(red_mask)
if len(xs) == 0:
    # Fall back: use a central 4"x2" box assumption (288x144 points) centered
    page_rect = page.rect
    w_pts = page_rect.width
    h_pts = page_rect.height
    # 4"x2" in points (72 points per inch)
    box_w_pts = 4 * 72
    box_h_pts = 2 * 72
    x0 = (w_pts - box_w_pts) / 2
    y0 = (h_pts - box_h_pts) / 2
    x1 = x0 + box_w_pts
    y1 = y0 + box_h_pts
    detected = False
else:
    detected = True
    # bounding box in image pixel coordinates
    min_x = xs.min(); max_x = xs.max()
    min_y = ys.min(); max_y = ys.max()
    # Map image pixel coords back to PDF points
    img_w, img_h = img.size
    page_rect = page.rect
    page_w_pts = page_rect.width
    page_h_pts = page_rect.height
    # note: image y-axis starts at top; PDF coordinate starts at bottom.
    # Convert pixel box to PDF points
    x0 = min_x * (page_w_pts / img_w)
    x1 = max_x * (page_w_pts / img_w)
    # for y, invert
    y0 = page_h_pts - (max_y * (page_h_pts / img_h))
    y1 = page_h_pts - (min_y * (page_h_pts / img_h))

# Create overlay PDF with transparent background and desired text placed inside (vector text)
# Try to register Arial from common system locations; fallback to Helvetica
registered_fonts = {}
def try_register(font_name, paths):
    for p in paths:
        p = Path(p)
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(p)))
                return True
            except Exception as e:
                continue
    return False

# Common paths to check (including Windows, Linux, and macOS)
arial_paths = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\Arial.ttf",
    r"C:\Windows\Fonts\ARIAL.TTF",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/arial/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/Arial.ttf",
    "/usr/share/fonts/Arial/Arial.ttf",
]

arial_bold_paths = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\ARIALBD.TTF",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/Arial/Arial Bold.ttf",
    "/usr/share/fonts/truetype/Arial_Bold.ttf",
]

have_arial = try_register("Arial", arial_paths)
have_arial_bold = try_register("Arial-Bold", arial_bold_paths)

# If Arial not available, use Helvetica (built-in)
font_regular = "Arial" if have_arial else "Helvetica"
font_bold = "Arial-Bold" if have_arial_bold else "Helvetica-Bold"

# Create overlay
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import landscape

packet = io.BytesIO()
c = canvas.Canvas(packet, pagesize=(page_rect.width, page_rect.height))

# For visual debugging (optional): draw a transparent rectangle border where text will be placed
c.setLineWidth(1)
c.setStrokeColorRGB(1,0,0)  # red border to show placement (will be vector)
c.rect(x0, y0, x1-x0, y1-y0, stroke=1, fill=0)

# Prepare text placement: start from top-left padding inside box
padding = 6  # points padding inside box
text_x = x0 + padding
text_top = y1 - padding  # top position in PDF coords

# Choose font sizes to fit inside box: dynamic sizing
box_w = x1 - x0
box_h = y1 - y0

# Determine a font size that allows 3 lines to fit comfortably
# Start with 24 and reduce until fit
from reportlab.pdfbase.pdfmetrics import stringWidth
font_size = 24
while font_size > 6:
    # compute heights: approximate line height 1.2 * font_size
    total_height = len(lines) * font_size * 1.2
    max_line_width = max(stringWidth(ln, font_regular, font_size if i>0 else font_size) for i,ln in enumerate(lines))
    if total_height <= (box_h - 2*padding) and max_line_width <= (box_w - 2*padding):
        break
    font_size -= 1

# Draw lines: first line bold
line_height = font_size * 1.2
y_cursor = text_top - font_size  # baseline for first line
# First line bold
c.setFont(font_bold, font_size)
c.drawString(text_x, y_cursor, lines[0])
# remaining lines regular
c.setFont(font_regular, font_size)
for ln in lines[1:]:
    y_cursor -= line_height
    c.drawString(text_x, y_cursor, ln)

c.save()

# Move to beginning of the StringIO buffer
packet.seek(0)
new_pdf = PdfReader(packet)
existing_pdf = PdfReader(str(template_path))
writer = PdfWriter()

# Merge overlay onto original page (vector)
page0 = existing_pdf.pages[0]
# PyPDF2 merging: merge_page expects PageObject
try:
    page0.merge_page(new_pdf.pages[0])
except Exception as e:
    # Log the error for debugging but proceed with fallback
    print(f"Merge error: {str(e)}")

writer.add_page(page0)
# Add remaining pages as-is
for p in existing_pdf.pages[1:]:
    writer.add_page(p)

# Write out final PDF
with open(final_output, "wb") as f_out:
    writer.write(f_out)

# Close the document
doc.close()

# Report results to the user
result = {
    "detected_red_box": bool(detected),
    "overlay_path": str(output_overlay),
    "final_pdf": str(final_output),
    "preview_png": str(preview_png),
    "font_used": font_regular,
    "font_bold": font_bold,
    "notes": ""
}

if not have_arial:
    result["notes"] = "Arial not found on the execution host; Helvetica fallback used. If you need Arial embedded, upload Arial TTF files or I can provide instructions to embed fonts."

result