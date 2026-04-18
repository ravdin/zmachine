"""
Z-Machine Logging Configuration

Central logging setup for the entire interpreter.
"""
import logging
import sys
from typing import Optional
from enum import IntEnum


class LogLevel(IntEnum):
    """Custom log levels for Z-Machine."""
    OPCODE = 5      # Ultra-verbose opcode execution
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


# Register custom OPCODE level
logging.addLevelName(LogLevel.OPCODE, "OPCODE")


class ColoredFormatter(logging.Formatter):
    """Add colors to console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'OPCODE': '\033[90m',     # Gray
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )
        result = super().format(record)
        record.levelname = levelname
        return result


def setup_logging(
    level: int = logging.WARNING,
    log_file: Optional[str] = None,
    opcode_log_file: Optional[str] = None,
    log_memory: bool = False
):
    """
    Configure logging for Z-Machine interpreter.
    
    Args:
        level: Base logging level for general logs (console/file)
        log_file: Optional file path for general log output
        opcode_log_file: Optional file path for opcode log output
        log_memory: Enable memory access logging
    """
    root_logger = logging.getLogger('zmachine')
    root_logger.setLevel(LogLevel.OPCODE)
    root_logger.handlers.clear()
    
    # File handler (no colors)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(LogLevel.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        def file_filter(record):
            if record.name == 'zmachine.opcodes':
                return False
            if record.name == 'zmachine.memory':
                return True
            return record.levelno >= level
        file_handler.addFilter(file_filter)
        root_logger.addHandler(file_handler)
    else:
        # Console handler with colors
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)  # ← Filter at handler level
        console.setFormatter(ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))
        # Don't show opcodes or memory on console (too verbose)
        console.addFilter(lambda record: record.name != 'zmachine.opcodes')
        console.addFilter(lambda record: record.name != 'zmachine.memory')
        root_logger.addHandler(console)

    # Separate opcode trace file (if specified)
    if opcode_log_file:
        opcode_handler = logging.FileHandler(opcode_log_file, mode='w')
        opcode_handler.setLevel(LogLevel.OPCODE)  # ← Accept OPCODE level
        opcode_handler.setFormatter(logging.Formatter(
            '%(message)s'  # Minimal formatting for opcode trace
        ))
        # ONLY opcodes go here
        opcode_handler.addFilter(lambda record: record.name == 'zmachine.opcodes')
        root_logger.addHandler(opcode_handler)
        
        # Enable opcode logger
        logging.getLogger('zmachine.opcodes').setLevel(LogLevel.OPCODE)
    else:
        logging.getLogger('zmachine.opcodes').setLevel(logging.INFO)
    
    if log_memory:
        logging.getLogger('zmachine.memory').setLevel(logging.DEBUG)
    else:
        logging.getLogger('zmachine.memory').setLevel(logging.WARNING)


# Subsystem loggers
opcodes_logger = logging.getLogger('zmachine.opcodes')
memory_logger = logging.getLogger('zmachine.memory')
screen_logger = logging.getLogger('zmachine.screen')
output_logger = logging.getLogger('zmachine.output')
quetzal_logger = logging.getLogger('zmachine.quetzal')
interpreter_logger = logging.getLogger('zmachine.interpreter')
error_logger = logging.getLogger('zmachine.error')
call_stack_logger = logging.getLogger('zmachine.call_stack')