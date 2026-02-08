#!/bin/bash
echo ""
echo "  ============================================================"
echo "    CFA MockGen - CFA Level I Mock Exam Generator"
echo "  ============================================================"
echo ""

# Install dependencies
echo "  Installing dependencies..."
pip3 install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt -q 2>/dev/null
echo "  [OK] Dependencies ready."
echo ""

echo "  Starting server..."
echo "  Your browser will open automatically."
echo "  Keep this terminal open while using the app."
echo ""
echo "  ============================================================"
echo "    http://localhost:5000"
echo "  ============================================================"
echo ""

# Open browser after 2 seconds
(sleep 2 && open http://localhost:5000 2>/dev/null || xdg-open http://localhost:5000 2>/dev/null) &

# Start server
python3 backend/app.py || python backend/app.py
