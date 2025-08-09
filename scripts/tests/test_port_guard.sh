#!/bin/bash
# Test script to demonstrate port guard functionality

echo "=== Port Guard Test Script ==="
echo ""

echo "1. Testing with free port (8010):"
./check_port_free.sh 8010 && echo "✓ Port check passed" || echo "✗ Port check failed"

echo ""
echo "2. Testing with occupied port (8080):"
./check_port_free.sh 8080 && echo "✓ Port check passed" || echo "✗ Port check failed (expected)"

echo ""
echo "3. Starting a test listener on 8010 to simulate conflict:"
python3 -m http.server 8010 >/dev/null 2>&1 &
TEST_PID=$!
sleep 1

echo "4. Testing port 8010 while occupied:"
./check_port_free.sh 8010 && echo "✓ Port check passed" || echo "✗ Port check failed (expected)"

echo ""
echo "5. Cleaning up test listener..."
kill $TEST_PID 2>/dev/null
sleep 1

echo "6. Testing port 8010 after cleanup:"
./check_port_free.sh 8010 && echo "✓ Port check passed" || echo "✗ Port check failed"

echo ""
echo "=== Test Complete ==="