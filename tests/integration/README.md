# Printer Integration Tests

These tests verify that the MicroWeldr system works correctly with an actual 3D printer.

## Requirements

- **Printer Connection**: Tests require an active PrusaLink connection
- **Safe Environment**: Tests are designed to be safe and non-destructive
- **Fast Execution**: Most tests complete in under 60 seconds

## Running Tests

### Quick Check
```bash
# Check if printer is available
python scripts/test_printer.py --check
```

### Fast Tests (Recommended)
```bash
# Run only fast, safe tests (~1 minute)
python scripts/test_printer.py --fast
```

### All Integration Tests
```bash
# Run all integration tests (~3-5 minutes)
python scripts/test_printer.py
```

### Manual Pytest
```bash
# Run specific test
pytest tests/integration/test_printer_integration.py::TestPrinterIntegration::test_invalid_gcode_handling -v

# Run all integration tests
pytest tests/integration/test_printer_integration.py -v

# Skip integration tests (if no printer)
pytest -m "not integration"
```

## Test Categories

### 🔥 Temperature Tests
- **Validation**: Tests temperature limit validation (120°C bed, 300°C nozzle)
- **Readback**: Verifies temperature clamping detection
- **Safety**: Tests force mode and error handling

### 🎯 Movement Tests
- **Validation**: Tests coordinate limit validation
- **Verification**: Checks actual movement vs requested
- **Safety**: Tests movement beyond printer limits

### 🛡️ Error Handling Tests
- **Invalid G-code**: Tests malformed command handling
- **Safety Halt**: Tests emergency halt functionality
- **Recovery**: Verifies printer remains operational after errors

## Safety Features

### ✅ Safe by Design
- **No Dangerous Commands**: Tests avoid high temperatures or risky movements
- **Small Movements**: Movement tests use minimal, safe displacements
- **Auto Cleanup**: Tests clean up after themselves (turn off heaters, etc.)
- **State Verification**: Always check printer state before and after tests

### 🚫 What Tests DON'T Do
- **No High Temperatures**: Never set dangerous temperatures
- **No Large Movements**: Avoid movements that could cause crashes
- **No File Uploads**: Don't upload large files or start prints
- **No Permanent Changes**: All changes are temporary and cleaned up

## Test Results

### Expected Behavior
```
✅ Printer is available and ready for testing
   State: FINISHED
   Bed: 25.2°C, Nozzle: 22.0°C

🧪 Running fast integration tests...
tests/integration/test_printer_integration.py::TestPrinterIntegration::test_invalid_gcode_handling PASSED
tests/integration/test_printer_integration.py::TestPrinterIntegration::test_error_recovery_and_halt PASSED

= 2 passed in 45.67s =
```

### Troubleshooting

#### Printer Not Available
```
❌ Printer not available: Connection failed
⚠️  Skipping integration tests - printer not available
```
**Solution**: Check PrusaLink connection, verify `secrets.toml` configuration

#### Tests Timeout
**Solution**: Printer may be busy, wait for current operation to complete

#### Permission Errors
**Solution**: Verify PrusaLink API key has proper permissions

## Development

### Adding New Tests
1. Keep tests **fast** (< 60 seconds each)
2. Make tests **safe** (no dangerous operations)
3. Add **cleanup** (reset printer state after test)
4. Use **assertions** to verify expected behavior

### Test Structure
```python
def test_new_feature(self, client):
    """Test description - what it verifies."""
    # Setup - get initial state
    initial_state = client.get_printer_status()

    # Test - perform safe operation
    result = client.safe_operation()
    assert result is True

    # Verify - check expected outcome
    final_state = client.get_printer_status()
    assert expected_condition

    # Cleanup - restore safe state
    client.cleanup_operation()
```

## Integration with CI/CD

These tests can be integrated into CI/CD pipelines with printer hardware:

```yaml
# GitHub Actions example
- name: Run Integration Tests
  run: |
    if python scripts/test_printer.py --check; then
      python scripts/test_printer.py --fast
    else
      echo "Printer not available, skipping integration tests"
    fi
```
