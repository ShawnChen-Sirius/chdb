import chdb
from chdb.session import Session
from chdb.sqltypes import INT64

def int_add(a, b):
    return a * b

chdb.create_function("int_add", int_add, [], INT64)

session = Session()

ret = session.query("SELECT int_add(6, 7) + 1")
print(str(ret))

chdb.drop_function("int_add")
try:
    ret = session.query("SELECT int_add(6, 7) + 1")
except Exception as e:
    print("raise")

chdb.drop_function("int_add")

chdb.create_function("int_add", int_add, [], "Int64")
ret = session.query("SELECT int_add(6, 7) + 1")
print(str(ret))

def int_add_2(a, b) -> int:
    return a * b - 1

chdb.create_function("int_add_2", int_add_2)
ret = session.query("SELECT int_add_2(6, 7)")
print(str(ret))

@chdb.func()
def int_add_3(a, b) -> int:
    return a * b - 1

ret = session.query("SELECT int_add_3(6, 6)")
print(str(ret))

@chdb.func()
def int_add_4(a: int, b: int) -> int:
    return a * b - 2

session.query("SELECT int_add_4(6, 6)").show()

# @chdb.func()
def int_add_5(a: str, b: int) -> int:
    return 33

# session.query("SELECT int_add_5(6, 6)").show()

chdb.create_function("int_add_5", int_add_5, ["String", "Int64"], "String")
session.query("SELECT int_add_5('6', 6)").show()
