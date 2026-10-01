# Photo sheets

Artifact pages can't load images from other hosts, so the page reads product photos from
sheets published next to it (`img/c/NNN.jpg` card images, `img/g/NNN.jpg` listing photos).
When a sheet is missing (e.g. opening this repo's `index.html` directly) each image falls
back to its Weidian URL.

To rebuild after editing PRODUCTS: write one product JSON object per line to
`products.jsonl`, then run `download_photos.py` followed by `build_sheets.py` (needs Pillow).
Product order matters: sheet positions come from each product's index in PRODUCTS.
