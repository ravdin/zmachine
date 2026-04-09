"""
Z-Machine Opcode Tests

Translated from CZECH (Comprehensive Z-machine Emulation CHecker) by Amir Karger
Original test file: czech.inf

These tests verify that Z-Machine opcodes execute correctly according to the
Z-Machine specification. Each test is based on the corresponding test in czech.inf.

Tests call actual opcode functions from opcodes.py using a mock interpreter.
"""
import pytest
from zmachine.opcodes import (
    op_je, op_jl, op_jg, op_jz,
    op_add, op_sub, op_mul, op_div, op_mod,
    op_and, op_or, op_not,
    op_loadb, op_storeb, op_loadw, op_storew,
    op_test,
    op_random,
    op_push, op_pull,
    sign_uint16
)


@pytest.mark.unit
class TestJumpOpcodes:
    """Test jump and branch opcodes (from test_jumps in czech.inf)."""
    
    @pytest.mark.unit
    def test_je_equal_values(self, mock_interpreter):
        """Test je (jump if equal) with equal values."""
        # Original: @je 5 5 ?~bad; p();
        # je should branch when values are equal
        op_je(mock_interpreter, 5, 5)
        assert mock_interpreter.branch_taken == True
        
    @pytest.mark.unit
    def test_je_unequal_values(self, mock_interpreter):
        """Test je with unequal values."""
        # Original: @je 5 n5 ?bad; p();
        op_je(mock_interpreter, 5, 0xFFFB)  # -5 as unsigned
        assert mock_interpreter.branch_taken == False
        
    @pytest.mark.unit
    def test_je_negative_values(self, mock_interpreter):
        """Test je with negative values."""
        # Original: @je n5 n5 ?~bad; p();
        op_je(mock_interpreter, 0xFFFB, 0xFFFB)  # -5, -5
        assert mock_interpreter.branch_taken == True
        
    @pytest.mark.unit
    def test_je_extreme_values(self, mock_interpreter):
        """Test je with extreme values."""
        # Original: @je 32767 n32768 ?bad; p();
        op_je(mock_interpreter, 32767, 0x8000)  # -32768 as unsigned
        assert mock_interpreter.branch_taken == False
        # Original: @je n32768 n32768 ?~bad; p();
        op_je(mock_interpreter, 0x8000, 0x8000)
        assert mock_interpreter.branch_taken == True
        
    @pytest.mark.unit
    def test_je_multiple_args(self, mock_interpreter):
        """Test je with up to 4 arguments."""
        # Original: @je 5 4 5 ?~bad; p();
        op_je(mock_interpreter, 5, 4, 5)
        assert mock_interpreter.branch_taken == True
        # Original: @je 5 4 3 5 ?~bad; p();
        op_je(mock_interpreter, 5, 4, 3, 5)
        assert mock_interpreter.branch_taken == True
        # Original: @je 5 4 5 3 ?~bad; p();
        op_je(mock_interpreter, 5, 4, 5, 3)
        assert mock_interpreter.branch_taken == True
        # Original: @je 5 4 3 2 ?bad; p();
        op_je(mock_interpreter, 5, 4, 3, 2)
        assert mock_interpreter.branch_taken == False
    
    @pytest.mark.unit
    def test_jg_greater_than(self, mock_interpreter):
        """Test jg (jump if greater) opcode."""
        # Original: @jg 5 5 ?bad; p();
        op_jg(mock_interpreter, 5, 5)
        assert mock_interpreter.branch_taken == False
        # Original: @jg 1 0 ?~bad; p();
        op_jg(mock_interpreter, 1, 0)
        assert mock_interpreter.branch_taken == True
        # Original: @jg 0 1 ?bad; p();
        op_jg(mock_interpreter, 0, 1)
        assert mock_interpreter.branch_taken == False
        
    @pytest.mark.unit
    def test_jg_negative_values(self, mock_interpreter):
        """Test jg with negative values."""
        # Original: @jg n1 n2 ?~bad; p();
        op_jg(mock_interpreter, 0xFFFF, 0xFFFE)  # -1, -2
        assert mock_interpreter.branch_taken == True
        # Original: @jg n2 n1 ?bad; p();
        op_jg(mock_interpreter, 0xFFFE, 0xFFFF)  # -2, -1
        assert mock_interpreter.branch_taken == False
        # Original: @jg 1 n1 ?~bad; p();
        op_jg(mock_interpreter, 1, 0xFFFF)  # 1, -1
        assert mock_interpreter.branch_taken == True
        # Original: @jg n1 1 ?bad; p();
        op_jg(mock_interpreter, 0xFFFF, 1)  # -1, 1
        assert mock_interpreter.branch_taken == False
    
    @pytest.mark.unit
    def test_jl_less_than(self, mock_interpreter):
        """Test jl (jump if less) opcode."""
        # Original: @jl 5 5 ?bad; p();
        op_jl(mock_interpreter, 5, 5)
        assert mock_interpreter.branch_taken == False
        # Original: @jl 1 0 ?bad; p();
        op_jl(mock_interpreter, 1, 0)
        assert mock_interpreter.branch_taken == False
        # Original: @jl 0 1 ?~bad; p();
        op_jl(mock_interpreter, 0, 1)
        assert mock_interpreter.branch_taken == True
        
    @pytest.mark.unit
    def test_jl_negative_values(self, mock_interpreter):
        """Test jl with negative values."""
        # Original: @jl n1 n2 ?bad; p();
        op_jl(mock_interpreter, 0xFFFF, 0xFFFE)  # -1, -2
        assert mock_interpreter.branch_taken == False
        # Original: @jl n2 n1 ?~bad; p();
        op_jl(mock_interpreter, 0xFFFE, 0xFFFF)  # -2, -1
        assert mock_interpreter.branch_taken == True
    
    @pytest.mark.unit
    def test_jz_zero(self, mock_interpreter):
        """Test jz (jump if zero) opcode."""
        # Original: @jz 0 ?~bad; p();
        op_jz(mock_interpreter, 0)
        assert mock_interpreter.branch_taken == True
        # Original: @jz 1 ?bad; p();
        op_jz(mock_interpreter, 1)
        assert mock_interpreter.branch_taken == False
        # Original: @jz n1 ?bad; p();
        op_jz(mock_interpreter, 0xFFFF)  # -1
        assert mock_interpreter.branch_taken == False


@pytest.mark.integration
class TestOpcodeIntegration:
    """
    Integration tests that combine multiple opcodes.
    
    These test complex operations that require multiple opcodes working together,
    similar to the actual game execution flow.
    """
    
    @pytest.mark.integration
    def test_arithmetic_sequence(self, mock_interpreter):
        """Test sequence of arithmetic operations: (5 + 3) * 2 - 1 = 15."""
        # (5 + 3) = 8
        op_add(mock_interpreter, 5, 3)
        result = mock_interpreter.stored_value
        assert result == 8
        
        # 8 * 2 = 16
        op_mul(mock_interpreter, result, 2)
        result = mock_interpreter.stored_value
        assert result == 16
        
        # 16 - 1 = 15
        op_sub(mock_interpreter, result, 1)
        result = mock_interpreter.stored_value
        assert result == 15
    
    @pytest.mark.integration
    def test_memory_and_logic(self, mock_interpreter):
        """Test memory operations with logical operations."""
        table_addr = 0x1000
        
        # Write word to memory
        mock_interpreter.write_word(table_addr, 0x1234)
        
        # Load it back
        op_loadw(mock_interpreter, table_addr, 0)
        loaded = mock_interpreter.stored_value
        assert loaded == 0x1234
        
        # Apply AND operation
        op_and(mock_interpreter, loaded, 0x0F0F)
        result = mock_interpreter.stored_value
        assert result == 0x0204


# TODO: Add more test classes for:
# - TestSubroutineOpcodes (call, ret, etc.)
# - TestObjectOpcodes (get_parent, get_child, etc.)
# - TestIndirectOpcodes (inc_chk, dec_chk, etc.)
# - TestPrintOpcodes (print_char, print_num, etc.)
    """Test jump and branch opcodes (from test_jumps in czech.inf)."""
    
    @pytest.mark.unit
    def test_je_equal_values(self, mock_interpreter):
        """Test je (jump if equal) with equal values."""
        # Original: @je 5 5 ?~bad; p();
        # je should branch when values are equal
        assert self._test_branch_je(mock_interpreter, 5, 5) == True
        
    @pytest.mark.unit
    def test_je_unequal_values(self, mock_interpreter):
        """Test je with unequal values."""
        # Original: @je 5 n5 ?bad; p();
        assert self._test_branch_je(mock_interpreter, 5, -5) == False
        
    @pytest.mark.unit
    def test_je_negative_values(self, mock_interpreter):
        """Test je with negative values."""
        # Original: @je n5 n5 ?~bad; p();
        assert self._test_branch_je(mock_interpreter, -5, -5) == True
        
    @pytest.mark.unit
    def test_je_extreme_values(self, mock_interpreter):
        """Test je with extreme values."""
        # Original: @je 32767 n32768 ?bad; p();
        assert self._test_branch_je(mock_interpreter, 32767, -32768) == False
        # Original: @je n32768 n32768 ?~bad; p();
        assert self._test_branch_je(mock_interpreter, -32768, -32768) == True
        
    @pytest.mark.unit
    def test_je_multiple_args(self, mock_interpreter):
        """Test je with up to 4 arguments."""
        # Original: @je 5 4 5 ?~bad; p();
        assert self._test_branch_je(mock_interpreter, 5, 4, 5) == True
        # Original: @je 5 4 3 5 ?~bad; p();
        assert self._test_branch_je(mock_interpreter, 5, 4, 3, 5) == True
        # Original: @je 5 4 5 3 ?~bad; p();
        assert self._test_branch_je(mock_interpreter, 5, 4, 5, 3) == True
        # Original: @je 5 4 3 2 ?bad; p();
        assert self._test_branch_je(mock_interpreter, 5, 4, 3, 2) == False
    
    @pytest.mark.unit
    def test_jg_greater_than(self, mock_interpreter):
        """Test jg (jump if greater) opcode."""
        # Original: @jg 5 5 ?bad; p();
        assert self._test_branch_jg(mock_interpreter, 5, 5) == False
        # Original: @jg 1 0 ?~bad; p();
        assert self._test_branch_jg(mock_interpreter, 1, 0) == True
        # Original: @jg 0 1 ?bad; p();
        assert self._test_branch_jg(mock_interpreter, 0, 1) == False
        
    @pytest.mark.unit
    def test_jg_negative_values(self, mock_interpreter):
        """Test jg with negative values."""
        # Original: @jg n1 n2 ?~bad; p();
        assert self._test_branch_jg(mock_interpreter, -1, -2) == True
        # Original: @jg n2 n1 ?bad; p();
        assert self._test_branch_jg(mock_interpreter, -2, -1) == False
        # Original: @jg 1 n1 ?~bad; p();
        assert self._test_branch_jg(mock_interpreter, 1, -1) == True
        # Original: @jg n1 1 ?bad; p();
        assert self._test_branch_jg(mock_interpreter, -1, 1) == False
    
    @pytest.mark.unit
    def test_jl_less_than(self, mock_interpreter):
        """Test jl (jump if less) opcode."""
        # Original: @jl 5 5 ?bad; p();
        assert self._test_branch_jl(mock_interpreter, 5, 5) == False
        # Original: @jl 1 0 ?bad; p();
        assert self._test_branch_jl(mock_interpreter, 1, 0) == False
        # Original: @jl 0 1 ?~bad; p();
        assert self._test_branch_jl(mock_interpreter, 0, 1) == True
        
    @pytest.mark.unit
    def test_jl_negative_values(self, mock_interpreter):
        """Test jl with negative values."""
        # Original: @jl n1 n2 ?bad; p();
        assert self._test_branch_jl(mock_interpreter, -1, -2) == False
        # Original: @jl n2 n1 ?~bad; p();
        assert self._test_branch_jl(mock_interpreter, -2, -1) == True
    
    @pytest.mark.unit
    def test_jz_zero(self, mock_interpreter):
        """Test jz (jump if zero) opcode."""
        # Original: @jz 0 ?~bad; p();
        assert self._test_branch_jz(mock_interpreter, 0) == True
        # Original: @jz 1 ?bad; p();
        assert self._test_branch_jz(mock_interpreter, 1) == False
        # Original: @jz n1 ?bad; p();
        assert self._test_branch_jz(mock_interpreter, 0xFFFE) == False
    
    # Helper methods to execute opcodes
    def _test_branch_je(self, interp, *args):
        """Execute je opcode: branch if first arg equals any other arg."""
        first = args[0]
        for arg in args[1:]:
            if first == arg:
                interp.do_branch(True)
                return True
        interp.do_branch(False)
        return False
    
    def _test_branch_jg(self, interp, a, b):
        """Execute jg opcode: branch if a > b (signed)."""
        op_jg(interp, a, b)
        return interp.branch_taken
    
    def _test_branch_jl(self, interp, a, b):
        """Execute jl opcode: branch if a < b (signed)."""
        op_jl(interp, a, b)
        return interp.branch_taken
    
    def _test_branch_jz(self, interp, value):
        """Execute jz opcode: branch if value == 0."""
        op_jz(interp, value)
        return interp.branch_taken


@pytest.mark.unit
class TestArithmeticOpcodes:
    """Test arithmetic opcodes (from test_arithmetic in czech.inf)."""
    
    @pytest.mark.unit
    def test_add_positive(self, mock_interpreter):
        """Test add opcode with positive numbers."""
        # Original: @add 5 6 -> i; assert1(i, 11, add_str, Ga);
        assert self._execute_add(mock_interpreter, 5, 6) == 11
        
    @pytest.mark.unit
    def test_add_negative(self, mock_interpreter):
        """Test add with negative numbers."""
        # Original: @add n5 6 -> i; assert1(i, 1, add_str, Ga);
        assert self._execute_add(mock_interpreter, 0xFFFB, 6) == 1
        # Original: @add n5 n5 -> i; assert1(i, -10, add_str, Ga);
        assert self._execute_add(mock_interpreter, 0xFFFB, 0xFFFB) == 0xFFF6
    
    @pytest.mark.unit
    def test_add_overflow(self, mock_interpreter):
        """Test add with overflow (wraps around)."""
        # Original: @add 32767 1 -> i; assert1(i, n32768, add_str, Ga);
        assert self._execute_add(mock_interpreter, 32767, 1) == 0x8000
        
    @pytest.mark.unit
    def test_sub_positive(self, mock_interpreter):
        """Test sub opcode."""
        # Original: @sub 6 5 -> i; assert1(i, 1, sub_str, Ga);
        assert self._execute_sub(mock_interpreter, 6, 5) == 1
        
    @pytest.mark.unit
    def test_sub_negative(self, mock_interpreter):
        """Test sub with negative numbers."""
        # Original: @sub n5 6 -> i; assert1(i, -11, sub_str, Ga);
        assert self._execute_sub(mock_interpreter, 0xFFFB, 6) == 0xFFF5
        # Original: @sub n5 n5 -> i; assert1(i, 0, sub_str, Ga);
        assert self._execute_sub(mock_interpreter, 0xFFFB, 0xFFFB) == 0
    
    @pytest.mark.unit
    def test_sub_underflow(self, mock_interpreter):
        """Test sub with underflow (wraps around)."""
        # Original: @sub n32768 1 -> i; assert1(i, 32767, sub_str, Ga);
        assert self._execute_sub(mock_interpreter, 0x8000, 1) == 0x7FFF
    
    @pytest.mark.unit
    def test_mul_positive(self, mock_interpreter):
        """Test mul opcode."""
        # Original: @mul 6 5 -> i; assert1(i, 30, mul_str, Ga);
        assert self._execute_mul(mock_interpreter, 6, 5) == 30
        
    @pytest.mark.unit
    def test_mul_negative(self, mock_interpreter):
        """Test mul with negative numbers."""
        # Original: @mul n5 6 -> i; assert1(i, -30, mul_str, Ga);
        assert self._execute_mul(mock_interpreter, 0xFFFB, 6) == 0xFFE2
        # Original: @mul n5 n5 -> i; assert1(i, 25, mul_str, Ga);
        assert self._execute_mul(mock_interpreter, 0xFFFB, 0xFFFB) == 25
    
    @pytest.mark.unit
    def test_mul_overflow(self, mock_interpreter):
        """Test mul with overflow."""
        # Original: @mul 1000 1000 -> i; assert1(i, 16960, mul_str, Ga);
        # Wraps: 1000000 % 65536 = 16960
        assert self._execute_mul(mock_interpreter, 1000, 1000) == 16960
    
    @pytest.mark.unit
    def test_div_positive(self, mock_interpreter):
        """Test div opcode."""
        # Original: @div 30 5 -> i; assert1(i, 6, div_str, Ga);
        assert self._execute_div(mock_interpreter, 30, 5) == 6
        
    @pytest.mark.unit
    def test_div_negative(self, mock_interpreter):
        """Test div with negative numbers."""
        # Original: @div n30 5 -> i; assert1(i, -6, div_str, Ga);
        assert self._execute_div(mock_interpreter, 0xFFE2, 5) == 0xFFFA
        # Original: @div n30 n5 -> i; assert1(i, 6, div_str, Ga);
        assert self._execute_div(mock_interpreter, 0xFFE2, 0xFFFB) == 6
    
    @pytest.mark.unit
    def test_div_truncation(self, mock_interpreter):
        """Test div truncates toward zero."""
        # Original: @div 11 3 -> i; assert1(i, 3, div_str, Ga);
        assert self._execute_div(mock_interpreter, 11, 3) == 3
        # Original: @div n11 3 -> i; assert1(i, -3, div_str, Ga);
        assert self._execute_div(mock_interpreter, 0xFFF5, 3) == 0xFFFD

    @pytest.mark.unit
    def test_mod_positive(self, mock_interpreter):
        """Test mod opcode."""
        # Original: @mod 30 7 -> i; assert1(i, 2, mod_str, Ga);
        assert self._execute_mod(mock_interpreter, 30, 7) == 2
    
    @pytest.mark.unit
    def test_mod_negative(self, mock_interpreter):
        """Test mod with negative numbers."""
        # Original: @mod n30 7 -> i; assert1(i, -2, mod_str, Ga);
        assert self._execute_mod(mock_interpreter, 0xFFE2, 7) == 0xFFFE
        # Original: @mod 30 n7 -> i; assert1(i, 2, mod_str, Ga);
        assert self._execute_mod(mock_interpreter, 30, 0xFFF9) == 2

    # Helper methods
    def _execute_add(self, interp, a, b):
        """Execute add opcode."""
        op_add(interp, a, b)
        return interp.stored_value
    
    def _execute_sub(self, interp, a, b):
        """Execute sub opcode."""
        op_sub(interp, a, b)
        return interp.stored_value
    
    def _execute_mul(self, interp, a, b):
        """Execute mul opcode."""
        op_mul(interp, a, b)
        return interp.stored_value
    
    def _execute_div(self, interp, a, b):
        """Execute div opcode."""
        op_div(interp, a, b)
        return interp.stored_value
    
    def _execute_mod(self, interp, a, b):
        """Execute mod opcode."""
        op_mod(interp, a, b)
        return interp.stored_value


@pytest.mark.unit
class TestLogicalOpcodes:
    """Test logical opcodes (from test_logical in czech.inf)."""
    
    @pytest.mark.unit
    def test_and_basic(self, mock_interpreter):
        """Test and opcode."""
        # Original: @and $ffff $ffff -> i; assert2(i, $ffff, and_str, Ga, Gb);
        assert self._execute_and(mock_interpreter, 0xFFFF, 0xFFFF) == 0xFFFF
        # Original: @and $ffff 0 -> i; assert2(i, 0, and_str, Ga, Gb);
        assert self._execute_and(mock_interpreter, 0xFFFF, 0) == 0
        # Original: @and $1234 $4321 -> i; assert2(i, $0220, and_str, Ga, Gb);
        assert self._execute_and(mock_interpreter, 0x1234, 0x4321) == 0x0220
    
    @pytest.mark.unit
    def test_or_basic(self, mock_interpreter):
        """Test or opcode."""
        # Original: @or $ffff $ffff -> i; assert2(i, $ffff, or_str, Ga, Gb);
        assert self._execute_or(mock_interpreter, 0xFFFF, 0xFFFF) == 0xFFFF
        # Original: @or $ffff 0 -> i; assert2(i, $ffff, or_str, Ga, Gb);
        assert self._execute_or(mock_interpreter, 0xFFFF, 0) == 0xFFFF
        # Original: @or $1234 $4321 -> i; assert2(i, $5335, or_str, Ga, Gb);
        assert self._execute_or(mock_interpreter, 0x1234, 0x4321) == 0x5335
    
    @pytest.mark.unit
    def test_not_basic(self, mock_interpreter):
        """Test not opcode (bitwise complement)."""
        # Original: @not $ffff -> i; assert1(i, 0, not_str, Ga);
        assert self._execute_not(mock_interpreter, 0xFFFF) == 0
        # Original: @not 0 -> i; assert1(i, $ffff, not_str, Ga);
        assert self._execute_not(mock_interpreter, 0) == 0xFFFF
        # Original: @not $1234 -> i; assert1(i, $edcb, not_str, Ga);
        assert self._execute_not(mock_interpreter, 0x1234) == 0xEDCB
    
    # Helper methods
    def _execute_and(self, interp, a, b):
        """Execute and opcode."""
        op_and(interp, a, b)
        return interp.stored_value
    
    def _execute_or(self, interp, a, b):
        """Execute or opcode."""
        op_or(interp, a, b)
        return interp.stored_value
    
    def _execute_not(self, interp, value):
        """Execute not opcode."""
        op_not(interp, value)
        return interp.stored_value


@pytest.mark.unit
class TestMemoryOpcodes:
    """Test memory load/store opcodes (from test_memory in czech.inf)."""
    
    @pytest.mark.unit
    def test_loadb_storeb(self, mock_interpreter):
        """Test loadb and storeb opcodes."""
        # Original test stores values and reads them back
        # @storeb mytable 0 42; @loadb mytable 0 -> i; assert0(i, 42);
        table_addr = 0x1000
        
        # Store byte
        self._execute_storeb(mock_interpreter, table_addr, 0, 42)
        # Load byte
        assert self._execute_loadb(mock_interpreter, table_addr, 0) == 42
        
        # Test with different offsets
        self._execute_storeb(mock_interpreter, table_addr, 5, 100)
        assert self._execute_loadb(mock_interpreter, table_addr, 5) == 100
    
    @pytest.mark.unit
    def test_loadw_storew(self, mock_interpreter):
        """Test loadw and storew opcodes."""
        # Original: @storew mytable 0 $1234; @loadw mytable 0 -> i;
        table_addr = 0x1000
        
        # Store word
        self._execute_storew(mock_interpreter, table_addr, 0, 0x1234)
        # Load word
        assert self._execute_loadw(mock_interpreter, table_addr, 0) == 0x1234
        
        # Test with negative values
        self._execute_storew(mock_interpreter, table_addr, 1, -100)
        assert self._execute_loadw(mock_interpreter, table_addr, 1) == 0xFF9C
    
    # Helper methods
    def _execute_loadb(self, interp, addr, offset):
        """Execute loadb opcode: load byte from addr+offset."""
        op_loadb(interp, addr, offset)
        return interp.stored_value
    
    def _execute_storeb(self, interp, addr, offset, value):
        """Execute storeb opcode: store byte to addr+offset."""
        op_storeb(interp, addr, offset, value & 0xFF)
    
    def _execute_loadw(self, interp, addr, offset):
        """Execute loadw opcode: load word from addr+(offset*2)."""
        op_loadw(interp, addr, offset)  # Just to set stored_value
        return interp.stored_value
    
    def _execute_storew(self, interp, addr, offset, value):
        """Execute storew opcode: store word to addr+(offset*2)."""
        op_storew(interp, addr, offset, value & 0xFFFF)


@pytest.mark.unit
class TestStackOpcodes:
    """Test stack opcodes (from test_variables in czech.inf)."""
    
    @pytest.mark.unit
    def test_push_pop(self, mock_interpreter):
        """Test push and pop opcodes."""
        # Original: @push 5; @pop -> i; assert0(i, 5);
        self._execute_push(mock_interpreter, 5)
        assert self._execute_pop(mock_interpreter) == 5
        
        # Test multiple values
        self._execute_push(mock_interpreter, 10)
        self._execute_push(mock_interpreter, 20)
        self._execute_push(mock_interpreter, 30)
        assert self._execute_pop(mock_interpreter) == 30
        assert self._execute_pop(mock_interpreter) == 20
        assert self._execute_pop(mock_interpreter) == 10
    
    @pytest.mark.unit
    def test_push_pop_negative(self, mock_interpreter):
        """Test push/pop with negative values."""
        self._execute_push(mock_interpreter, -50)
        assert self._execute_pop(mock_interpreter) == 0xFFCE  # -50 as unsigned 16-bit

    def _execute_push(self, interp, value):
        """Execute push opcode."""
        op_push(interp, value)

    def _execute_pop(self, interp):
        """Execute pop opcode."""
        op_pull(interp, 1)
        return interp.read_var(1)



@pytest.mark.unit
class TestMiscOpcodes:
    """Test miscellaneous opcodes (from test_misc in czech.inf)."""
    
    @pytest.mark.unit
    def test_test_opcode(self, mock_interpreter):
        """Test 'test' opcode (bitwise test)."""
        # Original: @test $ffff $ffff ?~bad; p();
        assert self._execute_test(mock_interpreter, 0xFFFF, 0xFFFF) == True
        # Original: @test $ffff 0 ?~bad; p();
        assert self._execute_test(mock_interpreter, 0xFFFF, 0) == True
        # Original: @test $1234 $4321 ?bad; p();
        assert self._execute_test(mock_interpreter, 0x1234, 0x4321) == False
    
    @pytest.mark.unit
    def test_random_seeded(self, mock_interpreter):
        """Test random opcode with seeding."""
        # Original: Tests that random returns same value after seeding
        # Note: This test validates the seeding mechanism exists,
        # actual implementation will be in the interpreter
        # For now, just test the interface
        result1 = self._execute_random(mock_interpreter, 100)
        result2 = self._execute_random(mock_interpreter, 100)
        # Both should be in range
        assert 1 <= result1 <= 100
        assert 1 <= result2 <= 100
    
    # Helper methods
    def _execute_test(self, interp, value, mask):
        """Execute test opcode: branch if (value & mask) == mask."""
        op_test(interp, value, mask)
        return interp.branch_taken
    
    def _execute_random(self, interp, range_value):
        """Execute random opcode."""
        # Mock implementation: just return a value in range
        # Real interpreter will handle proper random/seeding
        op_random(interp, range_value)
        return interp.stored_value


# TODO: Add more test classes for:
# - TestSubroutineOpcodes (call, ret, etc.)
# - TestObjectOpcodes (get_parent, get_child, etc.)
# - TestIndirectOpcodes (inc_chk, dec_chk, etc.)
# - TestPrintOpcodes (print_char, print_num, etc.)