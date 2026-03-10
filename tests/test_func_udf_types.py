#!python3

import unittest
import datetime
import chdb
from chdb import func
from chdb.sqltypes import (
    BOOL, INT8, INT16, INT32, INT64, INT128, INT256,
    UINT8, UINT16, UINT32, UINT64, UINT128, UINT256,
    FLOAT32, FLOAT64, STRING, DATE, DATE32, DATETIME, DATETIME64,
)
from chdb.session import Session


class TestBoolUDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_bool_return_explicit_arg_types(self):
        def is_positive(x):
            return x > 0

        chdb.create_function("is_positive", is_positive, arg_types=[INT64], return_type=BOOL)
        ret = self.session.query("SELECT is_positive(5)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT is_positive(-3)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("is_positive")

    def test_create_function_bool_lambda_explicit(self):
        chdb.create_function("is_even", lambda x: x % 2 == 0, arg_types=[INT64], return_type=BOOL)
        ret = self.session.query("SELECT is_even(4)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT is_even(3)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("is_even")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_bool_return_no_arg_types(self):
        def is_long(s):
            return len(s) > 3

        chdb.create_function("is_long", is_long, return_type=BOOL)
        ret = self.session.query("SELECT is_long('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT is_long('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("is_long")

    # ── create_function: infer return_type from annotation ──

    def test_create_function_bool_infer_return_from_annotation(self):
        def is_negative(x) -> bool:
            return x < 0

        chdb.create_function("is_negative", is_negative)
        ret = self.session.query("SELECT is_negative(-1)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT is_negative(1)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("is_negative")

    # ── create_function: infer both arg_types and return_type from annotations ──

    def test_create_function_bool_infer_all_from_annotations(self):
        def both_positive(a: int, b: int) -> bool:
            return a > 0 and b > 0

        chdb.create_function("both_positive", both_positive)
        ret = self.session.query("SELECT both_positive(1, 2)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT both_positive(1, -2)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("both_positive")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def is_big(x: int) -> bool:
            return x > 100

        chdb.create_function("is_big", is_big, arg_types=[INT64], return_type=BOOL)
        ret = self.session.query("SELECT is_big(200)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT is_big(50)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("is_big")

    # ── create_function: string type names ──

    def test_create_function_bool_string_types(self):
        chdb.create_function("str_eq", lambda a, b: a == b, arg_types=["String", "String"], return_type="Bool")
        ret = self.session.query("SELECT str_eq('abc', 'abc')", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT str_eq('abc', 'xyz')", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("str_eq")

    # ── create_function: bool as arg_type ──

    def test_create_function_bool_as_arg_type(self):
        def negate(x):
            return not x

        chdb.create_function("negate", negate, arg_types=[BOOL], return_type=BOOL)
        ret = self.session.query("SELECT negate(true)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        ret = self.session.query("SELECT negate(false)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        chdb.drop_function("negate")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return True

        with self.assertRaises(RuntimeError):
            chdb.create_function("dummy", dummy, arg_types=[INT64], return_type=BOOL)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        def check_int(x):
            return x > 0

        chdb.create_function("check_int", check_int, arg_types=[INT64], return_type=BOOL)
        with self.assertRaises(Exception):
            self.session.query("SELECT check_int('hello')", "CSV")
        chdb.drop_function("check_int")

    # ── create_function: compatible arg type (e.g. UInt8 → Int64) ──

    def test_create_function_compatible_arg_type(self):
        def is_one(x):
            return x == 1

        chdb.create_function("is_one", is_one, arg_types=[INT64], return_type=BOOL)
        ret = self.session.query("SELECT is_one(toUInt8(1))", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        chdb.drop_function("is_one")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_bool_explicit_all(self):
        @func(arg_types=[INT64], return_type=BOOL)
        def dec_is_positive(x):
            return x > 0

        ret = self.session.query("SELECT dec_is_positive(10)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT dec_is_positive(-10)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("dec_is_positive")

    def test_func_decorator_bool_return_only(self):
        @func(return_type=BOOL)
        def dec_is_zero(x):
            return x == 0

        ret = self.session.query("SELECT dec_is_zero(0)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT dec_is_zero(1)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("dec_is_zero")

    # ── @func decorator: infer all from annotations ──

    def test_func_decorator_bool_infer_all(self):
        @func()
        def dec_both_true(a: bool, b: bool) -> bool:
            return a and b

        ret = self.session.query("SELECT dec_both_true(true, true)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT dec_both_true(true, false)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("dec_both_true")

    # ── @func decorator: infer return_type only ──

    def test_func_decorator_bool_infer_return(self):
        @func(arg_types=[INT64, INT64])
        def dec_gt(a, b) -> bool:
            return a > b

        ret = self.session.query("SELECT dec_gt(5, 3)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        ret = self.session.query("SELECT dec_gt(1, 3)", "CSV")
        self.assertEqual(str(ret).strip(), "false")
        chdb.drop_function("dec_gt")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_bool_udf(self):
        chdb.create_function("to_drop", lambda x: x > 0, arg_types=[INT64], return_type=BOOL)
        ret = self.session.query("SELECT to_drop(1)", "CSV")
        self.assertEqual(str(ret).strip(), "true")
        chdb.drop_function("to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT to_drop(1)", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=BOOL)
        def py_callable(x):
            return x > 0

        self.assertTrue(py_callable(5))
        self.assertFalse(py_callable(-1))
        chdb.drop_function("py_callable")


# ═══════════════════════════════════════════════════════════════════
# Signed Integer Types
# ═══════════════════════════════════════════════════════════════════


class TestInt8UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int8_return_explicit_arg_types(self):
        def add_i8(x, y):
            return x + y

        chdb.create_function("i8_add", add_i8, arg_types=[INT8, INT8], return_type=INT8)
        ret = self.session.query("SELECT i8_add(toInt8(10), toInt8(20))", "CSV")
        self.assertEqual(str(ret).strip(), "30")
        ret = self.session.query("SELECT i8_add(toInt8(-5), toInt8(3))", "CSV")
        self.assertEqual(str(ret).strip(), "-2")
        chdb.drop_function("i8_add")

    def test_create_function_int8_lambda_explicit(self):
        chdb.create_function("i8_double", lambda x: x * 2, arg_types=[INT8], return_type=INT8)
        ret = self.session.query("SELECT i8_double(toInt8(10))", "CSV")
        self.assertEqual(str(ret).strip(), "20")
        ret = self.session.query("SELECT i8_double(toInt8(-5))", "CSV")
        self.assertEqual(str(ret).strip(), "-10")
        chdb.drop_function("i8_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int8_return_no_arg_types(self):
        def str_len_i8(s):
            return len(s)

        chdb.create_function("i8_strlen", str_len_i8, return_type=INT8)
        ret = self.session.query("SELECT i8_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i8_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i8_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i8(x: int) -> int:
            return x + 1

        chdb.create_function("i8_inc_override", inc_i8, arg_types=[INT8], return_type=INT8)
        ret = self.session.query("SELECT i8_inc_override(toInt8(10))", "CSV")
        self.assertEqual(str(ret).strip(), "11")
        ret = self.session.query("SELECT i8_inc_override(toInt8(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i8_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int8_string_types(self):
        chdb.create_function("i8_inc_str", lambda x: x + 1, arg_types=["Int8"], return_type="Int8")
        ret = self.session.query("SELECT i8_inc_str(toInt8(9))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        ret = self.session.query("SELECT i8_inc_str(toInt8(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i8_inc_str")

    # ── create_function: int8 as arg_type ──

    def test_create_function_int8_as_arg_type(self):
        def neg_i8(x):
            return -x

        chdb.create_function("i8_neg", neg_i8, arg_types=[INT8], return_type=INT8)
        ret = self.session.query("SELECT i8_neg(toInt8(42))", "CSV")
        self.assertEqual(str(ret).strip(), "-42")
        ret = self.session.query("SELECT i8_neg(toInt8(-10))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        chdb.drop_function("i8_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i8_dummy", dummy, arg_types=[INT8], return_type=INT8)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i8_check", lambda x: x, arg_types=[INT8], return_type=INT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_check('hello')", "CSV")
        chdb.drop_function("i8_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i8_compat", lambda x: x + 1, arg_types=[INT16], return_type=INT8)
        ret = self.session.query("SELECT i8_compat(toInt8(5))", "CSV")
        self.assertEqual(str(ret).strip(), "6")
        chdb.drop_function("i8_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int8_explicit_all(self):
        @func(arg_types=[INT8, INT8], return_type=INT8)
        def dec_i8_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i8_add(toInt8(3), toInt8(4))", "CSV")
        self.assertEqual(str(ret).strip(), "7")
        ret = self.session.query("SELECT dec_i8_add(toInt8(-3), toInt8(4))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i8_add")

    def test_func_decorator_int8_return_only(self):
        @func(return_type=INT8)
        def dec_i8_one(x):
            return 1

        ret = self.session.query("SELECT dec_i8_one(toInt8(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i8_one(toInt8(99))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i8_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("i8_overflow", lambda x: 200, arg_types=[INT8], return_type=INT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_overflow(toInt8(1))", "CSV")
        chdb.drop_function("i8_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("i8_underflow", lambda x: -200, arg_types=[INT8], return_type=INT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_underflow(toInt8(1))", "CSV")
        chdb.drop_function("i8_underflow")

    # ── input arg out of range (larger type passed to Int8 arg_type) ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("i8_input_ovf", lambda x: x, arg_types=[INT8], return_type=INT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_input_ovf(toInt16(200))", "CSV")
        chdb.drop_function("i8_input_ovf")

    def test_input_arg_underflow_raises(self):
        chdb.create_function("i8_input_udf", lambda x: x, arg_types=[INT8], return_type=INT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_input_udf(toInt16(-200))", "CSV")
        chdb.drop_function("i8_input_udf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int8_udf(self):
        chdb.create_function("i8_to_drop", lambda x: x + 1, arg_types=[INT8], return_type=INT8)
        ret = self.session.query("SELECT i8_to_drop(toInt8(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i8_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i8_to_drop(toInt8(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT8)
        def i8_py_callable(x):
            return x + 1

        self.assertEqual(i8_py_callable(5), 6)
        self.assertEqual(i8_py_callable(-1), 0)
        chdb.drop_function("i8_py_callable")


class TestInt16UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int16_return_explicit_arg_types(self):
        def add_i16(x, y):
            return x + y

        chdb.create_function("i16_add", add_i16, arg_types=[INT16, INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_add(toInt16(1000), toInt16(2000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000")
        ret = self.session.query("SELECT i16_add(toInt16(-500), toInt16(300))", "CSV")
        self.assertEqual(str(ret).strip(), "-200")
        chdb.drop_function("i16_add")

    def test_create_function_int16_lambda_explicit(self):
        chdb.create_function("i16_double", lambda x: x * 2, arg_types=[INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_double(toInt16(100))", "CSV")
        self.assertEqual(str(ret).strip(), "200")
        ret = self.session.query("SELECT i16_double(toInt16(-50))", "CSV")
        self.assertEqual(str(ret).strip(), "-100")
        chdb.drop_function("i16_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int16_return_no_arg_types(self):
        def str_len_i16(s):
            return len(s)

        chdb.create_function("i16_strlen", str_len_i16, return_type=INT16)
        ret = self.session.query("SELECT i16_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i16_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i16_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i16(x: int) -> int:
            return x + 1

        chdb.create_function("i16_inc_override", inc_i16, arg_types=[INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_inc_override(toInt16(100))", "CSV")
        self.assertEqual(str(ret).strip(), "101")
        ret = self.session.query("SELECT i16_inc_override(toInt16(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i16_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int16_string_types(self):
        chdb.create_function("i16_inc_str", lambda x: x + 1, arg_types=["Int16"], return_type="Int16")
        ret = self.session.query("SELECT i16_inc_str(toInt16(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT i16_inc_str(toInt16(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i16_inc_str")

    # ── create_function: int16 as arg_type ──

    def test_create_function_int16_as_arg_type(self):
        def neg_i16(x):
            return -x

        chdb.create_function("i16_neg", neg_i16, arg_types=[INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_neg(toInt16(1000))", "CSV")
        self.assertEqual(str(ret).strip(), "-1000")
        ret = self.session.query("SELECT i16_neg(toInt16(-500))", "CSV")
        self.assertEqual(str(ret).strip(), "500")
        chdb.drop_function("i16_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i16_dummy", dummy, arg_types=[INT16], return_type=INT16)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i16_check", lambda x: x, arg_types=[INT16], return_type=INT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_check('hello')", "CSV")
        chdb.drop_function("i16_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i16_compat", lambda x: x + 1, arg_types=[INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_compat(toInt8(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("i16_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int16_explicit_all(self):
        @func(arg_types=[INT16, INT16], return_type=INT16)
        def dec_i16_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i16_add(toInt16(300), toInt16(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_i16_add(toInt16(-300), toInt16(400))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        chdb.drop_function("dec_i16_add")

    def test_func_decorator_int16_return_only(self):
        @func(return_type=INT16)
        def dec_i16_one(x):
            return 1

        ret = self.session.query("SELECT dec_i16_one(toInt16(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i16_one(toInt16(9999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i16_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("i16_overflow", lambda x: 40000, arg_types=[INT16], return_type=INT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_overflow(toInt16(1))", "CSV")
        chdb.drop_function("i16_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("i16_underflow", lambda x: -40000, arg_types=[INT16], return_type=INT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_underflow(toInt16(1))", "CSV")
        chdb.drop_function("i16_underflow")

    # ── input arg out of range (larger type passed to Int16 arg_type) ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("i16_input_ovf", lambda x: x, arg_types=[INT16], return_type=INT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_input_ovf(toInt32(40000))", "CSV")
        chdb.drop_function("i16_input_ovf")

    def test_input_arg_underflow_raises(self):
        chdb.create_function("i16_input_udf", lambda x: x, arg_types=[INT16], return_type=INT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_input_udf(toInt32(-40000))", "CSV")
        chdb.drop_function("i16_input_udf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int16_udf(self):
        chdb.create_function("i16_to_drop", lambda x: x + 1, arg_types=[INT16], return_type=INT16)
        ret = self.session.query("SELECT i16_to_drop(toInt16(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i16_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i16_to_drop(toInt16(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT16)
        def i16_py_callable(x):
            return x + 1

        self.assertEqual(i16_py_callable(5), 6)
        self.assertEqual(i16_py_callable(-1), 0)
        chdb.drop_function("i16_py_callable")


class TestInt32UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int32_return_explicit_arg_types(self):
        def add_i32(x, y):
            return x + y

        chdb.create_function("i32_add", add_i32, arg_types=[INT32, INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_add(toInt32(100000), toInt32(200000))", "CSV")
        self.assertEqual(str(ret).strip(), "300000")
        ret = self.session.query("SELECT i32_add(toInt32(-50000), toInt32(30000))", "CSV")
        self.assertEqual(str(ret).strip(), "-20000")
        chdb.drop_function("i32_add")

    def test_create_function_int32_lambda_explicit(self):
        chdb.create_function("i32_double", lambda x: x * 2, arg_types=[INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_double(toInt32(50000))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT i32_double(toInt32(-25000))", "CSV")
        self.assertEqual(str(ret).strip(), "-50000")
        chdb.drop_function("i32_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int32_return_no_arg_types(self):
        def str_len_i32(s):
            return len(s)

        chdb.create_function("i32_strlen", str_len_i32, return_type=INT32)
        ret = self.session.query("SELECT i32_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i32_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i32_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i32(x: int) -> int:
            return x + 1

        chdb.create_function("i32_inc_override", inc_i32, arg_types=[INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_inc_override(toInt32(99999))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT i32_inc_override(toInt32(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i32_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int32_string_types(self):
        chdb.create_function("i32_inc_str", lambda x: x + 1, arg_types=["Int32"], return_type="Int32")
        ret = self.session.query("SELECT i32_inc_str(toInt32(99999))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT i32_inc_str(toInt32(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i32_inc_str")

    # ── create_function: int32 as arg_type ──

    def test_create_function_int32_as_arg_type(self):
        def neg_i32(x):
            return -x

        chdb.create_function("i32_neg", neg_i32, arg_types=[INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_neg(toInt32(12345))", "CSV")
        self.assertEqual(str(ret).strip(), "-12345")
        ret = self.session.query("SELECT i32_neg(toInt32(-67890))", "CSV")
        self.assertEqual(str(ret).strip(), "67890")
        chdb.drop_function("i32_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i32_dummy", dummy, arg_types=[INT32], return_type=INT32)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i32_check", lambda x: x, arg_types=[INT32], return_type=INT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_check('hello')", "CSV")
        chdb.drop_function("i32_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i32_compat", lambda x: x + 1, arg_types=[INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_compat(toInt16(1000))", "CSV")
        self.assertEqual(str(ret).strip(), "1001")
        chdb.drop_function("i32_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int32_explicit_all(self):
        @func(arg_types=[INT32, INT32], return_type=INT32)
        def dec_i32_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i32_add(toInt32(30000), toInt32(40000))", "CSV")
        self.assertEqual(str(ret).strip(), "70000")
        ret = self.session.query("SELECT dec_i32_add(toInt32(-30000), toInt32(40000))", "CSV")
        self.assertEqual(str(ret).strip(), "10000")
        chdb.drop_function("dec_i32_add")

    def test_func_decorator_int32_return_only(self):
        @func(return_type=INT32)
        def dec_i32_one(x):
            return 1

        ret = self.session.query("SELECT dec_i32_one(toInt32(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i32_one(toInt32(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i32_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("i32_overflow", lambda x: 2200000000, arg_types=[INT32], return_type=INT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_overflow(toInt32(1))", "CSV")
        chdb.drop_function("i32_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("i32_underflow", lambda x: -2200000000, arg_types=[INT32], return_type=INT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_underflow(toInt32(1))", "CSV")
        chdb.drop_function("i32_underflow")

    # ── input arg out of range (larger type passed to Int32 arg_type) ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("i32_input_ovf", lambda x: x, arg_types=[INT32], return_type=INT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_input_ovf(toInt64(2200000000))", "CSV")
        chdb.drop_function("i32_input_ovf")

    def test_input_arg_underflow_raises(self):
        chdb.create_function("i32_input_udf", lambda x: x, arg_types=[INT32], return_type=INT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_input_udf(toInt64(-2200000000))", "CSV")
        chdb.drop_function("i32_input_udf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int32_udf(self):
        chdb.create_function("i32_to_drop", lambda x: x + 1, arg_types=[INT32], return_type=INT32)
        ret = self.session.query("SELECT i32_to_drop(toInt32(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i32_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i32_to_drop(toInt32(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT32)
        def i32_py_callable(x):
            return x + 1

        self.assertEqual(i32_py_callable(5), 6)
        self.assertEqual(i32_py_callable(-1), 0)
        chdb.drop_function("i32_py_callable")


class TestInt64UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int64_return_explicit_arg_types(self):
        def add_i64(x, y):
            return x + y

        chdb.create_function("i64_add", add_i64, arg_types=[INT64, INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_add(toInt64(1000000), toInt64(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        ret = self.session.query("SELECT i64_add(toInt64(-500000), toInt64(300000))", "CSV")
        self.assertEqual(str(ret).strip(), "-200000")
        chdb.drop_function("i64_add")

    def test_create_function_int64_lambda_explicit(self):
        chdb.create_function("i64_double", lambda x: x * 2, arg_types=[INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_double(toInt64(500000))", "CSV")
        self.assertEqual(str(ret).strip(), "1000000")
        ret = self.session.query("SELECT i64_double(toInt64(-250000))", "CSV")
        self.assertEqual(str(ret).strip(), "-500000")
        chdb.drop_function("i64_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int64_return_no_arg_types(self):
        def str_len_i64(s):
            return len(s)

        chdb.create_function("i64_strlen", str_len_i64, return_type=INT64)
        ret = self.session.query("SELECT i64_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i64_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i64_strlen")

    # ── create_function: infer return_type from annotation ──

    def test_create_function_int64_infer_return_from_annotation(self):
        def triple_i64(x) -> int:
            return x * 3

        chdb.create_function("i64_triple_infer", triple_i64)
        ret = self.session.query("SELECT i64_triple_infer(toInt64(5))", "CSV")
        self.assertEqual(str(ret).strip(), "15")
        ret = self.session.query("SELECT i64_triple_infer(toInt64(-3))", "CSV")
        self.assertEqual(str(ret).strip(), "-9")
        chdb.drop_function("i64_triple_infer")

    # ── create_function: infer both arg_types and return_type from annotations ──

    def test_create_function_int64_infer_all_from_annotations(self):
        def add_annotated(a: int, b: int) -> int:
            return a + b

        chdb.create_function("i64_annotated", add_annotated)
        ret = self.session.query("SELECT i64_annotated(toInt64(10), toInt64(20))", "CSV")
        self.assertEqual(str(ret).strip(), "30")
        ret = self.session.query("SELECT i64_annotated(toInt64(-10), toInt64(20))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        chdb.drop_function("i64_annotated")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i64(x: float) -> float:
            return x + 1

        chdb.create_function("i64_inc_override", inc_i64, arg_types=[INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_inc_override(toInt64(99999))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT i64_inc_override(toInt64(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i64_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int64_string_types(self):
        chdb.create_function("i64_inc_str", lambda x: x + 1, arg_types=["Int64"], return_type="Int64")
        ret = self.session.query("SELECT i64_inc_str(toInt64(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000000")
        ret = self.session.query("SELECT i64_inc_str(toInt64(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i64_inc_str")

    # ── create_function: int64 as arg_type ──

    def test_create_function_int64_as_arg_type(self):
        def neg_i64(x):
            return -x

        chdb.create_function("i64_neg", neg_i64, arg_types=[INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_neg(toInt64(123456))", "CSV")
        self.assertEqual(str(ret).strip(), "-123456")
        ret = self.session.query("SELECT i64_neg(toInt64(-789012))", "CSV")
        self.assertEqual(str(ret).strip(), "789012")
        chdb.drop_function("i64_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i64_dummy", dummy, arg_types=[INT64], return_type=INT64)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i64_check", lambda x: x, arg_types=[INT64], return_type=INT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT i64_check('hello')", "CSV")
        chdb.drop_function("i64_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i64_compat", lambda x: x + 1, arg_types=[INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_compat(toInt32(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("i64_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int64_explicit_all(self):
        @func(arg_types=[INT64, INT64], return_type=INT64)
        def dec_i64_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i64_add(toInt64(300000), toInt64(400000))", "CSV")
        self.assertEqual(str(ret).strip(), "700000")
        ret = self.session.query("SELECT dec_i64_add(toInt64(-300000), toInt64(400000))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        chdb.drop_function("dec_i64_add")

    def test_func_decorator_int64_return_only(self):
        @func(return_type=INT64)
        def dec_i64_one(x):
            return 1

        ret = self.session.query("SELECT dec_i64_one(toInt64(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i64_one(toInt64(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i64_one")

    # ── @func decorator: infer all from annotations ──

    def test_func_decorator_int64_infer_all(self):
        @func()
        def dec_i64_sum(a: int, b: int) -> int:
            return a + b

        ret = self.session.query("SELECT dec_i64_sum(toInt64(10), toInt64(20))", "CSV")
        self.assertEqual(str(ret).strip(), "30")
        ret = self.session.query("SELECT dec_i64_sum(toInt64(-10), toInt64(20))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        chdb.drop_function("dec_i64_sum")

    # ── @func decorator: infer return_type only ──

    def test_func_decorator_int64_infer_return(self):
        @func(arg_types=[INT64, INT64])
        def dec_i64_diff(a, b) -> int:
            return a - b

        ret = self.session.query("SELECT dec_i64_diff(toInt64(50), toInt64(30))", "CSV")
        self.assertEqual(str(ret).strip(), "20")
        ret = self.session.query("SELECT dec_i64_diff(toInt64(10), toInt64(30))", "CSV")
        self.assertEqual(str(ret).strip(), "-20")
        chdb.drop_function("dec_i64_diff")

    # ── return value out of range ──
    # Int64 range is [-9223372036854775808, 9223372036854775807]
    # Python int has no overflow, but PyLong_AsLongLongAndOverflow will detect it

    def test_return_value_overflow_raises(self):
        chdb.create_function("i64_overflow", lambda x: 2**63, arg_types=[INT64], return_type=INT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT i64_overflow(toInt64(1))", "CSV")
        chdb.drop_function("i64_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("i64_underflow", lambda x: -(2**63) - 1, arg_types=[INT64], return_type=INT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT i64_underflow(toInt64(1))", "CSV")
        chdb.drop_function("i64_underflow")

    # ── input arg out of range (larger type passed to Int64 arg_type) ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("i64_input_ovf", lambda x: x, arg_types=[INT64], return_type=INT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT i64_input_ovf(toUInt64(9223372036854775808))", "CSV")
        chdb.drop_function("i64_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int64_udf(self):
        chdb.create_function("i64_to_drop", lambda x: x + 1, arg_types=[INT64], return_type=INT64)
        ret = self.session.query("SELECT i64_to_drop(toInt64(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i64_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i64_to_drop(toInt64(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT64)
        def i64_py_callable(x):
            return x + 1

        self.assertEqual(i64_py_callable(5), 6)
        self.assertEqual(i64_py_callable(-1), 0)
        chdb.drop_function("i64_py_callable")


class TestInt128UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int128_return_explicit_arg_types(self):
        def add_i128(x, y):
            return x + y

        chdb.create_function("i128_add", add_i128, arg_types=[INT128, INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_add(toInt128(100), toInt128(200))", "CSV")
        self.assertEqual(str(ret).strip(), "300")
        ret = self.session.query("SELECT i128_add(toInt128(-50), toInt128(30))", "CSV")
        self.assertEqual(str(ret).strip(), "-20")
        chdb.drop_function("i128_add")

    def test_create_function_int128_lambda_explicit(self):
        chdb.create_function("i128_double", lambda x: x * 2, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_double(toInt128(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT i128_double(toInt128(-250))", "CSV")
        self.assertEqual(str(ret).strip(), "-500")
        chdb.drop_function("i128_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int128_return_no_arg_types(self):
        def str_len_i128(s):
            return len(s)

        chdb.create_function("i128_strlen", str_len_i128, return_type=INT128)
        ret = self.session.query("SELECT i128_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i128_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i128_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i128(x: int) -> int:
            return x + 1

        chdb.create_function("i128_inc_override", inc_i128, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_inc_override(toInt128(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT i128_inc_override(toInt128(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i128_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int128_string_types(self):
        chdb.create_function("i128_inc_str", lambda x: x + 1, arg_types=["Int128"], return_type="Int128")
        ret = self.session.query("SELECT i128_inc_str(toInt128(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT i128_inc_str(toInt128(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i128_inc_str")

    # ── create_function: int128 as arg_type ──

    def test_create_function_int128_as_arg_type(self):
        def neg_i128(x):
            return -x

        chdb.create_function("i128_neg", neg_i128, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_neg(toInt128(12345))", "CSV")
        self.assertEqual(str(ret).strip(), "-12345")
        ret = self.session.query("SELECT i128_neg(toInt128(-67890))", "CSV")
        self.assertEqual(str(ret).strip(), "67890")
        chdb.drop_function("i128_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i128_dummy", dummy, arg_types=[INT128], return_type=INT128)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i128_check", lambda x: x, arg_types=[INT128], return_type=INT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT i128_check('hello')", "CSV")
        chdb.drop_function("i128_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i128_compat", lambda x: x + 1, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_compat(toInt64(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("i128_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int128_explicit_all(self):
        @func(arg_types=[INT128, INT128], return_type=INT128)
        def dec_i128_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i128_add(toInt128(300), toInt128(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_i128_add(toInt128(-300), toInt128(400))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        chdb.drop_function("dec_i128_add")

    def test_func_decorator_int128_return_only(self):
        @func(return_type=INT128)
        def dec_i128_one(x):
            return 1

        ret = self.session.query("SELECT dec_i128_one(toInt128(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i128_one(toInt128(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i128_one")

    # ── return value out of range (wide integer overflow not detected, wraps silently) ──

    def test_return_value_overflow_wraps(self):
        chdb.create_function("i128_overflow", lambda x: 2**127, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_overflow(toInt128(1))", "CSV")
        self.assertEqual(str(ret).strip(), str(-(2**127)))
        chdb.drop_function("i128_overflow")

    def test_return_value_underflow_wraps(self):
        chdb.create_function("i128_underflow", lambda x: -(2**127) - 1, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_underflow(toInt128(1))", "CSV")
        self.assertEqual(str(ret).strip(), str(2**127 - 1))
        chdb.drop_function("i128_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("i128_input_ovf", lambda x: x, arg_types=[INT128], return_type=INT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT i128_input_ovf(toInt256(170141183460469231731687303715884105728))", "CSV")
        chdb.drop_function("i128_input_ovf")

    def test_input_arg_underflow_raises(self):
        chdb.create_function("i128_input_udf", lambda x: x, arg_types=[INT128], return_type=INT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT i128_input_udf(toInt256(-170141183460469231731687303715884105729))", "CSV")
        chdb.drop_function("i128_input_udf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int128_udf(self):
        chdb.create_function("i128_to_drop", lambda x: x + 1, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_to_drop(toInt128(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i128_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i128_to_drop(toInt128(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT128)
        def i128_py_callable(x):
            return x + 1

        self.assertEqual(i128_py_callable(5), 6)
        self.assertEqual(i128_py_callable(-1), 0)
        chdb.drop_function("i128_py_callable")

    # ── large integers beyond Int64 range ──

    def test_large_integer_beyond_int64_range(self):
        chdb.create_function("i128_big_add", lambda x, y: x + y, arg_types=[INT128, INT128], return_type=INT128)
        ret = self.session.query(
            "SELECT i128_big_add(toInt128('10000000000000000000'), toInt128('20000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "30000000000000000000")
        chdb.drop_function("i128_big_add")

    def test_large_negative_integer_beyond_int64_range(self):
        chdb.create_function("i128_big_neg", lambda x: -x, arg_types=[INT128], return_type=INT128)
        ret = self.session.query("SELECT i128_big_neg(toInt128('10000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "-10000000000000000000")
        ret = self.session.query("SELECT i128_big_neg(toInt128('-10000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "10000000000000000000")
        chdb.drop_function("i128_big_neg")


class TestInt256UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_int256_return_explicit_arg_types(self):
        def add_i256(x, y):
            return x + y

        chdb.create_function("i256_add", add_i256, arg_types=[INT256, INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_add(toInt256(100), toInt256(200))", "CSV")
        self.assertEqual(str(ret).strip(), "300")
        ret = self.session.query("SELECT i256_add(toInt256(-50), toInt256(30))", "CSV")
        self.assertEqual(str(ret).strip(), "-20")
        chdb.drop_function("i256_add")

    def test_create_function_int256_lambda_explicit(self):
        chdb.create_function("i256_double", lambda x: x * 2, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_double(toInt256(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT i256_double(toInt256(-250))", "CSV")
        self.assertEqual(str(ret).strip(), "-500")
        chdb.drop_function("i256_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_int256_return_no_arg_types(self):
        def str_len_i256(s):
            return len(s)

        chdb.create_function("i256_strlen", str_len_i256, return_type=INT256)
        ret = self.session.query("SELECT i256_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT i256_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i256_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_i256(x: int) -> int:
            return x + 1

        chdb.create_function("i256_inc_override", inc_i256, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_inc_override(toInt256(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT i256_inc_override(toInt256(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i256_inc_override")

    # ── create_function: string type names ──

    def test_create_function_int256_string_types(self):
        chdb.create_function("i256_inc_str", lambda x: x + 1, arg_types=["Int256"], return_type="Int256")
        ret = self.session.query("SELECT i256_inc_str(toInt256(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT i256_inc_str(toInt256(-1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("i256_inc_str")

    # ── create_function: int256 as arg_type ──

    def test_create_function_int256_as_arg_type(self):
        def neg_i256(x):
            return -x

        chdb.create_function("i256_neg", neg_i256, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_neg(toInt256(12345))", "CSV")
        self.assertEqual(str(ret).strip(), "-12345")
        ret = self.session.query("SELECT i256_neg(toInt256(-67890))", "CSV")
        self.assertEqual(str(ret).strip(), "67890")
        chdb.drop_function("i256_neg")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("i256_dummy", dummy, arg_types=[INT256], return_type=INT256)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("i256_check", lambda x: x, arg_types=[INT256], return_type=INT256)
        with self.assertRaises(Exception):
            self.session.query("SELECT i256_check('hello')", "CSV")
        chdb.drop_function("i256_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("i256_compat", lambda x: x + 1, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_compat(toInt128(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("i256_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_int256_explicit_all(self):
        @func(arg_types=[INT256, INT256], return_type=INT256)
        def dec_i256_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_i256_add(toInt256(300), toInt256(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_i256_add(toInt256(-300), toInt256(400))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        chdb.drop_function("dec_i256_add")

    def test_func_decorator_int256_return_only(self):
        @func(return_type=INT256)
        def dec_i256_one(x):
            return 1

        ret = self.session.query("SELECT dec_i256_one(toInt256(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_i256_one(toInt256(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_i256_one")

    # ── return value out of range (wide integer overflow not detected, wraps silently) ──

    def test_return_value_overflow_wraps(self):
        chdb.create_function("i256_overflow", lambda x: 2**255, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_overflow(toInt256(1))", "CSV")
        self.assertEqual(str(ret).strip(), str(-(2**255)))
        chdb.drop_function("i256_overflow")

    def test_return_value_underflow_wraps(self):
        chdb.create_function("i256_underflow", lambda x: -(2**255) - 1, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_underflow(toInt256(1))", "CSV")
        self.assertEqual(str(ret).strip(), str(2**255 - 1))
        chdb.drop_function("i256_underflow")

    # (no input arg overflow/underflow — Int256 is the widest signed integer type)

    # ── drop_function removes UDF ──

    def test_drop_function_removes_int256_udf(self):
        chdb.create_function("i256_to_drop", lambda x: x + 1, arg_types=[INT256], return_type=INT256)
        ret = self.session.query("SELECT i256_to_drop(toInt256(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("i256_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT i256_to_drop(toInt256(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=INT256)
        def i256_py_callable(x):
            return x + 1

        self.assertEqual(i256_py_callable(5), 6)
        self.assertEqual(i256_py_callable(-1), 0)
        chdb.drop_function("i256_py_callable")

    # ── large integers beyond Int64 range ──

    def test_large_integer_beyond_int64_range(self):
        chdb.create_function("i256_big64", lambda x, y: x + y, arg_types=[INT256, INT256], return_type=INT256)
        ret = self.session.query(
            "SELECT i256_big64(toInt256('10000000000000000000'), toInt256('20000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "30000000000000000000")
        chdb.drop_function("i256_big64")

    # ── large integers beyond Int128 range ──

    def test_large_integer_beyond_int128_range(self):
        v = 200000000000000000000000000000000000000
        chdb.create_function("i256_huge_add", lambda x, y: x + y, arg_types=[INT256, INT256], return_type=INT256)
        ret = self.session.query(f"SELECT i256_huge_add(toInt256('{v}'), toInt256('{v}'))", "CSV")
        self.assertEqual(str(ret).strip(), str(v * 2))
        chdb.drop_function("i256_huge_add")

    def test_large_negative_integer_beyond_int128_range(self):
        v = 200000000000000000000000000000000000000
        chdb.create_function("i256_huge_neg", lambda x: -x, arg_types=[INT256], return_type=INT256)
        ret = self.session.query(f"SELECT i256_huge_neg(toInt256('{v}'))", "CSV")
        self.assertEqual(str(ret).strip(), str(-v))
        ret = self.session.query(f"SELECT i256_huge_neg(toInt256('{-v}'))", "CSV")
        self.assertEqual(str(ret).strip(), str(v))
        chdb.drop_function("i256_huge_neg")


# ═══════════════════════════════════════════════════════════════════
# Unsigned Integer Types
# ═══════════════════════════════════════════════════════════════════


class TestUInt8UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint8_return_explicit_arg_types(self):
        def add_u8(x, y):
            return x + y

        chdb.create_function("u8_add", add_u8, arg_types=[UINT8, UINT8], return_type=UINT8)
        ret = self.session.query("SELECT u8_add(toUInt8(10), toUInt8(20))", "CSV")
        self.assertEqual(str(ret).strip(), "30")
        ret = self.session.query("SELECT u8_add(toUInt8(100), toUInt8(50))", "CSV")
        self.assertEqual(str(ret).strip(), "150")
        chdb.drop_function("u8_add")

    def test_create_function_uint8_lambda_explicit(self):
        chdb.create_function("u8_double", lambda x: x * 2, arg_types=[UINT8], return_type=UINT8)
        ret = self.session.query("SELECT u8_double(toUInt8(50))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT u8_double(toUInt8(10))", "CSV")
        self.assertEqual(str(ret).strip(), "20")
        chdb.drop_function("u8_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint8_return_no_arg_types(self):
        def str_len_u8(s):
            return len(s)

        chdb.create_function("u8_strlen", str_len_u8, return_type=UINT8)
        ret = self.session.query("SELECT u8_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u8_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u8_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u8(x: int) -> int:
            return x + 1

        chdb.create_function("u8_inc_override", inc_u8, arg_types=[UINT8], return_type=UINT8)
        ret = self.session.query("SELECT u8_inc_override(toUInt8(10))", "CSV")
        self.assertEqual(str(ret).strip(), "11")
        ret = self.session.query("SELECT u8_inc_override(toUInt8(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u8_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint8_string_types(self):
        chdb.create_function("u8_inc_str", lambda x: x + 1, arg_types=["UInt8"], return_type="UInt8")
        ret = self.session.query("SELECT u8_inc_str(toUInt8(9))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        ret = self.session.query("SELECT u8_inc_str(toUInt8(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u8_inc_str")

    # ── create_function: uint8 as arg_type ──

    def test_create_function_uint8_as_arg_type(self):
        def identity_u8(x):
            return x

        chdb.create_function("u8_id", identity_u8, arg_types=[UINT8], return_type=UINT8)
        ret = self.session.query("SELECT u8_id(toUInt8(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u8_id(toUInt8(255))", "CSV")
        self.assertEqual(str(ret).strip(), "255")
        chdb.drop_function("u8_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u8_dummy", dummy, arg_types=[UINT8], return_type=UINT8)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u8_check", lambda x: x, arg_types=[UINT8], return_type=UINT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT u8_check('hello')", "CSV")
        chdb.drop_function("u8_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u8_compat", lambda x: x + 1, arg_types=[UINT16], return_type=UINT8)
        ret = self.session.query("SELECT u8_compat(toUInt8(5))", "CSV")
        self.assertEqual(str(ret).strip(), "6")
        chdb.drop_function("u8_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint8_explicit_all(self):
        @func(arg_types=[UINT8, UINT8], return_type=UINT8)
        def dec_u8_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u8_add(toUInt8(3), toUInt8(4))", "CSV")
        self.assertEqual(str(ret).strip(), "7")
        ret = self.session.query("SELECT dec_u8_add(toUInt8(100), toUInt8(50))", "CSV")
        self.assertEqual(str(ret).strip(), "150")
        chdb.drop_function("dec_u8_add")

    def test_func_decorator_uint8_return_only(self):
        @func(return_type=UINT8)
        def dec_u8_one(x):
            return 1

        ret = self.session.query("SELECT dec_u8_one(toUInt8(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u8_one(toUInt8(99))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u8_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("u8_overflow", lambda x: 300, arg_types=[UINT8], return_type=UINT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT u8_overflow(toUInt8(1))", "CSV")
        chdb.drop_function("u8_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u8_underflow", lambda x: -1, arg_types=[UINT8], return_type=UINT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT u8_underflow(toUInt8(1))", "CSV")
        chdb.drop_function("u8_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("u8_input_ovf", lambda x: x, arg_types=[UINT8], return_type=UINT8)
        with self.assertRaises(Exception):
            self.session.query("SELECT u8_input_ovf(toUInt16(300))", "CSV")
        chdb.drop_function("u8_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint8_udf(self):
        chdb.create_function("u8_to_drop", lambda x: x + 1, arg_types=[UINT8], return_type=UINT8)
        ret = self.session.query("SELECT u8_to_drop(toUInt8(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u8_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u8_to_drop(toUInt8(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT8)
        def u8_py_callable(x):
            return x + 1

        self.assertEqual(u8_py_callable(5), 6)
        self.assertEqual(u8_py_callable(0), 1)
        chdb.drop_function("u8_py_callable")


class TestUInt16UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint16_return_explicit_arg_types(self):
        def add_u16(x, y):
            return x + y

        chdb.create_function("u16_add", add_u16, arg_types=[UINT16, UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_add(toUInt16(1000), toUInt16(2000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000")
        ret = self.session.query("SELECT u16_add(toUInt16(30000), toUInt16(20000))", "CSV")
        self.assertEqual(str(ret).strip(), "50000")
        chdb.drop_function("u16_add")

    def test_create_function_uint16_lambda_explicit(self):
        chdb.create_function("u16_double", lambda x: x * 2, arg_types=[UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_double(toUInt16(100))", "CSV")
        self.assertEqual(str(ret).strip(), "200")
        ret = self.session.query("SELECT u16_double(toUInt16(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        chdb.drop_function("u16_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint16_return_no_arg_types(self):
        def str_len_u16(s):
            return len(s)

        chdb.create_function("u16_strlen", str_len_u16, return_type=UINT16)
        ret = self.session.query("SELECT u16_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u16_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u16_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u16(x: int) -> int:
            return x + 1

        chdb.create_function("u16_inc_override", inc_u16, arg_types=[UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_inc_override(toUInt16(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT u16_inc_override(toUInt16(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u16_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint16_string_types(self):
        chdb.create_function("u16_inc_str", lambda x: x + 1, arg_types=["UInt16"], return_type="UInt16")
        ret = self.session.query("SELECT u16_inc_str(toUInt16(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT u16_inc_str(toUInt16(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u16_inc_str")

    # ── create_function: uint16 as arg_type ──

    def test_create_function_uint16_as_arg_type(self):
        def identity_u16(x):
            return x

        chdb.create_function("u16_id", identity_u16, arg_types=[UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_id(toUInt16(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u16_id(toUInt16(65535))", "CSV")
        self.assertEqual(str(ret).strip(), "65535")
        chdb.drop_function("u16_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u16_dummy", dummy, arg_types=[UINT16], return_type=UINT16)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u16_check", lambda x: x, arg_types=[UINT16], return_type=UINT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT u16_check('hello')", "CSV")
        chdb.drop_function("u16_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u16_compat", lambda x: x + 1, arg_types=[UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_compat(toUInt8(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("u16_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint16_explicit_all(self):
        @func(arg_types=[UINT16, UINT16], return_type=UINT16)
        def dec_u16_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u16_add(toUInt16(300), toUInt16(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_u16_add(toUInt16(30000), toUInt16(20000))", "CSV")
        self.assertEqual(str(ret).strip(), "50000")
        chdb.drop_function("dec_u16_add")

    def test_func_decorator_uint16_return_only(self):
        @func(return_type=UINT16)
        def dec_u16_one(x):
            return 1

        ret = self.session.query("SELECT dec_u16_one(toUInt16(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u16_one(toUInt16(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u16_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("u16_overflow", lambda x: 70000, arg_types=[UINT16], return_type=UINT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT u16_overflow(toUInt16(1))", "CSV")
        chdb.drop_function("u16_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u16_underflow", lambda x: -1, arg_types=[UINT16], return_type=UINT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT u16_underflow(toUInt16(1))", "CSV")
        chdb.drop_function("u16_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("u16_input_ovf", lambda x: x, arg_types=[UINT16], return_type=UINT16)
        with self.assertRaises(Exception):
            self.session.query("SELECT u16_input_ovf(toUInt32(70000))", "CSV")
        chdb.drop_function("u16_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint16_udf(self):
        chdb.create_function("u16_to_drop", lambda x: x + 1, arg_types=[UINT16], return_type=UINT16)
        ret = self.session.query("SELECT u16_to_drop(toUInt16(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u16_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u16_to_drop(toUInt16(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT16)
        def u16_py_callable(x):
            return x + 1

        self.assertEqual(u16_py_callable(5), 6)
        self.assertEqual(u16_py_callable(0), 1)
        chdb.drop_function("u16_py_callable")


class TestUInt32UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint32_return_explicit_arg_types(self):
        def add_u32(x, y):
            return x + y

        chdb.create_function("u32_add", add_u32, arg_types=[UINT32, UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_add(toUInt32(100000), toUInt32(200000))", "CSV")
        self.assertEqual(str(ret).strip(), "300000")
        ret = self.session.query("SELECT u32_add(toUInt32(3000000000), toUInt32(1000000000))", "CSV")
        self.assertEqual(str(ret).strip(), "4000000000")
        chdb.drop_function("u32_add")

    def test_create_function_uint32_lambda_explicit(self):
        chdb.create_function("u32_double", lambda x: x * 2, arg_types=[UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_double(toUInt32(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT u32_double(toUInt32(1000000))", "CSV")
        self.assertEqual(str(ret).strip(), "2000000")
        chdb.drop_function("u32_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint32_return_no_arg_types(self):
        def str_len_u32(s):
            return len(s)

        chdb.create_function("u32_strlen", str_len_u32, return_type=UINT32)
        ret = self.session.query("SELECT u32_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u32_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u32_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u32(x: int) -> int:
            return x + 1

        chdb.create_function("u32_inc_override", inc_u32, arg_types=[UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_inc_override(toUInt32(99999))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT u32_inc_override(toUInt32(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u32_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint32_string_types(self):
        chdb.create_function("u32_inc_str", lambda x: x + 1, arg_types=["UInt32"], return_type="UInt32")
        ret = self.session.query("SELECT u32_inc_str(toUInt32(99999))", "CSV")
        self.assertEqual(str(ret).strip(), "100000")
        ret = self.session.query("SELECT u32_inc_str(toUInt32(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u32_inc_str")

    # ── create_function: uint32 as arg_type ──

    def test_create_function_uint32_as_arg_type(self):
        def identity_u32(x):
            return x

        chdb.create_function("u32_id", identity_u32, arg_types=[UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_id(toUInt32(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u32_id(toUInt32(4294967295))", "CSV")
        self.assertEqual(str(ret).strip(), "4294967295")
        chdb.drop_function("u32_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u32_dummy", dummy, arg_types=[UINT32], return_type=UINT32)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u32_check", lambda x: x, arg_types=[UINT32], return_type=UINT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT u32_check('hello')", "CSV")
        chdb.drop_function("u32_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u32_compat", lambda x: x + 1, arg_types=[UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_compat(toUInt16(1000))", "CSV")
        self.assertEqual(str(ret).strip(), "1001")
        chdb.drop_function("u32_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint32_explicit_all(self):
        @func(arg_types=[UINT32, UINT32], return_type=UINT32)
        def dec_u32_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u32_add(toUInt32(30000), toUInt32(40000))", "CSV")
        self.assertEqual(str(ret).strip(), "70000")
        ret = self.session.query("SELECT dec_u32_add(toUInt32(2000000000), toUInt32(1000000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000000")
        chdb.drop_function("dec_u32_add")

    def test_func_decorator_uint32_return_only(self):
        @func(return_type=UINT32)
        def dec_u32_one(x):
            return 1

        ret = self.session.query("SELECT dec_u32_one(toUInt32(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u32_one(toUInt32(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u32_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("u32_overflow", lambda x: 4300000000, arg_types=[UINT32], return_type=UINT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT u32_overflow(toUInt32(1))", "CSV")
        chdb.drop_function("u32_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u32_underflow", lambda x: -1, arg_types=[UINT32], return_type=UINT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT u32_underflow(toUInt32(1))", "CSV")
        chdb.drop_function("u32_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("u32_input_ovf", lambda x: x, arg_types=[UINT32], return_type=UINT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT u32_input_ovf(toUInt64(4300000000))", "CSV")
        chdb.drop_function("u32_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint32_udf(self):
        chdb.create_function("u32_to_drop", lambda x: x + 1, arg_types=[UINT32], return_type=UINT32)
        ret = self.session.query("SELECT u32_to_drop(toUInt32(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u32_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u32_to_drop(toUInt32(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT32)
        def u32_py_callable(x):
            return x + 1

        self.assertEqual(u32_py_callable(5), 6)
        self.assertEqual(u32_py_callable(0), 1)
        chdb.drop_function("u32_py_callable")


class TestUInt64UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint64_return_explicit_arg_types(self):
        def add_u64(x, y):
            return x + y

        chdb.create_function("u64_add", add_u64, arg_types=[UINT64, UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_add(toUInt64(1000000), toUInt64(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        ret = self.session.query("SELECT u64_add(toUInt64(10000000000), toUInt64(5000000000))", "CSV")
        self.assertEqual(str(ret).strip(), "15000000000")
        chdb.drop_function("u64_add")

    def test_create_function_uint64_lambda_explicit(self):
        chdb.create_function("u64_double", lambda x: x * 2, arg_types=[UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_double(toUInt64(500000))", "CSV")
        self.assertEqual(str(ret).strip(), "1000000")
        ret = self.session.query("SELECT u64_double(toUInt64(5000000000))", "CSV")
        self.assertEqual(str(ret).strip(), "10000000000")
        chdb.drop_function("u64_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint64_return_no_arg_types(self):
        def str_len_u64(s):
            return len(s)

        chdb.create_function("u64_strlen", str_len_u64, return_type=UINT64)
        ret = self.session.query("SELECT u64_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u64_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u64_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u64(x: int) -> int:
            return x + 1

        chdb.create_function("u64_inc_override", inc_u64, arg_types=[UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_inc_override(toUInt64(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000000")
        ret = self.session.query("SELECT u64_inc_override(toUInt64(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u64_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint64_string_types(self):
        chdb.create_function("u64_inc_str", lambda x: x + 1, arg_types=["UInt64"], return_type="UInt64")
        ret = self.session.query("SELECT u64_inc_str(toUInt64(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1000000")
        ret = self.session.query("SELECT u64_inc_str(toUInt64(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u64_inc_str")

    # ── create_function: uint64 as arg_type ──

    def test_create_function_uint64_as_arg_type(self):
        def identity_u64(x):
            return x

        chdb.create_function("u64_id", identity_u64, arg_types=[UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_id(toUInt64(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u64_id(toUInt64(18446744073709551615))", "CSV")
        self.assertEqual(str(ret).strip(), "18446744073709551615")
        chdb.drop_function("u64_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u64_dummy", dummy, arg_types=[UINT64], return_type=UINT64)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u64_check", lambda x: x, arg_types=[UINT64], return_type=UINT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT u64_check('hello')", "CSV")
        chdb.drop_function("u64_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u64_compat", lambda x: x + 1, arg_types=[UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_compat(toUInt32(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("u64_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint64_explicit_all(self):
        @func(arg_types=[UINT64, UINT64], return_type=UINT64)
        def dec_u64_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u64_add(toUInt64(300000), toUInt64(400000))", "CSV")
        self.assertEqual(str(ret).strip(), "700000")
        ret = self.session.query("SELECT dec_u64_add(toUInt64(10000000000), toUInt64(5000000000))", "CSV")
        self.assertEqual(str(ret).strip(), "15000000000")
        chdb.drop_function("dec_u64_add")

    def test_func_decorator_uint64_return_only(self):
        @func(return_type=UINT64)
        def dec_u64_one(x):
            return 1

        ret = self.session.query("SELECT dec_u64_one(toUInt64(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u64_one(toUInt64(999999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u64_one")

    # ── return value out of range ──

    def test_return_value_overflow_raises(self):
        chdb.create_function("u64_overflow", lambda x: 2**64, arg_types=[UINT64], return_type=UINT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT u64_overflow(toUInt64(1))", "CSV")
        chdb.drop_function("u64_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u64_underflow", lambda x: -1, arg_types=[UINT64], return_type=UINT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT u64_underflow(toUInt64(1))", "CSV")
        chdb.drop_function("u64_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("u64_input_ovf", lambda x: x, arg_types=[UINT64], return_type=UINT64)
        with self.assertRaises(Exception):
            self.session.query("SELECT u64_input_ovf(toUInt128(18446744073709551616))", "CSV")
        chdb.drop_function("u64_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint64_udf(self):
        chdb.create_function("u64_to_drop", lambda x: x + 1, arg_types=[UINT64], return_type=UINT64)
        ret = self.session.query("SELECT u64_to_drop(toUInt64(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u64_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u64_to_drop(toUInt64(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT64)
        def u64_py_callable(x):
            return x + 1

        self.assertEqual(u64_py_callable(5), 6)
        self.assertEqual(u64_py_callable(0), 1)
        chdb.drop_function("u64_py_callable")


class TestUInt128UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint128_return_explicit_arg_types(self):
        def add_u128(x, y):
            return x + y

        chdb.create_function("u128_add", add_u128, arg_types=[UINT128, UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_add(toUInt128(100), toUInt128(200))", "CSV")
        self.assertEqual(str(ret).strip(), "300")
        ret = self.session.query("SELECT u128_add(toUInt128(1000000), toUInt128(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        chdb.drop_function("u128_add")

    def test_create_function_uint128_lambda_explicit(self):
        chdb.create_function("u128_double", lambda x: x * 2, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_double(toUInt128(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT u128_double(toUInt128(1000000))", "CSV")
        self.assertEqual(str(ret).strip(), "2000000")
        chdb.drop_function("u128_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint128_return_no_arg_types(self):
        def str_len_u128(s):
            return len(s)

        chdb.create_function("u128_strlen", str_len_u128, return_type=UINT128)
        ret = self.session.query("SELECT u128_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u128_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u128_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u128(x: int) -> int:
            return x + 1

        chdb.create_function("u128_inc_override", inc_u128, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_inc_override(toUInt128(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT u128_inc_override(toUInt128(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u128_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint128_string_types(self):
        chdb.create_function("u128_inc_str", lambda x: x + 1, arg_types=["UInt128"], return_type="UInt128")
        ret = self.session.query("SELECT u128_inc_str(toUInt128(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT u128_inc_str(toUInt128(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u128_inc_str")

    # ── create_function: uint128 as arg_type ──

    def test_create_function_uint128_as_arg_type(self):
        def identity_u128(x):
            return x

        chdb.create_function("u128_id", identity_u128, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_id(toUInt128(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u128_id(toUInt128(12345))", "CSV")
        self.assertEqual(str(ret).strip(), "12345")
        chdb.drop_function("u128_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u128_dummy", dummy, arg_types=[UINT128], return_type=UINT128)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u128_check", lambda x: x, arg_types=[UINT128], return_type=UINT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT u128_check('hello')", "CSV")
        chdb.drop_function("u128_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u128_compat", lambda x: x + 1, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_compat(toUInt64(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("u128_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint128_explicit_all(self):
        @func(arg_types=[UINT128, UINT128], return_type=UINT128)
        def dec_u128_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u128_add(toUInt128(300), toUInt128(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_u128_add(toUInt128(1000000), toUInt128(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        chdb.drop_function("dec_u128_add")

    def test_func_decorator_uint128_return_only(self):
        @func(return_type=UINT128)
        def dec_u128_one(x):
            return 1

        ret = self.session.query("SELECT dec_u128_one(toUInt128(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u128_one(toUInt128(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u128_one")

    # ── return value out of range (wide integer overflow not detected, wraps silently) ──

    def test_return_value_overflow_wraps(self):
        chdb.create_function("u128_overflow", lambda x: 2**128, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_overflow(toUInt128(1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("u128_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u128_underflow", lambda x: -1, arg_types=[UINT128], return_type=UINT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT u128_underflow(toUInt128(1))", "CSV")
        chdb.drop_function("u128_underflow")

    # ── input arg out of range ──

    def test_input_arg_overflow_raises(self):
        chdb.create_function("u128_input_ovf", lambda x: x, arg_types=[UINT128], return_type=UINT128)
        with self.assertRaises(Exception):
            self.session.query("SELECT u128_input_ovf(toUInt256(340282366920938463463374607431768211456))", "CSV")
        chdb.drop_function("u128_input_ovf")

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint128_udf(self):
        chdb.create_function("u128_to_drop", lambda x: x + 1, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_to_drop(toUInt128(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u128_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u128_to_drop(toUInt128(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT128)
        def u128_py_callable(x):
            return x + 1

        self.assertEqual(u128_py_callable(5), 6)
        self.assertEqual(u128_py_callable(0), 1)
        chdb.drop_function("u128_py_callable")

    # ── large integers beyond UInt64 range ──

    def test_large_integer_beyond_uint64_range(self):
        chdb.create_function("u128_big_add", lambda x, y: x + y, arg_types=[UINT128, UINT128], return_type=UINT128)
        ret = self.session.query(
            "SELECT u128_big_add(toUInt128('100000000000000000000'), toUInt128('200000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "300000000000000000000")
        chdb.drop_function("u128_big_add")

    def test_large_integer_identity_beyond_uint64_range(self):
        chdb.create_function("u128_big_id", lambda x: x, arg_types=[UINT128], return_type=UINT128)
        ret = self.session.query("SELECT u128_big_id(toUInt128('100000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "100000000000000000000")
        chdb.drop_function("u128_big_id")


class TestUInt256UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    # ── create_function: explicit return_type + explicit arg_types ──

    def test_create_function_uint256_return_explicit_arg_types(self):
        def add_u256(x, y):
            return x + y

        chdb.create_function("u256_add", add_u256, arg_types=[UINT256, UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_add(toUInt256(100), toUInt256(200))", "CSV")
        self.assertEqual(str(ret).strip(), "300")
        ret = self.session.query("SELECT u256_add(toUInt256(1000000), toUInt256(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        chdb.drop_function("u256_add")

    def test_create_function_uint256_lambda_explicit(self):
        chdb.create_function("u256_double", lambda x: x * 2, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_double(toUInt256(500))", "CSV")
        self.assertEqual(str(ret).strip(), "1000")
        ret = self.session.query("SELECT u256_double(toUInt256(1000000))", "CSV")
        self.assertEqual(str(ret).strip(), "2000000")
        chdb.drop_function("u256_double")

    # ── create_function: return_type only, no arg_types ──

    def test_create_function_uint256_return_no_arg_types(self):
        def str_len_u256(s):
            return len(s)

        chdb.create_function("u256_strlen", str_len_u256, return_type=UINT256)
        ret = self.session.query("SELECT u256_strlen('hello')", "CSV")
        self.assertEqual(str(ret).strip(), "5")
        ret = self.session.query("SELECT u256_strlen('hi')", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u256_strlen")

    # ── create_function: explicit arg_types override annotations ──

    def test_create_function_explicit_arg_types_override_annotations(self):
        def inc_u256(x: int) -> int:
            return x + 1

        chdb.create_function("u256_inc_override", inc_u256, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_inc_override(toUInt256(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT u256_inc_override(toUInt256(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u256_inc_override")

    # ── create_function: string type names ──

    def test_create_function_uint256_string_types(self):
        chdb.create_function("u256_inc_str", lambda x: x + 1, arg_types=["UInt256"], return_type="UInt256")
        ret = self.session.query("SELECT u256_inc_str(toUInt256(99))", "CSV")
        self.assertEqual(str(ret).strip(), "100")
        ret = self.session.query("SELECT u256_inc_str(toUInt256(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("u256_inc_str")

    # ── create_function: uint256 as arg_type ──

    def test_create_function_uint256_as_arg_type(self):
        def identity_u256(x):
            return x

        chdb.create_function("u256_id", identity_u256, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_id(toUInt256(0))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        ret = self.session.query("SELECT u256_id(toUInt256(12345))", "CSV")
        self.assertEqual(str(ret).strip(), "12345")
        chdb.drop_function("u256_id")

    # ── create_function: arg_types count mismatch ──

    def test_create_function_arg_types_count_mismatch(self):
        def dummy(a, b):
            return a + b

        with self.assertRaises(RuntimeError):
            chdb.create_function("u256_dummy", dummy, arg_types=[UINT256], return_type=UINT256)

    # ── create_function: arg type validation at query time ──

    def test_create_function_arg_type_mismatch_at_query(self):
        chdb.create_function("u256_check", lambda x: x, arg_types=[UINT256], return_type=UINT256)
        with self.assertRaises(Exception):
            self.session.query("SELECT u256_check('hello')", "CSV")
        chdb.drop_function("u256_check")

    # ── create_function: compatible arg type (smaller type → declared type) ──

    def test_create_function_compatible_arg_type(self):
        chdb.create_function("u256_compat", lambda x: x + 1, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_compat(toUInt128(42))", "CSV")
        self.assertEqual(str(ret).strip(), "43")
        chdb.drop_function("u256_compat")

    # ── @func decorator: explicit return_type + explicit arg_types ──

    def test_func_decorator_uint256_explicit_all(self):
        @func(arg_types=[UINT256, UINT256], return_type=UINT256)
        def dec_u256_add(x, y):
            return x + y

        ret = self.session.query("SELECT dec_u256_add(toUInt256(300), toUInt256(400))", "CSV")
        self.assertEqual(str(ret).strip(), "700")
        ret = self.session.query("SELECT dec_u256_add(toUInt256(1000000), toUInt256(2000000))", "CSV")
        self.assertEqual(str(ret).strip(), "3000000")
        chdb.drop_function("dec_u256_add")

    def test_func_decorator_uint256_return_only(self):
        @func(return_type=UINT256)
        def dec_u256_one(x):
            return 1

        ret = self.session.query("SELECT dec_u256_one(toUInt256(0))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        ret = self.session.query("SELECT dec_u256_one(toUInt256(999))", "CSV")
        self.assertEqual(str(ret).strip(), "1")
        chdb.drop_function("dec_u256_one")

    # ── return value out of range (wide integer overflow not detected, wraps silently) ──

    def test_return_value_overflow_wraps(self):
        chdb.create_function("u256_overflow", lambda x: 2**256, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_overflow(toUInt256(1))", "CSV")
        self.assertEqual(str(ret).strip(), "0")
        chdb.drop_function("u256_overflow")

    def test_return_value_underflow_raises(self):
        chdb.create_function("u256_underflow", lambda x: -1, arg_types=[UINT256], return_type=UINT256)
        with self.assertRaises(Exception):
            self.session.query("SELECT u256_underflow(toUInt256(1))", "CSV")
        chdb.drop_function("u256_underflow")

    # (no input arg overflow — UInt256 is the widest unsigned integer type)

    # ── drop_function removes UDF ──

    def test_drop_function_removes_uint256_udf(self):
        chdb.create_function("u256_to_drop", lambda x: x + 1, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query("SELECT u256_to_drop(toUInt256(1))", "CSV")
        self.assertEqual(str(ret).strip(), "2")
        chdb.drop_function("u256_to_drop")
        with self.assertRaises(Exception):
            self.session.query("SELECT u256_to_drop(toUInt256(1))", "CSV")

    # ── Python callability preserved ──

    def test_func_decorator_preserves_python_callability(self):
        @func(return_type=UINT256)
        def u256_py_callable(x):
            return x + 1

        self.assertEqual(u256_py_callable(5), 6)
        self.assertEqual(u256_py_callable(0), 1)
        chdb.drop_function("u256_py_callable")

    # ── large integers beyond UInt64 range ──

    def test_large_integer_beyond_uint64_range(self):
        chdb.create_function("u256_big64", lambda x, y: x + y, arg_types=[UINT256, UINT256], return_type=UINT256)
        ret = self.session.query(
            "SELECT u256_big64(toUInt256('100000000000000000000'), toUInt256('200000000000000000000'))", "CSV")
        self.assertEqual(str(ret).strip(), "300000000000000000000")
        chdb.drop_function("u256_big64")

    # ── large integers beyond UInt128 range ──

    def test_large_integer_beyond_uint128_range(self):
        v = 400000000000000000000000000000000000000
        chdb.create_function("u256_huge_add", lambda x, y: x + y, arg_types=[UINT256, UINT256], return_type=UINT256)
        ret = self.session.query(f"SELECT u256_huge_add(toUInt256('{v}'), toUInt256('{v}'))", "CSV")
        self.assertEqual(str(ret).strip(), str(v * 2))
        chdb.drop_function("u256_huge_add")

    def test_large_integer_identity_beyond_uint128_range(self):
        v = 400000000000000000000000000000000000000
        chdb.create_function("u256_huge_id", lambda x: x, arg_types=[UINT256], return_type=UINT256)
        ret = self.session.query(f"SELECT u256_huge_id(toUInt256('{v}'))", "CSV")
        self.assertEqual(str(ret).strip(), str(v))
        chdb.drop_function("u256_huge_id")


# ═══════════════════════════════════════════════════════════════════
# Float Types
# ═══════════════════════════════════════════════════════════════════


@unittest.skip("TODO")
class TestFloat32UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        chdb.create_function("f32_half", lambda x: x / 2, arg_types=[FLOAT32], return_type=FLOAT32)
        ret = self.session.query("SELECT f32_half(toFloat32(7.0))", "CSV")
        self.assertEqual(str(ret).strip(), "3.5")
        chdb.drop_function("f32_half")

    def test_string_type_name(self):
        chdb.create_function("f32_double", lambda x: x * 2, arg_types=["Float32"], return_type="Float32")
        ret = self.session.query("SELECT f32_double(toFloat32(1.5))", "CSV")
        self.assertEqual(str(ret).strip(), "3")
        chdb.drop_function("f32_double")

    def test_func_decorator(self):
        @func(arg_types=[FLOAT32, FLOAT32], return_type=FLOAT32)
        def f32_avg(a, b):
            return (a + b) / 2

        ret = self.session.query("SELECT f32_avg(toFloat32(3.0), toFloat32(5.0))", "CSV")
        self.assertEqual(str(ret).strip(), "4")
        chdb.drop_function("f32_avg")

    def test_arg_type_mismatch(self):
        chdb.create_function("f32_check", lambda x: x, arg_types=[FLOAT32], return_type=FLOAT32)
        with self.assertRaises(Exception):
            self.session.query("SELECT f32_check('hello')", "CSV")
        chdb.drop_function("f32_check")


@unittest.skip("TODO")
class TestFloat64UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        chdb.create_function("f64_half", lambda x: x / 2, arg_types=[FLOAT64], return_type=FLOAT64)
        ret = self.session.query("SELECT f64_half(toFloat64(7.0))", "CSV")
        self.assertEqual(str(ret).strip(), "3.5")
        chdb.drop_function("f64_half")

    def test_string_type_name(self):
        chdb.create_function("f64_double", lambda x: x * 2, arg_types=["Float64"], return_type="Float64")
        ret = self.session.query("SELECT f64_double(toFloat64(1.25))", "CSV")
        self.assertEqual(str(ret).strip(), "2.5")
        chdb.drop_function("f64_double")

    def test_func_decorator(self):
        @func(arg_types=[FLOAT64, FLOAT64], return_type=FLOAT64)
        def f64_avg(a, b):
            return (a + b) / 2

        ret = self.session.query("SELECT f64_avg(toFloat64(3.0), toFloat64(5.0))", "CSV")
        self.assertEqual(str(ret).strip(), "4")
        chdb.drop_function("f64_avg")

    def test_compatible_arg_type_float32_to_float64(self):
        chdb.create_function("f64_compat", lambda x: x, arg_types=[FLOAT64], return_type=FLOAT64)
        ret = self.session.query("SELECT f64_compat(toFloat32(2.5))", "CSV")
        self.assertEqual(str(ret).strip(), "2.5")
        chdb.drop_function("f64_compat")

    def test_infer_all_from_annotations(self):
        def f64_annotated(a: float, b: float) -> float:
            return a * b

        chdb.create_function("f64_annotated", f64_annotated)
        ret = self.session.query("SELECT f64_annotated(toFloat64(2.5), toFloat64(4.0))", "CSV")
        self.assertEqual(str(ret).strip(), "10")
        chdb.drop_function("f64_annotated")

    def test_infer_return_from_annotation(self):
        def f64_ret_only(x) -> float:
            return x * 0.5

        chdb.create_function("f64_ret_only", f64_ret_only)
        ret = self.session.query("SELECT f64_ret_only(toFloat64(5.0))", "CSV")
        self.assertEqual(str(ret).strip(), "2.5")
        chdb.drop_function("f64_ret_only")


# ═══════════════════════════════════════════════════════════════════
# String Type
# ═══════════════════════════════════════════════════════════════════


@unittest.skip("TODO")
class TestStringUDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        chdb.create_function("str_upper", lambda s: s.upper(), arg_types=[STRING], return_type=STRING)
        ret = self.session.query("SELECT str_upper('hello')", "CSV")
        self.assertEqual(str(ret).strip(), '"HELLO"')
        chdb.drop_function("str_upper")

    def test_string_type_name(self):
        chdb.create_function("str_rev", lambda s: s[::-1], arg_types=["String"], return_type="String")
        ret = self.session.query("SELECT str_rev('abcde')", "CSV")
        self.assertEqual(str(ret).strip(), '"edcba"')
        chdb.drop_function("str_rev")

    def test_func_decorator(self):
        @func(arg_types=[STRING, STRING], return_type=STRING)
        def str_concat(a, b):
            return a + b

        ret = self.session.query("SELECT str_concat('hello', ' world')", "CSV")
        self.assertEqual(str(ret).strip(), '"hello world"')
        chdb.drop_function("str_concat")

    def test_infer_all_from_annotations(self):
        def str_annotated(s: str) -> str:
            return s.lower()

        chdb.create_function("str_annotated", str_annotated)
        ret = self.session.query("SELECT str_annotated('HELLO')", "CSV")
        self.assertEqual(str(ret).strip(), '"hello"')
        chdb.drop_function("str_annotated")

    def test_infer_return_from_annotation(self):
        def str_ret_only(s) -> str:
            return s + "!"

        chdb.create_function("str_ret_only", str_ret_only)
        ret = self.session.query("SELECT str_ret_only('hi')", "CSV")
        self.assertEqual(str(ret).strip(), '"hi!"')
        chdb.drop_function("str_ret_only")

    def test_arg_type_mismatch(self):
        chdb.create_function("str_mismatch", lambda s: s, arg_types=[STRING], return_type=STRING)
        with self.assertRaises(Exception):
            self.session.query("SELECT str_mismatch(123)", "CSV")
        chdb.drop_function("str_mismatch")


# ═══════════════════════════════════════════════════════════════════
# Date Types
# ═══════════════════════════════════════════════════════════════════


@unittest.skip("TODO")
class TestDateUDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        def add_day(d):
            return d + datetime.timedelta(days=1)

        chdb.create_function("date_add_day", add_day, arg_types=[DATE], return_type=DATE)
        ret = self.session.query("SELECT date_add_day(toDate('2024-01-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-16"')
        chdb.drop_function("date_add_day")

    def test_string_type_name(self):
        def date_identity(d):
            return d

        chdb.create_function("date_str_name", date_identity, arg_types=["Date"], return_type="Date")
        ret = self.session.query("SELECT date_str_name(toDate('2024-06-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-06-15"')
        chdb.drop_function("date_str_name")

    def test_func_decorator(self):
        @func(arg_types=[DATE], return_type=DATE)
        def date_add_week(d):
            return d + datetime.timedelta(weeks=1)

        ret = self.session.query("SELECT date_add_week(toDate('2024-01-01'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-08"')
        chdb.drop_function("date_add_week")

    def test_infer_all_from_annotations(self):
        def date_infer(d: datetime.date) -> datetime.date:
            return d + datetime.timedelta(days=10)

        chdb.create_function("date_infer", date_infer)
        ret = self.session.query("SELECT date_infer(toDate('2024-01-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-25"')
        chdb.drop_function("date_infer")

    def test_extract_component_as_int(self):
        def date_year(d):
            return d.year

        chdb.create_function("date_year", date_year, arg_types=[DATE], return_type=INT32)
        ret = self.session.query("SELECT date_year(toDate('2024-06-15'))", "CSV")
        self.assertEqual(str(ret).strip(), "2024")
        chdb.drop_function("date_year")


@unittest.skip("TODO")
class TestDate32UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        def add_day32(d):
            return d + datetime.timedelta(days=1)

        chdb.create_function("d32_add_day", add_day32, arg_types=[DATE32], return_type=DATE32)
        ret = self.session.query("SELECT d32_add_day(toDate32('2024-01-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-16"')
        chdb.drop_function("d32_add_day")

    def test_string_type_name(self):
        def d32_identity(d):
            return d

        chdb.create_function("d32_str_name", d32_identity, arg_types=["Date32"], return_type="Date32")
        ret = self.session.query("SELECT d32_str_name(toDate32('2024-06-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-06-15"')
        chdb.drop_function("d32_str_name")

    def test_func_decorator(self):
        @func(arg_types=[DATE32], return_type=DATE32)
        def d32_add_month(d):
            month = d.month % 12 + 1
            year = d.year + (1 if d.month == 12 else 0)
            return d.replace(year=year, month=month)

        ret = self.session.query("SELECT d32_add_month(toDate32('2024-01-15'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-02-15"')
        chdb.drop_function("d32_add_month")

    def test_compatible_arg_type_date_to_date32(self):
        chdb.create_function("d32_compat", lambda d: d, arg_types=[DATE32], return_type=DATE32)
        ret = self.session.query("SELECT d32_compat(toDate('2024-03-01'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-03-01"')
        chdb.drop_function("d32_compat")


# ═══════════════════════════════════════════════════════════════════
# DateTime Types
# ═══════════════════════════════════════════════════════════════════


@unittest.skip("TODO")
class TestDateTimeUDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        def dt_identity(d):
            return d

        chdb.create_function("dt_id", dt_identity, arg_types=[DATETIME], return_type=DATETIME)
        ret = self.session.query("SELECT dt_id(toDateTime('2024-01-15 10:30:00'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-15 10:30:00"')
        chdb.drop_function("dt_id")

    def test_string_type_name(self):
        def dt_str_id(d):
            return d

        chdb.create_function("dt_str_name", dt_str_id, arg_types=["DateTime"], return_type="DateTime")
        ret = self.session.query("SELECT dt_str_name(toDateTime('2024-06-15 08:00:00'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-06-15 08:00:00"')
        chdb.drop_function("dt_str_name")

    def test_func_decorator(self):
        @func(arg_types=[DATETIME], return_type=INT32)
        def dt_hour(d):
            return d.hour

        ret = self.session.query("SELECT dt_hour(toDateTime('2024-01-15 14:30:00'))", "CSV")
        self.assertEqual(str(ret).strip(), "14")
        chdb.drop_function("dt_hour")

    def test_extract_components(self):
        def dt_minute(d):
            return d.minute

        chdb.create_function("dt_minute", dt_minute, arg_types=[DATETIME], return_type=INT32)
        ret = self.session.query("SELECT dt_minute(toDateTime('2024-01-15 10:45:00'))", "CSV")
        self.assertEqual(str(ret).strip(), "45")
        chdb.drop_function("dt_minute")


@unittest.skip("TODO")
class TestDateTime64UDF(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def tearDown(self):
        self.session.close()

    def test_create_function_explicit(self):
        def dt64_identity(d):
            return d

        chdb.create_function("dt64_id", dt64_identity, arg_types=[DATETIME64], return_type=DATETIME64)
        ret = self.session.query("SELECT dt64_id(toDateTime64('2024-01-15 10:30:00.123', 3))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-15 10:30:00.123"')
        chdb.drop_function("dt64_id")

    def test_string_type_name(self):
        def dt64_str_id(d):
            return d

        chdb.create_function("dt64_str_name", dt64_str_id,
                             arg_types=["DateTime64(3)"], return_type="DateTime64(3)")
        ret = self.session.query("SELECT dt64_str_name(toDateTime64('2024-06-15 08:00:00.456', 3))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-06-15 08:00:00.456"')
        chdb.drop_function("dt64_str_name")

    def test_func_decorator(self):
        @func(arg_types=[DATETIME64], return_type=INT32)
        def dt64_ms(d):
            return d.microsecond // 1000

        ret = self.session.query("SELECT dt64_ms(toDateTime64('2024-01-15 10:30:00.789', 3))", "CSV")
        self.assertEqual(str(ret).strip(), "789")
        chdb.drop_function("dt64_ms")

    def test_infer_all_from_annotations(self):
        def dt64_infer(d: datetime.datetime) -> datetime.datetime:
            return d

        chdb.create_function("dt64_infer", dt64_infer)
        ret = self.session.query("SELECT dt64_infer(toDateTime64('2024-01-15 10:30:00.123', 3))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-01-15 10:30:00.123"')
        chdb.drop_function("dt64_infer")

    def test_compatible_arg_type_datetime_to_datetime64(self):
        chdb.create_function("dt64_compat", lambda d: d, arg_types=[DATETIME64], return_type=DATETIME64)
        ret = self.session.query("SELECT dt64_compat(toDateTime('2024-03-01 12:00:00'))", "CSV")
        self.assertEqual(str(ret).strip(), '"2024-03-01 12:00:00.000"')
        chdb.drop_function("dt64_compat")


if __name__ == "__main__":
    unittest.main()
