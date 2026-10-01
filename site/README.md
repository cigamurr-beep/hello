# Weidian Finds

A static product-finds site (grid + search + categories, product pages with QC photos and agent buy links).

## Add your products
Export your spreadsheet as CSV and save it as `products.csv` in this folder (or set `CONFIG.csvUrl` in
`index.html` to a Google Sheets "File → Share → Publish to web → CSV" link so edits show up live).

| column | what goes in it |
|---|---|
| `name` | product name |
| `price` | price in ¥ CNY (number) |
| `category` | Shoes, Hoodies, … (becomes a filter chip) |
| `brand` | optional |
| `link` | Weidian item link, e.g. `https://weidian.com/item.html?itemID=1234567890` |
| `image` | main photo URL (optional — first QC photo is used if empty) |
| `qc` | QC photo URLs separated by `|` |
| `notes` | batch, sizing, anything else |

Agent buttons (KakoBuy, CNFans, Mulebuy, …) are built from the Weidian `itemID`. Edit `CONFIG.agents`
in `index.html` to add your affiliate codes or change the list.

## Run locally
`python3 -m http.server -d site 8000` then open http://localhost:8000. Any static host works (GitHub Pages, Netlify, Vercel).
