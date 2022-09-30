#!/bin/bash
python3 src/generate_html.py  --output ../www/index.html data/*.textproto data/sites/*.textproto data/sites/*/*.textproto
