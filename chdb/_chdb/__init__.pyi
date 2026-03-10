import enum
from . import _sqltypes as _sqltypes

class NullHandling(enum.Enum):
    SKIP: int    # Do not call UDF for NULL inputs, return NULL directly (default)
    PASS: int    # Convert NULL to None and call the UDF

class ExceptionHandling(enum.Enum):
    PROPAGATE: int  # Raise the exception (default)
    IGNORE: int     # Return NULL for the row and continue
