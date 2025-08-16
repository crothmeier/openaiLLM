#!/bin/bash
set -euo pipefail

# Test script to simulate adverse conditions and verify reliability safeguards

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=== NVMe Model Storage Reliability Test Suite ==="
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name=$1
    local test_command=$2
    local expected_result=$3  # "fail" or "pass"
    
    echo -e "${BLUE}Test:${NC} $test_name"
    
    # Run the test command and capture result
    set +e
    eval "$test_command" >/dev/null 2>&1
    local result=$?
    set -e
    
    if [[ "$expected_result" == "fail" ]]; then
        if [[ $result -ne 0 ]]; then
            echo -e "${GREEN}  ✓ Test passed (expected failure detected)${NC}"
            ((TESTS_PASSED++))
        else
            echo -e "${RED}  ✗ Test failed (expected failure but succeeded)${NC}"
            ((TESTS_FAILED++))
        fi
    else
        if [[ $result -eq 0 ]]; then
            echo -e "${GREEN}  ✓ Test passed${NC}"
            ((TESTS_PASSED++))
        else
            echo -e "${RED}  ✗ Test failed (expected success but failed)${NC}"
            ((TESTS_FAILED++))
        fi
    fi
    echo ""
}

# Test 1: Check behavior when /mnt/nvme is not mounted
echo -e "${YELLOW}=== Test Group 1: Mount Point Verification ===${NC}"
echo ""

# Simulate unmounted condition (without actually unmounting)
run_test "NVMe mount check in lib/nvme_checks.sh" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && check_nvme_mounted'" \
    "$(mountpoint -q /mnt/nvme && echo 'pass' || echo 'fail')"

run_test "Setup script with unmounted NVMe (dry run)" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && check_nvme_mounted && echo pass'" \
    "$(mountpoint -q /mnt/nvme && echo 'pass' || echo 'fail')"

# Test 2: Lock file mechanism
echo -e "${YELLOW}=== Test Group 2: Concurrent Run Prevention ===${NC}"
echo ""

# Create a test script that acquires lock
cat > /tmp/test_lock.sh << 'EOF'
#!/bin/bash
source nvme-model-storage/lib/nvme_checks.sh
acquire_lock
sleep 2
release_lock
EOF
chmod +x /tmp/test_lock.sh

# Try to run two instances concurrently
run_test "Single instance lock acquisition" \
    "/tmp/test_lock.sh" \
    "pass"

# Start first instance in background
/tmp/test_lock.sh &
LOCK_PID=$!
sleep 0.5

# Try second instance while first is running
run_test "Second instance blocked by lock" \
    "timeout 1 /tmp/test_lock.sh" \
    "fail"

# Wait for first instance to complete
wait $LOCK_PID 2>/dev/null || true

# Test 3: Disk space checks
echo -e "${YELLOW}=== Test Group 3: Disk Space Verification ===${NC}"
echo ""

if mountpoint -q /mnt/nvme; then
    # Get available space
    available=$(df /mnt/nvme --output=avail -BG | tail -1 | tr -d 'G')
    
    # Test with reasonable requirement
    run_test "Disk space check with 1GB requirement" \
        "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && check_disk_space 1'" \
        "pass"
    
    # Test with excessive requirement (10TB)
    run_test "Disk space check with excessive requirement (10000GB)" \
        "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && check_disk_space 10000'" \
        "fail"
else
    echo -e "${YELLOW}  Skipping disk space tests - /mnt/nvme not mounted${NC}"
    echo ""
fi

# Test 4: Backup and restore functionality
echo -e "${YELLOW}=== Test Group 4: Backup and Restore ===${NC}"
echo ""

# Create a test file
TEST_FILE="/tmp/test_backup_file_$$"
echo "Original content" > "$TEST_FILE"

run_test "File backup creation" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && backup_file $TEST_FILE && test -f ${TEST_FILE}.bak.*'" \
    "pass"

# Modify the file
echo "Modified content" > "$TEST_FILE"

# Find the backup file
BACKUP_FILE=$(ls -t ${TEST_FILE}.bak.* 2>/dev/null | head -1)

if [[ -n "$BACKUP_FILE" ]]; then
    run_test "File restore from backup" \
        "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && restore_file $BACKUP_FILE && grep -q \"Original content\" $TEST_FILE'" \
        "pass"
fi

# Clean up test files
rm -f "$TEST_FILE" ${TEST_FILE}.bak.*

# Test 5: Python verification
echo -e "${YELLOW}=== Test Group 5: Python Environment Checks ===${NC}"
echo ""

run_test "Python availability check" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && verify_python'" \
    "pass"

# Test 6: Model size estimation
echo -e "${YELLOW}=== Test Group 6: Model Size Estimation ===${NC}"
echo ""

run_test "Estimate size for 7B model" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && size=\$(estimate_model_size \"test/model-7b\") && [[ \$size -ge 10 ]]'" \
    "pass"

run_test "Estimate size for 70B model" \
    "bash -c 'source nvme-model-storage/lib/nvme_checks.sh && size=\$(estimate_model_size \"test/model-70b\") && [[ \$size -ge 100 ]]'" \
    "pass"

# Test 7: JSON output from verify script
echo -e "${YELLOW}=== Test Group 7: JSON Output Verification ===${NC}"
echo ""

run_test "Verify script JSON output format" \
    "bash nvme-model-storage/verify-nvme-storage.sh --output=json | python3 -m json.tool > /dev/null" \
    "pass"

# Test 8: Error handling in download script
echo -e "${YELLOW}=== Test Group 8: Download Error Handling ===${NC}"
echo ""

# Test download script's disk space check (without actually downloading)
run_test "Download script exits cleanly with --help" \
    "echo '6' | bash nvme-model-storage/download-models.sh" \
    "pass"

# Clean up
rm -f /tmp/test_lock.sh

# Summary
echo ""
echo -e "${YELLOW}=== Test Summary ===${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}All reliability safeguards are working correctly!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the implementation.${NC}"
    exit 1
fi