#!/bin/bash
python3 src/generate_html.py  --output ../docs/index.html data/*.textproto data/sites/*.textproto data/sites/*/*.textproto
