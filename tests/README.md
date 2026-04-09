# Z-Machine Unit Tests

## Running Tests
```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_opcodes.py -v

# Single test
pytest tests/test_opcodes.py::TestArithmeticOpcodes::test_add_overflow -v

# By marker
pytest tests/ -m regression
pytest tests/ -m unit
```

## Test Categories
- **unit**: Individual component tests
- **integration**: Multi-component tests
- **regression**: Specific bug fix tests
- **slow**: Long-running tests